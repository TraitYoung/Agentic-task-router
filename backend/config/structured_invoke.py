"""结构化 LLM 输出：Moonshot/Kimi 不支持 response_format 时用 JSON 提示 + 解析。"""

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


def uses_json_prompt_structured() -> bool:
    import os

    mode = os.getenv("LLM_STRUCTURED_MODE", "").strip().lower()
    if mode in ("json_prompt", "prompt", "moonshot"):
        return True
    if mode in ("native", "openai", "dashscope"):
        return False
    return "moonshot" in llm_base_url().lower()


def _extract_json_text(text: str) -> str:
    raw = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start : end + 1]
    return raw


def _append_schema_hint(messages: list[BaseMessage], model_cls: type[T]) -> list[BaseMessage]:
    schema_hint = (
        "\n\n请只输出一个 JSON 对象（不要 markdown 代码块、不要额外说明），"
        f"字段须符合下列 JSON Schema：\n{json.dumps(model_cls.model_json_schema(), ensure_ascii=False)}"
    )
    out: list[BaseMessage] = []
    for i, msg in enumerate(messages):
        if i == 0 and isinstance(msg, SystemMessage):
            out.append(SystemMessage(content=str(msg.content) + schema_hint))
        else:
            out.append(msg)
    if not out or not isinstance(out[0], SystemMessage):
        out.insert(0, SystemMessage(content=schema_hint.lstrip()))
    return out


def invoke_structured(llm, model_cls: type[T], messages: list[BaseMessage]) -> T:
    if not uses_json_prompt_structured():
        bound = llm.with_structured_output(model_cls)
        return bound.invoke(messages)

    enhanced = _append_schema_hint(messages, model_cls)
    logger.info("structured_invoke: json_prompt mode model=%s", model_cls.__name__)
    response = llm.invoke(enhanced)
    content = getattr(response, "content", None) or str(response)
    try:
        payload: Any = json.loads(_extract_json_text(str(content)))
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM 返回非合法 JSON（{model_cls.__name__}）: {content[:500]}") from exc
    return model_cls.model_validate(payload)
