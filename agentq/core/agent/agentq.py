from datetime import datetime
from string import Template
from typing import Optional

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
        ltm: Optional[str] = None
        ltm = self.__get_ltm()
        system_prompt = self.__modify_system_prompt(ltm)
        self.name = "agentq"

        super().__init__(
            name=self.name,
            system_prompt=system_prompt,
            input_format=AgentQInput,
            output_format=AgentQOutput,
            keep_message_history=False,
            tools=self._get_tools(),
        )

    def __get_ltm(self):
        return ltm.get_user_ltm()

    def __modify_system_prompt(self, ltm):
        system_prompt: str = LLM_PROMPTS["AGENTQ_PROMPT"]

        # Add user ltm to system prompt
        
        if ltm is not None: 
            ltm = "\n" + ltm
            system_prompt = Template(system_prompt).substitute(basic_user_information=ltm)

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
