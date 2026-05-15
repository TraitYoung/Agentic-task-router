"""
上下文预算控制：集中管理 Token 成本，工作流步骤间传递 JSON 摘要。
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


# 工作流：首包用户原文进入解析的上限
WORKFLOW_USER_TEXT_MAX_CHARS = _env_int("AX_WORKFLOW_USER_MAX_CHARS", 8000)

# 工作流：步骤间传递的 JSON 摘要硬上限（避免下一步 prompt 膨胀）
WORKFLOW_STEP_JSON_MAX_CHARS = _env_int("AX_WORKFLOW_STEP_JSON_MAX_CHARS", 2500)


def clip_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
