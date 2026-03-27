from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
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

    reply = str(result.get("final_response", ""))
    intent = result.get("intent")
    if intent is None:
        raise HTTPException(status_code=500, detail="router returned empty intent")

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