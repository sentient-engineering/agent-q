"""Piece-1: DeepSeek provider wiring (Option A') — RED→GREEN contract.

Tests the TYPED provider-selection seam in BaseAgent: env-driven selection,
the deepseek client factory, the provider→model binding, and the named
ProviderConfigError fail-fast (unknown provider / missing key). No network:
client construction (openai.OpenAI(base_url=..., api_key=...)) is offline.
"""
import pytest

from agentq.core.agent.base import (
    BaseAgent,
    ProviderConfigError,
    _PROVIDER_CLIENT_FACTORIES,
    _PROVIDER_MODEL_MAP,
)
from agentq.core.models.models import AgentQActorInput, AgentQActorOutput
from agentq.core.agent.vision_agent import VisionAgent


def _agent(**kwargs):
    return BaseAgent(
        name="t",
        system_prompt="",
        input_format=AgentQActorInput,
        output_format=AgentQActorOutput,
        **kwargs,
    )


def test_deepseek_factory_targets_deepseek_base_url(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    client = _PROVIDER_CLIENT_FACTORIES["deepseek"]()
    assert str(client.base_url).startswith("https://api.deepseek.com")


def test_provider_model_map_deepseek_is_deepseek_chat():
    assert _PROVIDER_MODEL_MAP["deepseek"] == "deepseek-chat"


def test_env_selection_routes_zero_arg_agent_to_deepseek(monkeypatch):
    monkeypatch.setenv("AGENTQ_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    a = _agent()  # zero provider arg — picks up the env seam
    assert a.provider == "deepseek"
    assert a._default_model == "deepseek-chat"


def test_missing_deepseek_key_raises_provider_config_error(monkeypatch):
    monkeypatch.setenv("AGENTQ_LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ProviderConfigError):
        _agent()


def test_unknown_provider_raises_provider_config_error_not_attribute_error(monkeypatch):
    monkeypatch.delenv("AGENTQ_LLM_PROVIDER", raising=False)
    with pytest.raises(ProviderConfigError):
        _agent(client="anthropic")


def test_case_typo_provider_normalized_then_validated(monkeypatch):
    # "DeepSeek" lowercases to "deepseek" (valid); a real typo still raises.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    a = _agent(client="DeepSeek")
    assert a.provider == "deepseek"
    with pytest.raises(ProviderConfigError):
        _agent(client="deepsek")  # genuine typo


def test_openai_default_preserved_regression(monkeypatch):
    monkeypatch.delenv("AGENTQ_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    a = _agent()
    assert a.provider == "openai"
    assert a._default_model == "gpt-4o-2024-08-06"


def test_vision_agent_stays_openai_under_deepseek_env_scope_boundary(monkeypatch):
    """Piece-1 SCOPE BOUNDARY (per code review): VisionAgent pins its own
    ``client="openai"`` default (vision_agent.py:7), so it intentionally does
    NOT pick up AGENTQ_LLM_PROVIDER. This is correct for Piece-1 — vision's
    model is also hardcoded (browser_mcts.py), so migrating only its client
    would send gpt-4o to DeepSeek. Vision's DeepSeek migration is Piece-3.
    The no-tools agents (planner/actor/critic) forward no ``client=`` and DO
    pick up the env seam (proven by the real-path acceptance test)."""
    monkeypatch.setenv("AGENTQ_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "dummy-key")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key")
    v = VisionAgent()  # zero-arg — but its own default pins client="openai"
    assert v.provider == "openai"
    assert v._default_model == "gpt-4o-2024-08-06"
