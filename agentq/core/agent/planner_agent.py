from datetime import datetime
from string import Template
from typing import Optional

from agentq.core.agent.base import BaseAgent
from agentq.core.memory import ltm
from agentq.core.models.models import PlannerInput, PlannerOutput
from agentq.core.prompts.prompts import LLM_PROMPTS


class PlannerAgent(BaseAgent):
    def __init__(self):
        ltm: Optional[str] = None
        ltm = self.__get_ltm()
        system_prompt = self.__modify_system_prompt(ltm)
        self.name = "planner"

        super().__init__(
            name=self.name,
            system_prompt=system_prompt,
            input_format=PlannerInput,
            output_format=PlannerOutput,
            keep_message_history=False,
        )

    def __get_ltm(self):
        return ltm.get_user_ltm()

    def __modify_system_prompt(self, ltm):
        system_prompt: str = LLM_PROMPTS["PLANNER_AGENT_PROMPT"]

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
