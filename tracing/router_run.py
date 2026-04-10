"""
使用 LangGraph stream_mode="updates" 收集主图每步 state 增量，并插入条件边决策步骤。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

_ROUTE_TO_NODE = {
    "emotion_route": "emotion_agent",
    "jean_route": "jean_agent",
    "bit_route": "bit_agent",
    "juzheng_route": "juzheng_agent",
}


def _node_key_str(node_key: Any) -> str:
    if isinstance(node_key, tuple):
        return ".".join(str(x) for x in node_key)
    return str(node_key)


def _summarize_update(update: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if "intent" in update:
        intent = update["intent"]
        if hasattr(intent, "model_dump"):
            d = dict(intent.model_dump())
            raw = str(d.get("raw_input") or "")
            if len(raw) > 200:
                d["raw_input"] = raw[:200] + "..."
            out["intent"] = d
        else:
            out["intent"] = str(intent)[:200]
    if "active_task_type" in update:
        out["active_task_type"] = update["active_task_type"]
    if "final_response" in update:
        fr = str(update["final_response"])
        out["reply_preview"] = fr[:220] + ("..." if len(fr) > 220 else "")
    return out


def run_router_traced(graph, graph_state: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    执行编译后的 LangGraph，返回与 invoke 等价的累积 state 与追踪步骤列表。
    在 parser 之后会追加一步 __router__（与 route_by_intent 一致），便于对齐条件边。
    """
    from agents.default_router.graph import route_by_intent

    accumulated: Dict[str, Any] = {**graph_state}
    steps: List[Dict[str, Any]] = []
    t_prev = time.perf_counter()

    for chunk in graph.stream(graph_state, stream_mode="updates"):
        if not isinstance(chunk, dict):
            continue
        for node_key, update in chunk.items():
            node_str = _node_key_str(node_key)
            t_now = time.perf_counter()
            duration_ms = round((t_now - t_prev) * 1000, 2)
            t_prev = t_now

            if not isinstance(update, dict):
                steps.append(
                    {
                        "index": 0,
                        "node": node_str,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": duration_ms,
                        "keys_written": [],
                        "summary": {"non_dict_update": type(update).__name__},
                    }
                )
                continue

            accumulated.update(update)
            keys_written = list(update.keys())
            summary = _summarize_update(update)

            steps.append(
                {
                    "index": 0,
                    "node": node_str,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": duration_ms,
                    "keys_written": keys_written,
                    "summary": summary,
                }
            )

            if node_str == "parser" and accumulated.get("intent") is not None:
                try:
                    rk = route_by_intent(accumulated)  # type: ignore[arg-type]
                except Exception as exc:
                    rk = f"<route_error:{exc}>"
                steps.append(
                    {
                        "index": 0,
                        "node": "__router__",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "duration_ms": 0.0,
                        "keys_written": [],
                        "summary": {
                            "route_key": rk,
                            "next_node": _ROUTE_TO_NODE.get(str(rk), str(rk)),
                        },
                    }
                )

    for i, s in enumerate(steps, start=1):
        s["index"] = i

    return accumulated, steps
