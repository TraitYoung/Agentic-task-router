from uuid import uuid4
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import List, Literal

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config.step_model_routing import resolve_step_llm
from middleware import RateLimitMiddleware, RequestLogMiddleware
from agents.workflow_pipelines import run_dev_pipeline, run_reverse_engineer, synthetic_intent_for_workflow
from agents.dev_pipeline.orchestrator import run_dev_pipeline_stream, run_reverse_engineer_stream
from memory.session_cache import SessionCache
from memory.spec_store import get_spec_store
from schemas.protocols import TaskIntent
from schemas.trace import TraceStep
from core_logging import configure_stdio_utf8, get_logger, setup_logging
from repo_paths import REPO_ROOT

configure_stdio_utf8()
setup_logging()

logger = get_logger("specforge.main")

app = FastAPI(title="SpecForge API", version="2.0.0")
STARTED_AT = time.monotonic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLogMiddleware)

session_cache = SessionCache(ttl_seconds=3600, window_size=5)

spec_store = get_spec_store()

# 启动时校验关键配置
if not os.getenv("QWEN_API_KEY"):
    logger.warning("QWEN_API_KEY not set — LLM calls will fail. Copy .env.example to .env and fill in your key.")


@app.on_event("shutdown")
def _shutdown() -> None:
    session_cache.close()
    spec_store.close()
    logger.info("shutdown complete")


@app.get("/api/v1/health")
def api_health():
    """轻量探活:供 Next 开发代理与运维脚本探测；不调用大模型。"""
    redis_status = {"ok": False, "error": ""}
    try:
        session_cache.client.ping()
        redis_status["ok"] = True
    except Exception as exc:
        redis_status["error"] = str(exc)

    sqlite_status = {"ok": False, "error": ""}
    try:
        spec_store._conn.execute("SELECT 1").fetchone()
        sqlite_status["ok"] = True
    except Exception as exc:
        sqlite_status["error"] = str(exc)

    return {
        "ok": True,
        "version": app.version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.monotonic() - STARTED_AT, 2),
        "redis": redis_status,
        "redis_ok": redis_status["ok"],
        "sqlite": sqlite_status,
        "memory_mb": _memory_mb(),
        "env": {
            "has_qwen_key": bool(os.getenv("QWEN_API_KEY")),
            "has_redis_url": bool(os.getenv("REDIS_URL")),
        },
    }


def _memory_mb() -> float:
    try:
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return 0.0


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
    store = get_spec_store()
    retrieval_context = ""

    if payload.mode == "review":
        top_issues = store.get_top_issues(limit=8)
        if top_issues:
            retrieval_context = "高频问题模式（按频率降序）:\n" + "\n".join(
                f"- [{i['issue_type']}] {i['issue_text']}（出现 {i['frequency']} 次）"
                for i in top_issues
            )
        llm = resolve_step_llm("reverse_engineer", None)
        reply_raw, trace_raw = run_reverse_engineer(payload.text, llm, retrieval_context=retrieval_context)
    else:
        past_specs = store.search_specs(payload.text, mode="spec", limit=3)
        if past_specs:
            parts: list[str] = []
            for s in past_specs:
                stories = _parse_json_field(s.get("user_stories", "[]"))
                modules = _parse_json_field(s.get("modules", "[]"))
                parts.append(
                    f"• 目标:{s['goal']}\n"
                    f"  用户故事:{', '.join(stories) if stories else '无'}\n"
                    f"  模块:{', '.join(modules) if modules else '无'}"
                )
            retrieval_context = "\n".join(parts)
        llm = resolve_step_llm("discovery", None)
        reply_raw, trace_raw = run_dev_pipeline(payload.text, llm, retrieval_context=retrieval_context)

    # 从 trace 中提取 profile，保存到知识库
    profile = _extract_profile(trace_raw)
    try:
        if payload.mode == "review":
            _save_review_issues(store, trace_raw, profile)
        else:
            _save_spec_result(store, trace_raw, payload.text, profile)
    except Exception as exc:
        logger.warning("save to spec_store failed: %s", exc)

    intent = synthetic_intent_for_workflow(payload.text)
    reply = f"[specforge]: {reply_raw}"
    return reply, intent, trace_raw, payload.mode


async def _execute_turn_stream(payload: ChatRequest, session_id: str):
    """流式执行流水线:通过 asyncio.Queue 推送状态/delta 事件。"""
    store = get_spec_store()
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    retrieval_context = ""
    if payload.mode == "review":
        top_issues = store.get_top_issues(limit=8)
        if top_issues:
            retrieval_context = "高频问题模式（按频率降序）:\n" + "\n".join(
                f"- [{i['issue_type']}] {i['issue_text']}（出现 {i['frequency']} 次）"
                for i in top_issues
            )
    else:
        past_specs = store.search_specs(payload.text, mode="spec", limit=3)
        if past_specs:
            parts: list[str] = []
            for s in past_specs:
                stories = _parse_json_field(s.get("user_stories", "[]"))
                modules = _parse_json_field(s.get("modules", "[]"))
                parts.append(
                    f"• 目标:{s['goal']}\n"
                    f"  用户故事:{', '.join(stories) if stories else '无'}\n"
                    f"  模块:{', '.join(modules) if modules else '无'}"
                )
            retrieval_context = "\n".join(parts)

    loop = asyncio.get_running_loop()

    def _run_sync():
        llm = resolve_step_llm("discovery" if payload.mode != "review" else "reverse_engineer", None)
        if payload.mode == "review":
            return run_reverse_engineer_stream(
                payload.text, llm, retrieval_context=retrieval_context, event_queue=event_queue
            )
        else:
            return run_dev_pipeline_stream(
                payload.text, llm, retrieval_context=retrieval_context, event_queue=event_queue
            )

    future = loop.run_in_executor(None, _run_sync)

    # 从 queue 读取事件并 yield，直到 executor 完成
    while True:
        try:
            event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
            yield event
        except asyncio.TimeoutError:
            if future.done():
                while not event_queue.empty():
                    try:
                        yield event_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                break

    reply_raw, trace_raw = future.result()

    # 保存到知识库 + Redis
    profile = _extract_profile(trace_raw)
    try:
        if payload.mode == "review":
            _save_review_issues(store, trace_raw, profile)
        else:
            _save_spec_result(store, trace_raw, payload.text, profile)
    except Exception as exc:
        logger.warning("save to spec_store failed (stream): %s", exc)

    try:
        intent = synthetic_intent_for_workflow(payload.text)
        reply = f"[specforge]: {reply_raw}"
        session_cache.append_turn(session_id=session_id, user_text=payload.text, assistant_text=reply)
    except Exception as exc:
        logger.warning("Redis append_turn failed: %s", exc)
        intent = synthetic_intent_for_workflow(payload.text)
        reply = f"[specforge]: {reply_raw}"

    trace_payload = [TraceStep.model_validate(s).model_dump() for s in trace_raw]

    yield {
        "type": "meta",
        "session_id": session_id,
        "intent": intent.model_dump(),
        "trace_id": "",
        "trace": trace_payload,
        "mode": payload.mode,
    }
    yield {"type": "done"}


def _parse_json_field(raw: str) -> list[str]:
    """安全解析 JSON 字符串字段，返回字符串列表。"""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_profile(trace_raw: list) -> str:
    """从 trace 首步的 summary 中提取项目画像名。"""
    if trace_raw and isinstance(trace_raw[0], dict):
        return str(trace_raw[0].get("summary", {}).get("profile", ""))
    return ""


def _save_spec_result(store, trace_raw: list, user_text: str, profile: str) -> None:
    """从 trace 中提取 Discovery 步骤的结构化数据并保存。"""
    if not trace_raw:
        return

    discovery = trace_raw[0].get("summary", {}).get("discovery", {})
    sprint_design = (
        trace_raw[1].get("summary", {}).get("sprint_design", {})
        if len(trace_raw) > 1
        else {}
    )

    store.save_spec(
        mode="spec",
        profile=profile,
        user_text=user_text[:500],
        goal=str(discovery.get("goal", user_text[:200])),
        user_stories=list(discovery.get("user_stories", [])),
        modules=list(sprint_design.get("modules", [])),
        full_summary=json.dumps(
            {"discovery": discovery, "sprint": sprint_design},
            ensure_ascii=False,
        )[:4000],
    )


def _save_review_issues(store, trace_raw: list, profile: str) -> None:
    """从 trace 中提取审查发现的问题并保存。"""
    if not trace_raw:
        return

    spec = trace_raw[0].get("summary", {}).get("reverse_engineer", {})
    issues: list[dict[str, str]] = []

    for item in spec.get("architecture_issues", []):
        issues.append({"type": "architecture", "text": str(item), "suggestion": ""})
    for item in spec.get("code_quality_issues", []):
        issues.append({"type": "code_quality", "text": str(item), "suggestion": ""})

    suggestions = [str(s) for s in spec.get("improvement_plan", [])]
    for i, issue in enumerate(issues):
        if i < len(suggestions):
            issue["suggestion"] = suggestions[i]

    if issues:
        store.save_issues(profile=profile, issues=issues)


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
        logger.exception(
            "chat turn failed: trace_id=%s session_id=%s mode=%s input_len=%d",
            trace_id,
            session_id,
            payload.mode,
            len(payload.text),
        )
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
    """SSE 流式输出: 流水线各步骤实时推送状态/delta 事件。"""
    session_id = x_session_id or str(uuid4())
    trace_id = (x_trace_id or "").strip() or str(uuid4())

    async def event_gen():
        try:
            async for event in _execute_turn_stream(payload, session_id):
                if event.get("type") == "meta":
                    event["trace_id"] = trace_id
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "chat stream failed: trace_id=%s session_id=%s mode=%s input_len=%d",
                trace_id,
                session_id,
                payload.mode,
                len(payload.text),
            )
            yield f"data: {json.dumps({'type': 'error', 'detail': f'turn failed: {exc}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Trace-Id": trace_id},
    )


@app.post("/api/v1/chat/export", response_model=ChatExportResponse)
async def chat_export_api(x_session_id: str | None = Header(default=None), limit: int = 20):
    """
    导出当前 session 的最近对话轮次到 output/chats/*.jsonl。

    - 文件命名:YYYYMMDD_HHMMSS_首句prompt截断.jsonl
    - 内容:每行一个 {user, assistant, ts}
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
