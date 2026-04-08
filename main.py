from uuid import uuid4
import re
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.router import app as router_graph
from memory.session_cache import SessionCache
from schemas.protocols import TaskIntent

app = FastAPI(title="Axiodrasil Core API", version="1.0.0")

session_cache = SessionCache(ttl_seconds=3600, window_size=5)


@app.get("/api/v1/health")
def api_health():
    """轻量探活：供 Next 开发代理与运维脚本探测；不调用大模型。"""
    redis_ok = False
    try:
        session_cache.client.ping()
        redis_ok = True
    except Exception:
        pass
    return {"ok": True, "redis": redis_ok}


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000, description="用户原始输入")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: TaskIntent


class ChatExportItem(BaseModel):
    user: str
    assistant: str
    ts: str


class ChatExportResponse(BaseModel):
    session_id: str
    turns: List[ChatExportItem]
    file_path: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    turns: List[ChatExportItem]


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
        "jean": "jean",
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
        "jean": "jean",
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


@app.post("/api/v1/chat/export", response_model=ChatExportResponse)
async def chat_export_api(x_session_id: str | None = Header(default=None), limit: int = 20):
    """
    导出当前 session 的最近对话轮次到 output/chats/*.jsonl。

    - 文件命名：YYYYMMDD_HHMMSS_首句prompt截断.jsonl
    - 内容：每行一个 {user, assistant, ts}
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="missing x-session-id header")

    turns = session_cache.get_recent_turns(session_id=x_session_id, limit=limit)
    if not turns:
        raise HTTPException(status_code=404, detail="no turns found for this session")

    project_root = Path(__file__).resolve().parent
    export_dir = project_root / "output" / "chats"
    export_dir.mkdir(parents=True, exist_ok=True)

    first_user = ""
    for t in turns:
        if t.get("user"):
            first_user = t["user"]
            break
    title = (first_user.splitlines()[0] if first_user else "session").strip()
    if len(title) > 30:
        title = title[:30]
    safe_title = "".join(ch for ch in title if ch not in '\\/:*?"<>|' and ord(ch) >= 32) or "session"

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{safe_title}.jsonl"
    file_path = export_dir / filename

    items: List[ChatExportItem] = []
    with file_path.open("w", encoding="utf-8") as f:
        for t in turns:
            item = ChatExportItem(
                user=t.get("user", ""),
                assistant=t.get("assistant", ""),
                ts=t.get("ts", ""),
            )
            items.append(item)
            f.write(item.model_dump_json(ensure_ascii=False) + "\n")

    rel_path = str(file_path.relative_to(project_root))
    return ChatExportResponse(session_id=x_session_id, turns=items, file_path=rel_path)


@app.get("/api/v1/chat/history", response_model=ChatHistoryResponse)
async def chat_history_api(x_session_id: str | None = Header(default=None), limit: int = 50):
    """
    获取当前 session 的最近对话轮次（用于前端展示聊天记录）。
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="missing x-session-id header")

    turns_raw = session_cache.get_recent_turns(session_id=x_session_id, limit=limit)
    if not turns_raw:
        return ChatHistoryResponse(session_id=x_session_id, turns=[])

    items: List[ChatExportItem] = []
    for t in turns_raw:
        items.append(
            ChatExportItem(
                user=t.get("user", ""),
                assistant=t.get("assistant", ""),
                ts=t.get("ts", ""),
            )
        )

    return ChatHistoryResponse(session_id=x_session_id, turns=items)