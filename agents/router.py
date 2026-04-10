"""
向后兼容：`from agents.router import app, llm, memory_db, MAIN_THREAD_ID` 等。

默认路由实现已迁至 `agents.default_router`；新代码请优先 `from agents.default_router import ...`。
"""

from agents.default_router.graph import (
    MAIN_THREAD_ID,
    GraphState,
    app,
    llm,
    memory_db,
    node_bina,
    node_bit,
    node_jean,
    node_juzheng,
    node_parser,
    parser_llm,
    route_by_intent,
    workflow,
)

__all__ = [
    "MAIN_THREAD_ID",
    "GraphState",
    "app",
    "llm",
    "memory_db",
    "node_bina",
    "node_bit",
    "node_jean",
    "node_juzheng",
    "node_parser",
    "parser_llm",
    "route_by_intent",
    "workflow",
]
