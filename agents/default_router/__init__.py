"""
默认路由（Default Router）：软件工程教学/测试取向的可热插拔路由模块。

- 图与节点：`agents.default_router.graph`
- 默认执行器：`agents.default_router.runner.run_default_router_turn`
- 注册入口：`agents.default_router.registry.get_default_router_runner`

兼容说明：当前实现复用 `agents.cabinet` 内核，后续可逐步迁移实现细节。
"""

from agents.default_router.graph import (
    MAIN_THREAD_ID,
    GraphState,
    app,
    llm,
    memory_db,
    route_by_intent,
)
from agents.default_router.registry import (
    get_default_router_runner,
    reset_default_router_runner_cache_for_tests,
)
from agents.default_router.runner import run_default_router_turn

__all__ = [
    "MAIN_THREAD_ID",
    "GraphState",
    "app",
    "llm",
    "memory_db",
    "route_by_intent",
    "get_default_router_runner",
    "reset_default_router_runner_cache_for_tests",
    "run_default_router_turn",
]
