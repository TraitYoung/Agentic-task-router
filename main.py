from uuid import uuid4
import re
import asyncio
import json

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.router import app as router_graph
from memory.session_cache import SessionCache
from schemas.protocols import TaskIntent

app = FastAPI(title="Axiodrasil Core API", version="1.0.0")

session_cache = SessionCache(ttl_seconds=3600, window_size=5)


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description="用户原始输入")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: TaskIntent


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_api(payload: ChatRequest, x_session_id: str | None = Header(default=None)):
    session_id = x_session_id or str(uuid4())

    # 先取 Redis 里的最近 5 轮上下文，不影响现有 SQLite 冷数据持久化
    try:
        recent_history = session_cache.format_recent_history(session_id=session_id, limit=5)
    except Exception:
        recent_history = []

    graph_state = {
        "current_input": payload.text,
        "thread_id": session_id,
        "recent_history": recent_history,
    }

    try:
        result = router_graph.invoke(graph_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"router invoke failed: {exc}") from exc

    reply_raw = str(result.get("final_response", ""))
    intent = result.get("intent")
    if intent is None:
        raise HTTPException(status_code=500, detail="router returned empty intent")

    active_task_type = result.get("active_task_type")
    if active_task_type is None:
        active_task_type = getattr(intent, "task_type", None)

    # 由前端网关统一决定输出前缀（拼音）
    prefix_map = {
        "emotion": "bina",
        "taki": "taki",
        "bit": "bit",
        "juzheng": "juzheng",
        "unknown": "juzheng",
    }
    prefix = prefix_map.get(active_task_type, "juzheng")

    # 去掉模型可能自带的英文/中文角色前缀，避免前缀重复
    reply_clean = re.sub(r"^\s*\[[^\]]+]\s*[:：]\s*", "", reply_raw)
    reply = f"[{prefix}]: {reply_clean}"

    # 每次回复后写回 Redis，会话 TTL 维持 1 小时
    try:
        session_cache.append_turn(
            session_id=session_id,
            user_text=payload.text,
            assistant_text=reply,
        )
    except Exception:
        pass

    return ChatResponse(session_id=session_id, reply=reply, intent=intent)


@app.post("/api/v1/chat/stream")
async def chat_stream_api(payload: ChatRequest, x_session_id: str | None = Header(default=None)):
    """
    SSE 流式输出接口：返回 text/event-stream。
    说明：本实现先走一次 router 生成完整回复，然后把 reply 按片段分批吐给前端。
    这样可以不破坏现有 LangGraph 逻辑，同时让前端获得“打字机效果”的流式体验。
    """
    session_id = x_session_id or str(uuid4())

    # 先取 Redis 里的最近 5 轮上下文，不影响现有 SQLite 冷数据持久化
    try:
        recent_history = session_cache.format_recent_history(session_id=session_id, limit=5)
    except Exception:
        recent_history = []

    graph_state = {
        "current_input": payload.text,
        "thread_id": session_id,
        "recent_history": recent_history,
    }

    try:
        result = router_graph.invoke(graph_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"router invoke failed: {exc}") from exc

    reply_raw = str(result.get("final_response", ""))
    intent = result.get("intent")
    if intent is None:
        raise HTTPException(status_code=500, detail="router returned empty intent")

    active_task_type = result.get("active_task_type")
    if active_task_type is None:
        active_task_type = getattr(intent, "task_type", None)

    prefix_map = {
        "emotion": "bina",
        "taki": "taki",
        "bit": "bit",
        "juzheng": "juzheng",
        "unknown": "juzheng",
    }
    prefix = prefix_map.get(active_task_type, "juzheng")

    reply_clean = re.sub(r"^\s*\[[^\]]+]\s*[:：]\s*", "", reply_raw)
    reply = f"[{prefix}]: {reply_clean}"

    # 每次回复后写回 Redis，会话 TTL 维持 1 小时
    try:
        session_cache.append_turn(
            session_id=session_id,
            user_text=payload.text,
            assistant_text=reply,
        )
    except Exception:
        pass

    async def event_gen():
        # 1) meta
        meta = {"session_id": session_id, "intent": intent.model_dump()}
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        # 2) content chunks (pseudo streaming)
        chunk_size = 12
        for i in range(0, len(reply), chunk_size):
            piece = reply[i : i + chunk_size]
            data = {"type": "delta", "content": piece}
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.01)

        # 3) done
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")