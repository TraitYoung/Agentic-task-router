"""
上下文与材料长度预算：集中管理，便于调参与「省 Token」叙事对齐。
可通过环境变量覆盖（整数）。
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


# Parser：会话历史写入 prompt 的总字符上限（多轮拼接后整体截断）
MAX_PARSER_HISTORY_CHARS = _env_int("AX_PARSER_HISTORY_MAX_CHARS", 3500)

# 单轮 history 行（User+Assistant）在拼进 parser 前的单行软上限
MAX_SINGLE_HISTORY_LINE_CHARS = _env_int("AX_PARSER_HISTORY_LINE_MAX_CHARS", 1200)

# Jean：RAG 材料块进入 LLM 前的上限（原硬编码 2000）
JEAN_MATERIALS_MAX_CHARS = _env_int("AX_JEAN_MATERIALS_MAX_CHARS", 2000)

# 工作流：首包用户原文进入 spec/JD 解析的上限
WORKFLOW_USER_TEXT_MAX_CHARS = _env_int("AX_WORKFLOW_USER_MAX_CHARS", 8000)

# 工作流：步骤间传递的 JSON 摘要硬上限（避免下一步 prompt 膨胀）
WORKFLOW_STEP_JSON_MAX_CHARS = _env_int("AX_WORKFLOW_STEP_JSON_MAX_CHARS", 2500)


def clip_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def truncate_history_lines(lines: list[str]) -> list[str]:
    """逐行截断后再整体截断，供 parser 使用。"""
    trimmed: list[str] = []
    for line in lines:
        trimmed.append(clip_text(line, MAX_SINGLE_HISTORY_LINE_CHARS))
    joined = "\n".join(trimmed)
    if len(joined) <= MAX_PARSER_HISTORY_CHARS:
        return trimmed
    # 整体过长：从最新一轮开始往前保留（列表最后一项是最新？format_recent_history 是旧到新）
    acc: list[str] = []
    total = 0
    for line in reversed(trimmed):
        add = len(line) + (1 if acc else 0)
        if total + add > MAX_PARSER_HISTORY_CHARS:
            break
        acc.append(line)
        total += add
    return list(reversed(acc))
