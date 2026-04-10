from uuid import uuid4
import re
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents.default_router.graph import llm as router_llm
from agents.default_router.registry import get_default_router_runner
from agents.workflow_pipelines import run_dev_pipeline, synthetic_intent_for_workflow
from memory.session_cache import SessionCache
from schemas.protocols import TaskIntent
from schemas.trace import TraceStep
from core_logging import configure_stdio_utf8, setup_logging

configure_stdio_utf8()
setup_logging()

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


WorkflowMode = Literal["default", "dev_pipeline"]


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12000, description="用户原始输入")
    workflow_mode: WorkflowMode = Field(
        default="default",
        description="default=内阁路由；dev_pipeline=AI 赋能软件工程（敏捷取向）多步流水线",
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
    """
    执行一轮对话或工作流。返回 (带前缀的 reply, intent, trace_raw, active_task_type)。
    """
    if payload.workflow_mode == "dev_pipeline":
        reply_raw, trace_raw = run_dev_pipeline(payload.text, router_llm)
        intent = synthetic_intent_for_workflow(payload.text, task_type="bit")
        active_task_type = "dev_pipeline"
    else:
        default_router_run = get_default_router_runner()
        reply_raw, intent, trace_raw, active_task_type = default_router_run(
            payload.text,
            session_id,
            session_cache,
        )

    prefix_map = {
        "emotion": "bina",
        "jean": "jean",
        "bit": "bit",
        "juzheng": "juzheng",
        "unknown": "juzheng",
        "dev_pipeline": "dev",
    }
    prefix = prefix_map.get(str(active_task_type), "juzheng")
    reply_clean = re.sub(r"^\s*\[[^\]]+]\s*[:：]\s*", "", str(reply_raw))
    reply = f"[{prefix}]: {reply_clean}"
    return reply, intent, trace_raw, str(active_task_type)


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
            "workflow_mode": payload.workflow_mode,
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