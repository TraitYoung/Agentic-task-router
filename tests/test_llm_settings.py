"""LLM 环境变量解析与向后兼容 — 直接测试 Settings。"""

import os

import pytest

from config.settings import Settings


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("LLM_", "QWEN_", "AX_LLM_")):
            monkeypatch.delenv(key, raising=False)


def test_llm_api_key_prefers_llm_prefix(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "legacy")
    monkeypatch.setenv("LLM_API_KEY", "primary")
    assert Settings().llm_api_key == "primary"


def test_llm_api_key_falls_back_to_qwen(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "legacy-only")
    assert Settings().llm_api_key == "legacy-only"


def test_llm_defaults_to_deepseek(monkeypatch):
    assert Settings().llm_base_url == "https://api.deepseek.com/v1"
    assert Settings().llm_model == "deepseek-v4-pro"
    assert Settings().llm_request_timeout == 300
    assert Settings().uses_json_prompt_structured() is False
    assert Settings().reasoning_effort() == "max"


def test_llm_step_model_uses_step_override(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("LLM_DISCOVERY_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("LLM_MERGE_MODEL", "deepseek-v4-flash")
    assert Settings().step_model("discovery") == "deepseek-v4-pro"
    assert Settings().step_model("merge") == "deepseek-v4-flash"


def test_llm_max_tokens_per_step(monkeypatch):
    assert Settings().step_max_tokens("discovery") == 8192
    assert Settings().step_max_tokens("merge") == 16384
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
    assert Settings().step_max_tokens("unknown_step") == 2048


def test_llm_structured_thinking_override(monkeypatch):
    monkeypatch.setenv("LLM_THINKING", "default")
    monkeypatch.setenv("LLM_STRUCTURED_THINKING", "disabled")
    kwargs = Settings().structured_model_kwargs()
    assert kwargs["extra_body"]["thinking"]["type"] == "disabled"
    health = Settings().llm_env_health()
    assert health["llm_structured_thinking"] == "disabled"


def test_llm_thinking_disabled_via_env(monkeypatch):
    monkeypatch.setenv("LLM_THINKING", "disabled")
    kwargs = Settings().model_kwargs()
    assert kwargs["extra_body"]["thinking"]["type"] == "disabled"


def test_llm_thinking_enabled_max_effort(monkeypatch):
    kwargs = Settings().model_kwargs()
    assert kwargs["extra_body"]["thinking"]["type"] == "enabled"
    assert kwargs["reasoning_effort"] == "max"
    health = Settings().llm_env_health()
    assert health["llm_thinking"] == "enabled"
    assert health["llm_reasoning_effort"] == "max"


def test_llm_thinking_default_empty_kwargs(monkeypatch):
    assert Settings().thinking_mode() == "enabled"
    assert Settings().model_kwargs()["reasoning_effort"] == "max"


def test_llm_env_health_fields(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    health = Settings().llm_env_health()
    assert health["has_llm_key"] is True
    assert health["llm_provider"] == "deepseek"
    assert health["llm_thinking"] == "enabled"
