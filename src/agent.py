import asyncio
import json
import time

try:
    from openai import OpenAI
except ImportError:
    pass


class AI_Agent:
    """ """

    def __init__(self, Runner) -> None:
        self.Runner = Runner
        self.Running = False
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
