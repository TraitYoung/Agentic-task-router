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


def test_llm_step_model_uses_step_override(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "kimi-k2.6")
    monkeypatch.setenv("LLM_DISCOVERY_MODEL", "kimi-k2.5")
    assert llm_settings.llm_step_model("discovery") == "kimi-k2.5"
    assert llm_settings.llm_step_model("merge") == "kimi-k2.6"
