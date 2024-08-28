from datetime import datetime
from string import Template

from agentq.core.agent.base import BaseAgent
from agentq.core.memory import ltm
from agentq.core.models.models import AgentQInput, AgentQOutput
from agentq.core.prompts.prompts import LLM_PROMPTS
from agentq.core.skills.click_using_selector import click as click_element
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.enter_text_using_selector import bulk_enter_text, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl
from agentq.core.skills.pdf_text_extractor import extract_text_from_pdf
from agentq.core.skills.press_key_combination import press_key_combination
from agentq.core.skills.upload_file import upload_file


class AgentQ(BaseAgent):
    def __init__(self):
        self.name = "agentq"
        self.ltm = None
        self.dom = None
        self.system_prompt = None
        super().__init__(
            name=self.name,
            system_prompt="",
            input_format=AgentQInput,
            output_format=AgentQOutput,
            keep_message_history=False,
            tools=self._get_tools(),
        )

    async def initialize(self):
        self.ltm = self.__get_ltm()
        self.dom = await self.__get_dom()
        self.system_prompt = self.__modify_system_prompt(self.ltm, self.dom)
        self.messages = [{"role": "system", "content": self.system_prompt}]

    @classmethod
    async def create(cls):
        ltm = cls.__get_ltm()
        dom = await cls.__get_dom()
        system_prompt = cls.__modify_system_prompt(ltm, dom)
        return cls(system_prompt)

    @staticmethod
    def __get_ltm():
        return ltm.get_user_ltm()

    @staticmethod
    async def __get_dom():
        return await get_dom_with_content_type(content_type="all_fields")

    def __modify_system_prompt(self, ltm, dom):
        system_prompt: str = LLM_PROMPTS["AGENTQ_PROMPT"]

        substitutions = {
            "basic_user_information": ltm if ltm is not None else "",
            "dom_content": str(dom) if dom is not None else "",
        }

        # Use safe_substitute to avoid KeyError
        system_prompt = Template(system_prompt).safe_substitute(substitutions)

        # Add today's day & date to the system prompt
        today = datetime.now()
        today_date = today.strftime("%d/%m/%Y")
        weekday = today.strftime("%A")
        system_prompt += f"\nToday's date is: {today_date}"
        system_prompt += f"\nCurrent weekday is: {weekday}"

        return system_prompt

    def _get_tools(self):
        return [
            (openurl, LLM_PROMPTS["OPEN_URL_PROMPT"]),
            (enter_text_and_click, LLM_PROMPTS["ENTER_TEXT_AND_CLICK_PROMPT"]),
            (
                get_dom_with_content_type,
                LLM_PROMPTS["GET_DOM_WITH_CONTENT_TYPE_PROMPT"],
            ),
            (click_element, LLM_PROMPTS["CLICK_PROMPT"]),
            (geturl, LLM_PROMPTS["GET_URL_PROMPT"]),
            (bulk_enter_text, LLM_PROMPTS["BULK_ENTER_TEXT_PROMPT"]),
            (entertext, LLM_PROMPTS["ENTER_TEXT_PROMPT"]),
            (press_key_combination, LLM_PROMPTS["PRESS_KEY_COMBINATION_PROMPT"]),
            (extract_text_from_pdf, LLM_PROMPTS["EXTRACT_TEXT_FROM_PDF_PROMPT"]),
            (upload_file, LLM_PROMPTS["UPLOAD_FILE_PROMPT"]),
        ]
