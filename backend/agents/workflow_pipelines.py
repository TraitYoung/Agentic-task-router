"""工作流入口：统一对外导出 dev_pipeline 与 reverse_engineer 两条能力线。"""

from __future__ import annotations

from typing import Any

from agents.dev_pipeline.orchestrator import run_dev_pipeline, run_reverse_engineer


def synthetic_intent_for_workflow(raw_input: str) -> Any:
    """兼容占位：返回固定的 TaskIntent。当前 specForge 的 spec/review 模式由 API 层
    ChatRequest.mode 字段直接路由，不依赖意图分类。保留此函数以维持下游兼容性。"""
    from schemas.protocols import TaskIntent

    return TaskIntent(
        task_type="dev_pipeline",
        urgency_level=2,
        pain_level=1,
        raw_input=raw_input.strip()[:200] or ".",
        quadrant="Q4",
    )
