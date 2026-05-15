from uuid import uuid4
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Literal

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config.step_model_routing import resolve_step_llm
from agents.workflow_pipelines import run_dev_pipeline, run_reverse_engineer, synthetic_intent_for_workflow
from memory.session_cache import SessionCache
from schemas.protocols import TaskIntent
from schemas.trace import TraceStep
from core_logging import configure_stdio_utf8, setup_logging
from repo_paths import REPO_ROOT

configure_stdio_utf8()
setup_logging()

app = FastAPI(title="SpecForge API", version="2.0.0")

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


Mode = Literal["spec", "review"]


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000, description="用户输入（想法描述或待审查的代码）")
    mode: Mode = Field(
        default="spec",
        description="spec=想法→工程规格（正向）；review=粘贴代码→审查报告（逆向）",
    )


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: TaskIntent
    trace_id: str
    trace: list[TraceStep]


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


def _execute_turn(payload: ChatRequest, session_id: str) -> tuple[str, TaskIntent, list, str]:
    if payload.mode == "review":
        llm = resolve_step_llm("reverse_engineer", None)
        reply_raw, trace_raw = run_reverse_engineer(payload.text, llm)
    else:
        llm = resolve_step_llm("discovery", None)
        reply_raw, trace_raw = run_dev_pipeline(payload.text, llm)
    intent = synthetic_intent_for_workflow(payload.text)
    reply = f"[specforge]: {reply_raw}"
    return reply, intent, trace_raw, payload.mode


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_api(
    payload: ChatRequest,
    response: Response,
    x_session_id: str | None = Header(default=None),
    x_trace_id: str | None = Header(default=None, alias="x-trace-id"),
):
    session_id = x_session_id or str(uuid4())
    trace_id = (x_trace_id or "").strip() or str(uuid4())
    response.headers["X-Trace-Id"] = trace_id

    try:
        reply, intent, trace_raw, _active = _execute_turn(payload, session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"turn failed: {exc}") from exc

    # 每次回复后写回 Redis，会话 TTL 维持 1 小时
    try:
        session_cache.append_turn(
            session_id=session_id,
            user_text=payload.text,
            assistant_text=reply,
        )
    except Exception:
        pass

    trace = [TraceStep.model_validate(s) for s in trace_raw]
    return ChatResponse(
        session_id=session_id,
        reply=reply,
        intent=intent,
        trace_id=trace_id,
        trace=trace,
    )


@app.post("/api/v1/chat/stream")
async def chat_stream_api(
    payload: ChatRequest,
    x_session_id: str | None = Header(default=None),
    x_trace_id: str | None = Header(default=None, alias="x-trace-id"),
):
    """
    SSE 流式输出接口：返回 text/event-stream。
    说明：本实现先走一次 router 生成完整回复，然后把 reply 按片段分批吐给前端。
    这样可以不破坏现有 LangGraph 逻辑，同时让前端获得“打字机效果”的流式体验。
    """
    session_id = x_session_id or str(uuid4())
    trace_id = (x_trace_id or "").strip() or str(uuid4())

    try:
        reply, intent, trace_raw, _active = _execute_turn(payload, session_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"turn failed: {exc}") from exc

    # 每次回复后写回 Redis，会话 TTL 维持 1 小时
    try:
        session_cache.append_turn(
            session_id=session_id,
            user_text=payload.text,
            assistant_text=reply,
        )
    except Exception:
        pass

    trace_payload = [TraceStep.model_validate(s).model_dump() for s in trace_raw]

    async def event_gen():
        # 1) meta（含全链路追踪，便于前端展示）
        meta = {
            "session_id": session_id,
            "intent": intent.model_dump(),
            "trace_id": trace_id,
            "trace": trace_payload,
            "mode": payload.mode,
        }
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

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Trace-Id": trace_id},
    )


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

    export_dir = REPO_ROOT / "output" / "chats"
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

    rel_path = str(file_path.relative_to(REPO_ROOT))
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