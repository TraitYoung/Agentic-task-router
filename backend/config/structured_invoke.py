"""结构化 LLM 输出：Moonshot/Kimi 用 JSON 提示 + 解析；千问等走 native 或回退。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from config.llm_settings import llm_base_url
from config.structured_errors import StructuredStepError

logger = logging.getLogger("specforge.structured_invoke")

T = TypeVar("T", bound=BaseModel)

_THINKING_BLOCK_RE = re.compile(
    r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>",
    flags=re.IGNORECASE,
)

_LIST_JSON_HINT = "所有列表字段的元素必须是字符串，禁止使用 {name, responsibility} 等嵌套对象。"


def uses_json_prompt_structured() -> bool:
    import os

    mode = os.getenv("LLM_STRUCTURED_MODE", "").strip().lower()
    base = llm_base_url().lower()
    if mode in ("native", "openai", "dashscope"):
        return False
    if mode in ("json_prompt", "prompt", "moonshot"):
        return True
    if "dashscope" in base:
        return False
    return "moonshot" in base


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


def strip_thinking(text: str) -> str:
    """移除 Kimi 思考块，避免泄漏到用户可见 merge 流式正文。"""
    return _THINKING_BLOCK_RE.sub("", text).strip()


def _strip_thinking(text: str) -> str:
    return strip_thinking(text)


def _balance_json_closers(text: str) -> str:
    """截断 JSON 的轻量兜底：按栈补全未闭合括号（不修复字符串内断点）。"""
    if not text or "{" not in text:
        return text
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in ("}", "]") and stack and stack[-1] == ch:
            stack.pop()
    if in_string:
        text += '"'
    text += "".join(reversed(stack))
    return text


def _extract_json_text(text: str) -> str:
    raw = _strip_thinking((text or "").strip())
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    # 优先：从首个 { 起做括号平衡截取（避免前文说明里的 {} 干扰）
    start = raw.find("{")
    if start >= 0:
        candidate = raw[start:]
        depth = 0
        in_string = False
        escape = False
        end = -1
        for i, ch in enumerate(candidate):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end > 0:
            return candidate[: end + 1]
        return _balance_json_closers(candidate)
    for opener, closer in (("[", "]"),):
        s = raw.find(opener)
        e = raw.rfind(closer)
        if s >= 0 and e > s:
            return raw[s : e + 1]
    return raw


def _list_max_items(field) -> str:
    for meta in field.metadata:
        max_len = getattr(meta, "max_length", None)
        if max_len is not None:
            return f"最多 {max_len} 条"
    return ""


_SCHEMA_EXAMPLES: dict[str, dict[str, object]] = {
    "DevOutline": {
        "modules": ["app-shell: 入口与布局", "db: IndexedDB 封装"],
        "data_flow": "用户操作 → 状态层 → 持久化",
        "risks": ["离线同步冲突"],
        "backlog_mvp_ordered": ["实现首页看板"],
        "backlog_parking_lot": ["多币种"],
        "technical_spikes": ["验证 Dexie 版本迁移"],
    },
    "DevTaskSpec": {
        "goal": "业务目标",
        "constraints": ["约束1"],
        "stack_hint": "TypeScript + React",
        "acceptance_criteria": ["可验收条目"],
        "user_stories": ["As a user I want ..."],
        "mvp_sprint_goal": "本迭代 MVP",
        "measurable_outcomes": ["可观察指标"],
    },
    "DevCodeSketch": {
        "language": "TypeScript",
        "code": "// 代码草稿",
        "notes": "依赖说明",
    },
    "DevTestsChangelog": {
        "test_cases": ["用例1"],
        "changelog_entry": "Added MVP",
        "definition_of_done": ["DoD 条目"],
        "ci_cd_notes": ["CI 说明"],
        "sprint_retrospective_one_liner": "回顾一句",
    },
    "ReverseEngineerSpec": {
        "inferred_goal": "推测的业务目标",
        "inferred_user_stories": ["As a user I want ..."],
        "missing_tests": ["缺少单元测试"],
        "architecture_issues": ["模块耦合"],
        "code_quality_issues": ["魔法数字"],
        "improvement_plan": ["提取配置"],
    },
}


def _compact_schema_hint(model_cls: type[BaseModel]) -> str:
    lines = [
        "请只输出一个 JSON 对象（不要 markdown、不要额外说明）。",
        _LIST_JSON_HINT,
        "各列表不得超过条数上限：",
    ]
    for name, field in model_cls.model_fields.items():
        hint = field.description or str(getattr(field.annotation, "__name__", field.annotation))
        cap = _list_max_items(field)
        suffix = f"（{cap}）" if cap else ""
        lines.append(f"- {name}{suffix}: {hint}")
    example = _SCHEMA_EXAMPLES.get(model_cls.__name__)
    if example:
        lines.append(
            f"\n严格遵循下列 JSON 形状（可替换内容，但结构须一致）：\n"
            f"{json.dumps(example, ensure_ascii=False)}"
        )
    else:
        lines.append(
            f"\n示例结构：{json.dumps({k: '...' for k in model_cls.model_fields}, ensure_ascii=False)}"
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


def _finish_reason(response: Any) -> str:
    meta = getattr(response, "response_metadata", None) or {}
    if isinstance(meta, dict):
        fr = meta.get("finish_reason") or meta.get("stop_reason")
        if fr:
            return str(fr)
    kwargs = getattr(response, "additional_kwargs", None) or {}
    if isinstance(kwargs, dict) and kwargs.get("finish_reason"):
        return str(kwargs["finish_reason"])
    return ""


def _response_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, list):
        content = "".join(
            block.get("text", str(block)) if isinstance(block, dict) else str(block) for block in content
        )
    return _strip_thinking(str(content or response))


def _format_validation_errors(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(x) for x in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', '')}")
    return "; ".join(parts)


def _retry_hint(
    *,
    model_name: str,
    finish_reason: str,
    last_exc: Exception | None,
) -> str:
    if finish_reason == "length" or isinstance(last_exc, json.JSONDecodeError):
        return (
            "上次 JSON 因输出过长被截断。请重新输出更短的完整 JSON："
            "减少列表条数（modules≤8、每条≤60字），省略冗长描述，确保括号闭合。"
        )
    if isinstance(last_exc, ValidationError):
        detail = _format_validation_errors(last_exc)
        return (
            f"上次 JSON 校验失败（{detail}）。请修正后重新输出完整 JSON；"
            f"{_LIST_JSON_HINT}"
        )
    return (
        "上次输出无法解析。请重新输出单一、完整的 JSON 对象；"
        f"{_LIST_JSON_HINT} 控制总篇幅。"
    )


def _invoke_json_prompt(
    llm,
    model_cls: type[T],
    messages: list[BaseMessage],
    *,
    step_id: str = "",
) -> T:
    current = list(messages)
    last_text = ""
    last_exc: Exception | None = None
    last_finish = ""

    for attempt in range(2):
        enhanced = _append_schema_hint(current, model_cls)
        logger.info(
            "structured_invoke: json_prompt model=%s step=%s attempt=%s",
            model_cls.__name__,
            step_id or "-",
            attempt + 1,
        )
        response = llm.invoke(enhanced)
        last_text = _response_text(response)
        last_finish = _finish_reason(response)
        logger.info(
            "structured_invoke: response model=%s chars=%d finish_reason=%s",
            model_cls.__name__,
            len(last_text),
            last_finish or "unknown",
        )
        try:
            payload: Any = json.loads(_extract_json_text(last_text))
            return model_cls.model_validate(payload)
        except json.JSONDecodeError as exc:
            last_exc = exc
            logger.warning(
                "structured_invoke: JSON decode failed %s attempt=%s finish=%s: %s",
                model_cls.__name__,
                attempt + 1,
                last_finish,
                exc,
            )
        except ValidationError as exc:
            last_exc = exc
            logger.warning(
                "structured_invoke: validation failed %s attempt=%s: %s",
                model_cls.__name__,
                attempt + 1,
                _format_validation_errors(exc),
            )

        if attempt == 0:
            current = [
                *messages,
                HumanMessage(
                    content=_retry_hint(
                        model_name=model_cls.__name__,
                        finish_reason=last_finish,
                        last_exc=last_exc,
                    )
                ),
            ]

    logger.error(
        "structured_invoke: failed model=%s step=%s chars=%d finish_reason=%s preview=%s",
        model_cls.__name__,
        step_id or "-",
        len(last_text),
        last_finish or "unknown",
        last_text[:800],
    )
    raise ValueError(
        f"LLM 返回非合法 JSON（{model_cls.__name__}）: {last_text[:500]}"
    ) from last_exc


def invoke_structured(
    llm,
    model_cls: type[T],
    messages: list[BaseMessage],
    *,
    step_id: str = "",
) -> T:
    try:
        if uses_json_prompt_structured():
            return _invoke_json_prompt(llm, model_cls, messages, step_id=step_id)
        try:
            bound = llm.with_structured_output(model_cls)
            return bound.invoke(messages)
        except Exception as exc:
            logger.warning(
                "structured native failed for %s, fallback json_prompt: %s",
                model_cls.__name__,
                exc,
            )
            return _invoke_json_prompt(llm, model_cls, messages, step_id=step_id)
    except Exception as exc:
        if step_id:
            raise StructuredStepError(step_id, model_cls.__name__, exc) from exc
        raise
