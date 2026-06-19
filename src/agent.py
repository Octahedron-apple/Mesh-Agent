import asyncio
import json
import time
import threading

try:
    from openai import OpenAI
except ImportError:
    pass

hitl_event = threading.Event()
pending_action = None
hitl_response = None

class AI_Agent:
    """ """

    def __init__(self, Runner) -> None:
        self.Runner = Runner
        self.Running = False
        self.Thread = None
        self.Api_Key = ""
        self.Model = ""
        self.System_Prompt = "You Are an AI Agent. You have access to an python Sandbox. Use the tools provided to you to fullfill the request of the user."
        self.Messages = [{"role": "system", "content": self.System_Prompt}]

    def Set_Config(self, Api_key, Model):
        """ """
        self.Api_Key = Api_key
        self.Model = Model

    def Add_User_Message(self, text):
        """ """
        self.Messages.append({"role": "user", "content": text})

    def Start(self):
        if not self.Running:
            self.Running = True
            self.Thread = threading.Thread(target=self._Execution_Loop, daemon=True)
            self.Thread.start()

    def Stop(self):
        self.Running = False

    def _Auto_Commit(self, Action_Name):
        if Action_Name in ["Write_File", "Delete_File", "Replace_In_File"]:
            if hasattr(self.Runner, "Commit"):
                try:
                    self.Runner.Commit(f"Pre-action backup before {Action_Name}")
                except Exception:
                    pass

    def _Request_Hitl(self, Tool_Name, Kwargs):
        global pending_action, hitl_event, hitl_response
        
        pending_action = {
            "tool": Tool_Name,
            "args": Kwargs
        }
        
        hitl_event.clear()
        hitl_event.wait()
        
        Response = hitl_response
        pending_action = None
        hitl_response = None
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
                return str(Func(**Kwargs))
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
                            "Name": {"type": "string", "description": "Filename (e.g. script.py)"},
                            "Content": {"type": "string", "description": "The file contents to write"}
                        },
                        "required": ["Name", "Content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "Read_File",
                    "description": "Read content from a named file in the agent workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Name": {"type": "string", "description": "Filename to read"}
                        },
                        "required": ["Name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "Run_Code",
                    "description": "Write Python code to a temp file and execute it in the sandbox. Returns stdout/stderr.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Python code to execute"},
                            "filename": {"type": "string", "description": "Optional filename to save code as (default: _run_temp.py)"}
                        },
                        "required": ["code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "Add_Module",
                    "description": "Install a pip module into the sandbox virtual environment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "Name": {"type": "string", "description": "PIP package name (e.g. requests)"}
                        },
                        "required": ["Name"]
                    }
                }
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
                            "Target_Content": {"type": "string", "description": "The exact text to find"},
                            "Replacement_Content": {"type": "string", "description": "The text to replace it with"}
                        },
                        "required": ["Name", "Target_Content", "Replacement_Content"]
                    }
                }
            }
        ]

    def _Execution_Loop(self):
        while self.Running:
            if not self.Api_Key or not self.Model or len([m for m in self.Messages if m["role"] == "user"]) == 0:
                time.sleep(2)
                continue
            
            Last = self.Messages[-1]
            if isinstance(Last, dict) and Last.get("role") == "assistant" and not Last.get("tool_calls"):
                time.sleep(2)
                continue

            try:
                Client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.Api_Key
                )

                Response = Client.chat.completions.create(
                    model=self.Model,
                    messages=self.Messages,
                    tools=self._Get_Tools(),
                    temperature=0.2
                )
                
                Message = Response.choices[0].message
                
                Msg_Dict = Message.model_dump(exclude_unset=False)
                self.Messages.append(Msg_Dict)
                
                if Message.tool_calls:
                    for Tool_Call in Message.tool_calls:
                        Func_Name = Tool_Call.function.name
                        try:
                            Args = json.loads(Tool_Call.function.arguments)
                        except json.JSONDecodeError:
                            Args = {}
                        
                        Hitl_Res = self._Request_Hitl(Func_Name, Args)
                        
                        if Hitl_Res and Hitl_Res.get("approved"):
                            Result = self._Execute_Tool(Func_Name, **Args)
                            self.Messages.append({
                                "role": "tool",
                                "tool_call_id": Tool_Call.id,
                                "name": Func_Name,
                                "content": Result
                            })
                        else:
                            Reason = Hitl_Res.get("reason", "Rejected by user") if Hitl_Res else "Rejected"
                            self.Messages.append({
                                "role": "tool",
                                "tool_call_id": Tool_Call.id,
                                "name": Func_Name,
                                "content": f"Action rejected by user. Reason: {Reason}"
                            })

            except Exception:
                time.sleep(5)
