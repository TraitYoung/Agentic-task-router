"""工作流入口兼容层：保留旧 import 路径，委托到新版 dev_pipeline orchestrator。"""

from __future__ import annotations

from typing import Any

from config.context_budget import clip_text
from agents.dev_pipeline.orchestrator import run_dev_pipeline


def synthetic_intent_for_workflow(
    raw_input: str,
    *,
    task_type: str = "bit",
) -> Any:
    """生成合法 TaskIntent，供 ChatResponse 与前端兼容。"""
    from typing import Literal, cast

    from schemas.protocols import TaskIntent

    clip = clip_text(raw_input.strip(), 12000)
    tt = cast(Literal["emotion", "jean", "bit", "juzheng", "unknown"], task_type)
    return TaskIntent(
        task_type=tt,
        urgency_level=2,
        pain_level=1,
        raw_input=clip or ".",
        quadrant="Q3",
    )

