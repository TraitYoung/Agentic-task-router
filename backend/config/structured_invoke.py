"""结构化 LLM 输出：Moonshot/Kimi 用 JSON 提示 + 解析；千问等走 native 或回退。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage, SystemMessage
from pydantic import BaseModel

from config.llm_settings import llm_base_url

logger = logging.getLogger("specforge.structured_invoke")

T = TypeVar("T", bound=BaseModel)

_THINKING_BLOCK_RE = re.compile(
    r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>",
    flags=re.IGNORECASE,
)


def uses_json_prompt_structured() -> bool:
    import os

    mode = os.getenv("LLM_STRUCTURED_MODE", "").strip().lower()
    if mode in ("json_prompt", "prompt", "moonshot"):
        return True
    if mode in ("native", "openai", "dashscope"):
        return False
    return "moonshot" in llm_base_url().lower()


def prepare_system_content(system_content: str) -> str:
    """native 模式需含 json 字样（千问 json_object）；json_prompt 模式由 schema 提示覆盖。"""
    if uses_json_prompt_structured():
        return system_content.rstrip()
    if "json" in system_content.lower():
        return system_content.rstrip()
    return (
        f"{system_content.rstrip()}\n\n"
        "请仅以 JSON 对象格式返回结果，字段须与 schema 一致；不要输出 markdown 代码块或额外说明。"
    )


def _strip_thinking(text: str) -> str:
    return _THINKING_BLOCK_RE.sub("", text).strip()


def _extract_json_text(text: str) -> str:
    raw = _strip_thinking((text or "").strip())
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start >= 0 and end > start:
            return raw[start : end + 1]
    return raw


def _compact_schema_hint(model_cls: type[BaseModel]) -> str:
    lines = [f"请只输出一个 JSON 对象，须包含下列字段（不要 markdown、不要额外说明）："]
    for name, field in model_cls.model_fields.items():
        hint = field.description or str(getattr(field.annotation, "__name__", field.annotation))
        lines.append(f"- {name}: {hint}")
    lines.append(
        f"\n示例结构（值由你填写）：{json.dumps({k: '...' for k in model_cls.model_fields}, ensure_ascii=False)}"
    )
    return "\n".join(lines)


def _append_schema_hint(messages: list[BaseMessage], model_cls: type[T]) -> list[BaseMessage]:
    schema_hint = f"\n\n{_compact_schema_hint(model_cls)}"
    out: list[BaseMessage] = []
    for i, msg in enumerate(messages):
        if i == 0 and isinstance(msg, SystemMessage):
            out.append(SystemMessage(content=str(msg.content) + schema_hint))
        else:
            out.append(msg)
    if not out or not isinstance(out[0], SystemMessage):
        out.insert(0, SystemMessage(content=schema_hint.lstrip()))
    return out


def _invoke_json_prompt(llm, model_cls: type[T], messages: list[BaseMessage]) -> T:
    enhanced = _append_schema_hint(messages, model_cls)
    logger.info("structured_invoke: json_prompt model=%s", model_cls.__name__)
    response = llm.invoke(enhanced)
    content = getattr(response, "content", None)
    if isinstance(content, list):
        content = "".join(
            block.get("text", str(block)) if isinstance(block, dict) else str(block) for block in content
        )
    text = _strip_thinking(str(content or response))
    try:
        payload: Any = json.loads(_extract_json_text(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 返回非合法 JSON（{model_cls.__name__}）: {text[:500]}") from exc
    return model_cls.model_validate(payload)


def invoke_structured(llm, model_cls: type[T], messages: list[BaseMessage]) -> T:
    if uses_json_prompt_structured():
        return _invoke_json_prompt(llm, model_cls, messages)

    try:
        bound = llm.with_structured_output(model_cls)
        return bound.invoke(messages)
    except Exception as exc:
        logger.warning(
            "structured native failed for %s, fallback json_prompt: %s",
            model_cls.__name__,
            exc,
        )
        return _invoke_json_prompt(llm, model_cls, messages)
