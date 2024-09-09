from agentq.core.agent.base import BaseAgent
from agentq.core.models.models import BrowserNavInput, BrowserNavOutput
from agentq.core.prompts.prompts import LLM_PROMPTS
from agentq.core.skills.click_using_selector import click as click_element
from agentq.core.skills.enter_text_and_click import enter_text_and_click
from agentq.core.skills.enter_text_using_selector import bulk_enter_text, entertext
from agentq.core.skills.get_dom_with_content_type import get_dom_with_content_type
from agentq.core.skills.get_url import geturl
from agentq.core.skills.open_url import openurl
from agentq.core.skills.pdf_text_extractor import extract_text_from_pdf
from agentq.core.skills.press_key_combination import press_key_combination
from agentq.core.skills.solve_captcha import solve_captcha
from agentq.core.skills.upload_file import upload_file


class BrowserNavAgent(BaseAgent):
    def __init__(self):
        self.name = "executor"

        super().__init__(
            name=self.name,
            system_prompt=LLM_PROMPTS["BROWSER_AGENT_PROMPT"],
            input_format=BrowserNavInput,
            output_format=BrowserNavOutput,
            keep_message_history=False,
            tools=self._get_tools(),
        )

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
            (solve_captcha, LLM_PROMPTS["SOLVE_CAPTCHA_PROMPT"]),
        ]
