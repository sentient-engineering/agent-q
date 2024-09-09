from agentq.core.agent.base import BaseAgent
from agentq.core.models.models import CaptchaAgentInput, CaptchaAgentOutput
from agentq.core.prompts.prompts import LLM_PROMPTS


class CaptchaAgent(BaseAgent):
    def __init__(self):
        self.name = "captcha_solver"
        super().__init__(
            name=self.name,
            system_prompt=LLM_PROMPTS["CAPTCHA_AGENT_PROMPT"],
            input_format=CaptchaAgentInput,
            output_format=CaptchaAgentOutput,
            keep_message_history=False,
        )
