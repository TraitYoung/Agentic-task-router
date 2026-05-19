"""LLM 环境变量解析与向后兼容。"""

import os

import pytest

from config import llm_settings


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("LLM_", "QWEN_", "AX_LLM_")):
            monkeypatch.delenv(key, raising=False)


def test_llm_api_key_prefers_llm_prefix(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "legacy")
    monkeypatch.setenv("LLM_API_KEY", "primary")
    assert llm_settings.llm_api_key() == "primary"


def test_llm_api_key_falls_back_to_qwen(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "legacy-only")
    assert llm_settings.llm_api_key() == "legacy-only"


def test_llm_defaults_to_kimi_moonshot(monkeypatch):
    assert llm_settings.llm_base_url() == "https://api.moonshot.cn/v1"
    assert llm_settings.llm_default_model() == "kimi-k2.6"
    assert llm_settings.llm_request_timeout() == 300


def test_llm_step_model_uses_step_override(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "kimi-k2.6")
    monkeypatch.setenv("LLM_DISCOVERY_MODEL", "kimi-k2.5")
    assert llm_settings.llm_step_model("discovery") == "kimi-k2.5"
    assert llm_settings.llm_step_model("merge") == "kimi-k2.6"


def test_llm_max_tokens_per_step(monkeypatch):
    assert llm_settings.llm_max_tokens("discovery") == 4096
    assert llm_settings.llm_max_tokens("merge") == 16384
    monkeypatch.setenv("LLM_MAX_TOKENS", "2048")
    assert llm_settings.llm_max_tokens("unknown_step") == 2048


def test_llm_thinking_disabled_via_env(monkeypatch):
    monkeypatch.setenv("LLM_THINKING", "disabled")
    kwargs = llm_settings.llm_model_kwargs()
    assert kwargs["extra_body"]["thinking"]["type"] == "disabled"


def test_llm_thinking_default_empty_kwargs(monkeypatch):
    assert llm_settings.llm_thinking_mode() == "default"
    assert llm_settings.llm_model_kwargs() == {}


def test_llm_env_health_fields(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    health = llm_settings.llm_env_health()
    assert health["has_llm_key"] is True
    assert health["llm_provider"] == "moonshot"
    assert health["llm_thinking"] == "default"
