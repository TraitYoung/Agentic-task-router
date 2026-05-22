"""
上下文预算控制：集中管理 Token 成本，工作流步骤间传递 JSON 摘要。
可通过环境变量覆盖（整数）。
"""

from __future__ import annotations

from config.settings import get_settings

WORKFLOW_USER_TEXT_MAX_CHARS = get_settings().ax_workflow_user_max_chars
WORKFLOW_STEP_JSON_MAX_CHARS = get_settings().ax_workflow_step_json_max_chars


def clip_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
