"""structured_invoke：Moonshot JSON 提示模式与解析。"""

import os
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from config.structured_errors import StructuredStepError
from config.structured_invoke import (
    _balance_json_closers,
    _extract_json_text,
    _strip_thinking,
    invoke_structured,
    prepare_system_content,
    uses_json_prompt_structured,
)
from schemas.workflows import DevTaskSpec


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


def test_balance_json_closers():
    broken = '{"goal": "x", "constraints": ["a"'
    fixed = _balance_json_closers(broken)
    parsed = __import__("json").loads(fixed)
    assert parsed["goal"] == "x"


def test_extract_json_balanced_object():
    raw = '前缀说明 {"goal": "记账", "constraints": []} 后缀'
    assert _extract_json_text(raw) == '{"goal": "记账", "constraints": []}'


class _FakeLLM:
    def __init__(self, responses: list[str], finish_reason: str = "stop"):
        self._responses = responses
        self.calls = 0
        self._finish_reason = finish_reason

    def invoke(self, messages):
        self.calls += 1
        text = self._responses[min(self.calls - 1, len(self._responses) - 1)]
        return SimpleNamespace(
            content=text,
            response_metadata={"finish_reason": self._finish_reason},
        )


def test_invoke_structured_retries_on_invalid_json(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
    monkeypatch.delenv("LLM_STRUCTURED_MODE", raising=False)
    bad = "not valid json {{{"
    good = '{"goal": "完成", "constraints": [], "stack_hint": "", "acceptance_criteria": [], "user_stories": [], "mvp_sprint_goal": "", "measurable_outcomes": []}'
    llm = _FakeLLM([bad, good], finish_reason="length")
    spec = invoke_structured(
        llm,
        DevTaskSpec,
        [SystemMessage(content="test"), HumanMessage(content="hi")],
        step_id="discovery",
    )
    assert spec.goal == "完成"
    assert llm.calls == 2


def test_invoke_structured_wraps_step_error(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
    llm = _FakeLLM(['not json at all', 'still bad'])
    with pytest.raises(StructuredStepError) as ei:
        invoke_structured(
            llm,
            DevTaskSpec,
            [SystemMessage(content="test"), HumanMessage(content="hi")],
            step_id="discovery",
        )
    assert ei.value.step_id == "discovery"
    assert ei.value.model_name == "DevTaskSpec"
