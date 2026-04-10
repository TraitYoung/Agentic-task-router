"""
内阁（Cabinet）：可热插拔的多 Agent 路由模块。

- 图与节点：`agents.cabinet.graph`
- 默认执行器：`agents.cabinet.runner.run_cabinet_turn`
- 解析注册：`agents.cabinet.registry.get_cabinet_runner`
"""

from agents.cabinet.graph import (
    MAIN_THREAD_ID,
    GraphState,
    app,
    llm,
    memory_db,
    route_by_intent,
)
from agents.cabinet.registry import get_cabinet_runner, reset_cabinet_runner_cache_for_tests
from agents.cabinet.runner import run_cabinet_turn

__all__ = [
    "MAIN_THREAD_ID",
    "GraphState",
    "app",
    "llm",
    "memory_db",
    "route_by_intent",
    "get_cabinet_runner",
    "reset_cabinet_runner_cache_for_tests",
    "run_cabinet_turn",
]
