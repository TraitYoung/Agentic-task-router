"""structured_invoke：Moonshot JSON 提示模式与解析。"""

import os

import pytest
from langchain_core.messages import SystemMessage

from config.structured_invoke import (
    _extract_json_text,
    _strip_thinking,
    prepare_system_content,
    uses_json_prompt_structured,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("LLM_", "QWEN_")):
            monkeypatch.delenv(key, raising=False)


def test_uses_json_prompt_for_moonshot_base(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
    assert uses_json_prompt_structured() is True


def test_uses_native_for_dashscope(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    assert uses_json_prompt_structured() is False


def test_prepare_system_adds_json_hint_for_dashscope(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    out = prepare_system_content("你是需求教练。")
    assert "json" in out.lower()


def test_prepare_system_skips_duplicate_hint_for_moonshot(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
    base = "你是需求教练。"
    assert prepare_system_content(base) == base


def test_extract_json_from_fence():
    raw = '说明\n```json\n{"goal": "记账"}\n```'
    assert _extract_json_text(raw) == '{"goal": "记账"}'


def test_strip_thinking_before_json():
    raw = '推理中\n{"goal": "记账"}'
    assert _extract_json_text(raw) == '{"goal": "记账"}'


def test_strip_thinking_helper():
    assert _strip_thinking("<thinking>a</thinking>\nhi") == "hi"
