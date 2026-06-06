import json
import os
from typing import Callable, Dict, List, Literal, Optional, Tuple, Type, get_args

import instructor
import instructor.patch
import litellm
import openai
from instructor import Mode
from langsmith import traceable
from pydantic import BaseModel

from agentq.utils.function_utils import get_function_schema
from agentq.utils.logger import logger

# ── Typed LLM-provider selection seam (Piece 1: DeepSeek wiring) ───────────
# agent-q's LLM client is an OpenAI-API-compatible client wrapped by
# ``instructor`` (Mode.JSON). Provider selection is a single typed seam:
# a ``ProviderKind`` discriminator, a provider→client-factory registry, and
# a provider→default-model map. This keeps all agents source-agnostic (one
# seam, not a ``client=`` threaded through every subclass) and makes provider
# validity / key presence decidable-in-code via ``ProviderConfigError`` rather
# than a silent ``AttributeError`` / bare ``KeyError``.
ProviderKind = Literal["openai", "together", "deepseek"]


class ProviderConfigError(ValueError):
    """Raised when the selected LLM provider is unknown, or its required API
    key is absent. A named, decidable failure — never a bare KeyError or a
    silent fall-through that leaves ``self.client`` unset."""


def _make_openai_client() -> openai.OpenAI:
    return openai.Client()


def _make_together_client() -> openai.OpenAI:
    key = os.environ.get("TOGETHER_API_KEY")
    if not key:
        raise ProviderConfigError(
            "Provider 'together' selected but TOGETHER_API_KEY is not set."
        )
    return openai.OpenAI(base_url="https://api.together.xyz/v1", api_key=key)


def _make_deepseek_client() -> openai.OpenAI:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise ProviderConfigError(
            "Provider 'deepseek' selected but DEEPSEEK_API_KEY is not set."
        )
    return openai.OpenAI(base_url="https://api.deepseek.com/v1", api_key=key)


_PROVIDER_CLIENT_FACTORIES: Dict[ProviderKind, Callable[[], openai.OpenAI]] = {
    "openai": _make_openai_client,
    "together": _make_together_client,
    "deepseek": _make_deepseek_client,
}

_PROVIDER_MODEL_MAP: Dict[ProviderKind, str] = {
    "openai": "gpt-4o-2024-08-06",
    "together": "gpt-4o-2024-08-06",
    "deepseek": "deepseek-chat",
}


class BaseAgent:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        input_format: Type[BaseModel],
        output_format: Type[BaseModel],
        tools: Optional[List[Tuple[Callable, str]]] = None,
        keep_message_history: bool = True,
        client: Optional[ProviderKind] = None,
    ):
        # Metdata
        self.agent_name = name

        # Messages
        self.system_prompt = system_prompt
        # handling the case where agent has to do async intialisation as system prompt depends on some async functions.
        # in those cases, we do init with empty system prompt string and then handle adding system prompt to messages array in the agent itself
        if self.system_prompt:
            self._initialize_messages()
        self.keep_message_history = keep_message_history

        # Input-output format
        self.input_format = input_format
        self.output_format = output_format

        # Set global configurations for litellm
        litellm.logging = True
        litellm.set_verbose = True

        # LLM client — typed, env-driven provider selection at ONE seam.
        # Explicit ``client=`` wins; otherwise read AGENTQ_LLM_PROVIDER (so the
        # zero-arg orchestrated agents all pick up the selected provider).
        provider = (client or os.environ.get("AGENTQ_LLM_PROVIDER", "openai")).strip().lower()
        if provider not in get_args(ProviderKind):
            raise ProviderConfigError(
                f"Unknown LLM provider {provider!r}; "
                f"must be one of {list(get_args(ProviderKind))}."
            )
        self.provider: ProviderKind = provider  # type: ignore[assignment]
        # Registry lookup + named fail-fast (never a silent self.client-unset path).
        self.client = instructor.from_openai(
            _PROVIDER_CLIENT_FACTORIES[provider](), mode=Mode.JSON
        )
        # Provider-bound default model, resolved once from typed state.
        self._default_model: str = _PROVIDER_MODEL_MAP[provider]

        # Tools
        self.tools_list = []
        self.executable_functions_list = {}
        if tools:
            self._initialize_tools(tools)

    def _initialize_tools(self, tools: List[Tuple[Callable, str]]):
        for func, func_desc in tools:
            self.tools_list.append(get_function_schema(func, description=func_desc))
            self.executable_functions_list[func.__name__] = func

    def _initialize_messages(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]

    @traceable(run_type="chain", name="agent_run")
    async def run(
        self,
        input_data: BaseModel,
        screenshot: str = None,
        session_id: str = None,
        # model: str = "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        model: Optional[str] = None,
    ) -> BaseModel:
        # Default to the provider-bound model chosen at construction time
        # (self._default_model); an explicit model= override still wins.
        if model is None:
            model = self._default_model
        if not isinstance(input_data, self.input_format):
            raise ValueError(f"Input data must be of type {self.input_format.__name__}")

        # Handle message history.
        if not self.keep_message_history:
            self._initialize_messages()

        if screenshot:
            self.messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": input_data.model_dump_json(
                                exclude={"current_page_dom", "current_page_url"}
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": screenshot}},
                    ],
                }
            )
        else:
            self.messages.append(
                {
                    "role": "user",
                    "content": input_data.model_dump_json(
                        exclude={"current_page_dom", "current_page_url"}
                    ),
                }
            )

        # input dom and current page url in a separate message so that the LLM can pay attention to completed tasks better. *based on personal vibe check*
        if hasattr(input_data, "current_page_dom") and hasattr(
            input_data, "current_page_url"
        ):
            self.messages.append(
                {
                    "role": "user",
                    "content": f"Current page URL:\n{input_data.current_page_url}\n\n Current page DOM:\n{input_data.current_page_dom}",
                }
            )

        # logger.info(self.messages)

        # TODO: add a max_turn here to prevent a inifinite fallout
        while True:
            # TODO:
            # 1. exeception handling while calling the client
            # 2. remove the else block as JSON mode in instrutor won't allow us to pass in tools.
            if len(self.tools_list) == 0:
                response = self.client.chat.completions.create(
                    model=model,
                    # model="gpt-4o-2024-08-06",
                    # model="gpt-4o-mini",
                    # model="groq/llama3-groq-70b-8192-tool-use-preview",
                    # model="xlam-1b-fc-r",
                    messages=self.messages,
                    response_model=self.output_format,
                    max_retries=4,
                )
            else:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=self.messages,
                    response_model=self.output_format,
                    tool_choice="auto",
                    tools=self.tools_list,
                )

            # instructor directly outputs response.choices[0].message. so we will do response_message = response
            # response_message = response.choices[0].message

            # instructor does not support funciton in JSON mode
            # if response_message.tool_calls:
            #     tool_calls = response_message.tool_calls

            # if tool_calls:
            #     self.messages.append(response_message)
            #     for tool_call in tool_calls:
            #         await self._append_tool_response(tool_call)
            #     continue

            # parsed_response_content: self.output_format = response_message.parsed

            try:
                assert isinstance(response, self.output_format)
            except AssertionError:
                raise TypeError(
                    f"Expected response_message to be of type {self.output_format.__name__}, but got {type(response).__name__}"
                )
            return response

    async def _append_tool_response(self, tool_call):
        function_name = tool_call.function.name
        function_to_call = self.executable_functions_list[function_name]
        function_args = json.loads(tool_call.function.arguments)
        try:
            function_response = await function_to_call(**function_args)
            # print(function_response)
            self.messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": str(function_response),
                }
            )
        except Exception as e:
            logger.error(f"Error occurred calling the tool {function_name}: {str(e)}")
            self.messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": str(
                        "The tool responded with an error, please try again with a different tool or modify the parameters of the tool",
                        function_response,
                    ),
                }
            )
