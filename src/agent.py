import asyncio
import json

from openai import AsyncOpenAI


class AI_Agent:

    def __init__(self, Runner) -> None:
        self.Runner = Runner
        self.Running = False
        self.Is_Thinking = False
        self.Task = None
        self.Loop = None
        self.Api_Key = ""
        self.Model = ""
        self.System_Prompt = "You Are an AI Agent. You have access to an python Sandbox. Use the tools provided to you to fullfill the request of the user."
        self.Messages = [{"role": "system", "content": self.System_Prompt}]
        self.Pending_Action = None
        self.Hitl_Response = None
        self.Hitl_Event = None
        self.Client = None

    def Set_Config(self, Api_key, Model, System_Prompt=None):
        self.Api_Key = Api_key
        self.Model = Model
        if System_Prompt:
            self.System_Prompt = System_Prompt
            if len(self.Messages) > 0 and self.Messages[0]["role"] == "system":
                self.Messages[0]["content"] = self.System_Prompt
        self.Client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=self.Api_Key
        )
        self._Notify()

    def Add_User_Message(self, text):
        self.Messages.append({"role": "user", "content": text})
        self._Notify()

    def Start(self, loop):
        if not self.Running:
            self.Running = True
            self.Loop = loop
            self.Task = loop.create_task(self._Execution_Loop())

    def Stop(self):
        self.Running = False

    def _Auto_Commit(self, Action_Name):
        if Action_Name in ["Write_File", "Delete_File", "Replace_In_File"]:
            if hasattr(self.Runner, "Commit"):
                try:
                    self.Runner.Commit(f"Pre-action backup before {Action_Name}")
                except Exception:
                    pass

    async def _Request_Hitl(self, Tool_Name, Kwargs):
        self.Pending_Action = {"tool": Tool_Name, "args": Kwargs}
        self._Notify()

        self.Hitl_Event.clear()
        await self.Hitl_Event.wait()

        Response = self.Hitl_Response
        self.Pending_Action = None
        self.Hitl_Response = None
        self._Notify()
        return Response

    def _Execute_Tool(self, Tool_Name, **Kwargs):
        self._Auto_Commit(Tool_Name)

        if Tool_Name == "Run_Code":
            Code = Kwargs.get("code", "")
            Fname = Kwargs.get("filename", "_run_temp.py")
            try:
                self.Runner.Write_File(Name=Fname, Content=Code)
                Result = self.Runner.Run_Code(Name=Fname)
                return f"stdout: {Result.get('stdout', '')}\nstderr: {Result.get('stderr', '')}\nExit: {Result.get('Exit_Code', '')}"
            except Exception as e:
                return f"Error running code: {e}"

        if hasattr(self.Runner, Tool_Name):
            Func = getattr(self.Runner, Tool_Name)
            try:
                res = Func(**Kwargs)
                if res is None:
                    return f"Action {Tool_Name} completed successfully."
                return str(res)
            except Exception as e:
                return f"Error executing {Tool_Name}: {e}"
        else:
            return f"Error: Tool {Tool_Name} not found in runner."

    def _Get_Tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "Write_File",
                    "description": "Write content to a named file in the agent workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Name": {
                                "type": "string",
                                "description": "Filename (e.g. script.py)",
                            },
                            "Content": {
                                "type": "string",
                                "description": "The file contents to write",
                            },
                        },
                        "required": ["Name", "Content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "Read_File",
                    "description": "Read content from a named file in the agent workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Name": {
                                "type": "string",
                                "description": "Filename to read",
                            }
                        },
                        "required": ["Name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "Run_Code",
                    "description": "Write Python code to a temp file and execute it in the sandbox. Returns stdout/stderr.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute",
                            },
                            "filename": {
                                "type": "string",
                                "description": "Optional filename to save code as (default: _run_temp.py)",
                            },
                        },
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "Add_Module",
                    "description": "Install a pip module into the sandbox virtual environment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Name": {
                                "type": "string",
                                "description": "PIP package name (e.g. requests)",
                            }
                        },
                        "required": ["Name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "Replace_In_File",
                    "description": "Replace specific content inside an existing file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Name": {"type": "string"},
                            "Target_Content": {
                                "type": "string",
                                "description": "The exact text to find",
                            },
                            "Replacement_Content": {
                                "type": "string",
                                "description": "The text to replace it with",
                            },
                        },
                        "required": ["Name", "Target_Content", "Replacement_Content"],
                    },
                },
            },
        ]

    def _Notify(self):
        if callable(self.On_State_Change):
            try:
                self.On_State_Change()
            except Exception as e:
                print(f"[Agent] Error in On_State_Change callback: {e}")

    async def _Execution_Loop(self):
        self.Hitl_Event = asyncio.Event() 
        while self.Running:
            if (
                not self.Client
                or not self.Api_Key
                or not self.Model
                or len([m for m in self.Messages if m["role"] == "user"]) == 0
            ):
                await asyncio.sleep(2)
                continue

            Last = self.Messages[-1]
            if (
                isinstance(Last, dict)
                and Last.get("role") == "assistant"
                and not Last.get("tool_calls")
            ):
                await asyncio.sleep(2)
                continue

            try:
                self.Is_Thinking = True
                self._Notify()
                Response = await self.Client.chat.completions.create(
                    model=self.Model,
                    messages=self.Messages,
                    tools=self._Get_Tools(),
                    temperature=0.2,
                )
                self.Is_Thinking = False
                self._Notify()

                Message = Response.choices[0].message

                Msg_Dict = Message.model_dump(exclude_unset=True, exclude_none=True)
                if "content" not in Msg_Dict:
                    Msg_Dict["content"] = ""
                self.Messages.append(Msg_Dict)
                self._Notify()

                if Message.tool_calls:
                    for Tool_Call in Message.tool_calls:
                        Func_Name = Tool_Call.function.name
                        try:
                            Args = json.loads(Tool_Call.function.arguments)
                        except json.JSONDecodeError:
                            Args = {}

                        Hitl_Res = await self._Request_Hitl(Func_Name, Args)

                        if Hitl_Res and Hitl_Res.get("approved"):
                            Result = await asyncio.to_thread(
                                self._Execute_Tool, Func_Name, **Args
                            )
                            self.Messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": Tool_Call.id,
                                    "name": Func_Name,
                                    "content": Result,
                                }
                            )
                            self._Notify()
                        else:
                            Reason = (
                                Hitl_Res.get("reason", "Rejected by user")
                                if Hitl_Res
                                else "Rejected"
                            )
                            self.Messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": Tool_Call.id,
                                    "name": Func_Name,
                                    "content": f"Action rejected by user. Reason: {Reason}",
                                }
                            )
                            self._Notify()

            except Exception as e:
                self.Is_Thinking = False
                self._Notify()
                print(f"[Agent] Loop Error: {e}")
                await asyncio.sleep(5)