"""
内阁默认执行器：Redis 热上下文 + LangGraph + 全链路 trace。

签名稳定，便于与 `registry.get_cabinet_runner()` 返回的其它实现互换。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Tuple

from fastapi import HTTPException

from agents.cabinet.graph import app as cabinet_graph
from tracing.router_run import run_router_traced

if TYPE_CHECKING:
    from memory.session_cache import SessionCache
    from schemas.protocols import TaskIntent


def run_cabinet_turn(
    text: str,
    session_id: str,
    session_cache: "SessionCache",
) -> Tuple[str, "TaskIntent", List[dict], str]:
    """
    执行一轮内阁对话。

    Returns:
        reply_raw: 模型原文（未加 [prefix]:）
        intent: TaskIntent
        trace_raw: 与 TraceStep 兼容的 dict 列表
        active_task_type: emotion|jean|bit|juzheng|unknown
    """
    try:
        recent_history = session_cache.format_recent_history(session_id=session_id, limit=5)
    except Exception:
        recent_history = []
    graph_state = {
        "current_input": text,
        "thread_id": session_id,
        "recent_history": recent_history,
    }
    result, trace_raw = run_router_traced(cabinet_graph, graph_state)
    reply_raw = str(result.get("final_response", ""))
    intent = result.get("intent")
    if intent is None:
        raise HTTPException(status_code=500, detail="router returned empty intent")
    active_task_type = result.get("active_task_type")
    if active_task_type is None:
        active_task_type = getattr(intent, "task_type", None)
    return reply_raw, intent, trace_raw, str(active_task_type)
