from agentq.core.agent.base import BaseAgent
from agentq.core.models.models import VisionInput, VisionOutput
from agentq.core.prompts.prompts import LLM_PROMPTS


class VisionAgent(BaseAgent):
    def __init__(self, client: str = "openai"):
        system_prompt: str = LLM_PROMPTS["VISION_AGENT_PROMPT"]
        self.name = "vision"

        super().__init__(
            name=self.name,
            system_prompt=system_prompt,
            input_format=VisionInput,
            output_format=VisionOutput,
            keep_message_history=False,
            client=client,
        )
