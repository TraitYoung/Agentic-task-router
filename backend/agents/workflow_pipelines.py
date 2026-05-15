"""工作流入口：统一对外导出 dev_pipeline 与 reverse_engineer 两条能力线。"""

from __future__ import annotations

from typing import Any

from config.context_budget import clip_text
from agents.dev_pipeline.orchestrator import run_dev_pipeline, run_reverse_engineer


def synthetic_intent_for_workflow(raw_input: str) -> Any:
    from schemas.protocols import TaskIntent

    clip = clip_text(raw_input.strip(), 12000)
    return TaskIntent(
        task_type="dev_pipeline",
        urgency_level=2,
        pain_level=1,
        raw_input=clip or ".",
        quadrant="Q4",
    )
