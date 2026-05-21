from uuid import uuid4
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import List, Literal

from dotenv import load_dotenv
from repo_paths import REPO_ROOT

load_dotenv(REPO_ROOT / ".env", override=False)

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

from auth import api_key_middleware
from config.llm_settings import has_llm_api_key, llm_env_health
from config.settings import get_settings
from config.structured_errors import StructuredStepError
from config.step_model_routing import resolve_step_llm
from middleware import RateLimitMiddleware, RequestLogMiddleware
from agents.workflow_pipelines import run_dev_pipeline, run_reverse_engineer, synthetic_intent_for_workflow
from agents.dev_pipeline.orchestrator import run_dev_pipeline_stream, run_reverse_engineer_stream
from memory.session_cache import SessionCache
from memory.spec_store import get_spec_store
from schemas.error_codes import ErrorCode, ErrorResponse
from schemas.protocols import TaskIntent
from schemas.trace import TraceStep
from core_logging import configure_stdio_utf8, get_logger, setup_logging

configure_stdio_utf8()
setup_logging()

logger = get_logger("specforge.main")

app = FastAPI(
    title="SpecForge API",
    description=(
        "AI 驱动的软件工程规范生成与审查系统。"
        "将模糊需求转化为结构化工程规格，或将代码反向生成审查报告。"
    ),
    version="3.0.0",
    contact={"name": "SpecForge", "url": "https://github.com/specforge"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "health", "description": "服务健康与存活探针"},
        {"name": "chat", "description": "规范生成与代码审查对话端点"},
        {"name": "export", "description": "会话导出与历史查询"},
    ],
)
STARTED_AT = time.monotonic()

# ── Prometheus metrics ─────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics", tags=["health"])

# ── CORS ───────────────────────────────────────

def _cors_origins() -> list[str]:
    settings = get_settings()
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://spec-forge-phi.vercel.app",
    ]
    extra = settings.cors_origins
    if extra:
        origins.extend(x.strip() for x in extra.split(",") if x.strip())
    return list(dict.fromkeys(origins))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLogMiddleware)
# Auth must be after CORS/rate-limit but before request processing
app.middleware("http")(api_key_middleware)

# ── Session & store ────────────────────────────

session_cache = SessionCache(ttl_seconds=3600, window_size=5)
spec_store = get_spec_store()

if not has_llm_api_key():
    logger.warning(
        "LLM_API_KEY not set — LLM calls will fail. "
        "Copy .env.example to .env and set LLM_API_KEY."
    )


# ── Shutdown ───────────────────────────────────

@app.on_event("shutdown")
def _shutdown() -> None:
    session_cache.close()
    spec_store.close()
    logger.info("shutdown complete")


# ── Exception handlers ─────────────────────────

@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    trace_id = getattr(request.state, "trace_id", "") if hasattr(request, "state") else ""
    code_map = {
        400: ErrorCode.INVALID_INPUT,
        401: ErrorCode.AUTH_INVALID,
        404: ErrorCode.NOT_FOUND,
        429: ErrorCode.RATE_LIMIT,
        422: ErrorCode.VALIDATION_ERROR,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR),
            message=str(exc.detail),
            trace_id=trace_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def _generic_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "") if hasattr(request, "state") else ""
    logger.exception("unhandled exception: trace_id=%s", trace_id)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="internal server error",
            trace_id=trace_id,
        ).model_dump(),
    )


# ── Health ─────────────────────────────────────

@app.get(
    "/api/v1/health",
    tags=["health"],
    summary="健康检查",
    description="轻量探活，供开发代理与运维脚本探测；不调用大模型。",
    responses={200: {"description": "服务正常"}},
)
def api_health():
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

    settings = get_settings()
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
            **llm_env_health(),
            "has_redis_url": bool(settings.redis_url),
        },
    }


def _memory_mb() -> float:
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return 0.0


# ── Models ─────────────────────────────────────

Mode = Literal["spec", "review"]


def _turn_error_payload(exc: Exception) -> dict[str, str]:
    if isinstance(exc, StructuredStepError):
        return {"detail": exc.user_message(), "step": exc.step_id}
    return {"detail": f"turn failed: {exc}", "step": ""}


class ChatRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=12000,
        description="用户输入（想法描述或待审查的代码）",
        examples=["做一个 React Todo 应用，支持增删改"],
    )
    mode: Mode = Field(
        default="spec",
        description="spec=想法→工程规格（正向）；review=粘贴代码→审查报告（逆向）",
        examples=["spec"],
    )


class ChatResponse(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    reply: str = Field(..., description="助手回复文本")
    intent: TaskIntent = Field(..., description="解析后的任务意图")
    trace_id: str = Field(..., description="请求追踪 ID")
    trace: list[TraceStep] = Field(default_factory=list, description="流水线各步骤追踪")
    artifact_md: str | None = Field(default=None, description="生成的 Markdown 工件内容")
    artifact_path: str | None = Field(default=None, description="工件文件路径")
    artifact_filename: str | None = Field(default=None, description="工件文件名")


class ChatExportItem(BaseModel):
    user: str = Field(..., description="用户消息")
    assistant: str = Field(..., description="助手回复")
    ts: str = Field(..., description="ISO 时间戳")


class ChatExportResponse(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    turns: List[ChatExportItem] = Field(..., description="对话轮次列表")
    file_path: str = Field(..., description="导出文件路径")


class ChatHistoryResponse(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    turns: List[ChatExportItem] = Field(..., description="对话轮次列表")


# ── Pipeline execution ─────────────────────────

def _execute_turn(payload: ChatRequest, session_id: str):
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
        pipeline = run_reverse_engineer(payload.text, llm, retrieval_context=retrieval_context)
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
        pipeline = run_dev_pipeline(payload.text, llm, retrieval_context=retrieval_context)

    trace_raw = pipeline.steps
    profile = _extract_profile(trace_raw)
    try:
        if payload.mode == "review":
            _save_review_issues(store, trace_raw, profile)
        else:
            _save_spec_result(store, trace_raw, payload.text, profile)
    except Exception as exc:
        logger.warning("save to spec_store failed: %s", exc)

    intent = synthetic_intent_for_workflow(payload.text)
    reply = pipeline.summary
    return (
        reply,
        intent,
        trace_raw,
        payload.mode,
        pipeline.artifact_md,
        pipeline.artifact_path,
        pipeline.artifact_filename,
    )


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

    pipeline = future.result()
    trace_raw = pipeline.steps

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
        session_cache.append_turn(
            session_id=session_id,
            user_text=payload.text,
            assistant_text=pipeline.summary,
        )
    except Exception as exc:
        logger.warning("Redis append_turn failed: %s", exc)
        intent = synthetic_intent_for_workflow(payload.text)

    trace_payload = [TraceStep.model_validate(s).model_dump() for s in trace_raw]

    yield {
        "type": "artifact",
        "format": "markdown",
        "filename": pipeline.artifact_filename,
        "file_path": pipeline.artifact_path,
        "content": pipeline.artifact_md,
    }
    yield {"type": "reply", "content": pipeline.summary}
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
    if trace_raw and isinstance(trace_raw[0], dict):
        return str(trace_raw[0].get("summary", {}).get("profile", ""))
    return ""


def _save_spec_result(store, trace_raw: list, user_text: str, profile: str) -> None:
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


# ── Endpoints ──────────────────────────────────

@app.post(
    "/api/v1/chat",
    response_model=ChatResponse,
    tags=["chat"],
    summary="生成规范或审查报告（同步）",
    description="提交用户想法或代码片段，返回工程规格或审查报告。",
    responses={
        200: {"description": "成功返回规格/审查报告"},
        401: {"description": "缺少或无效的 API Key"},
        422: {"description": "请求参数校验失败"},
        500: {"description": "内部错误"},
    },
)
async def chat_api(
    payload: ChatRequest,
    response: Response,
    x_session_id: str | None = Header(default=None, description="客户端会话 ID"),
    x_trace_id: str | None = Header(default=None, alias="x-trace-id", description="分布式追踪 ID"),
):
    session_id = x_session_id or str(uuid4())
    trace_id = (x_trace_id or "").strip() or str(uuid4())
    response.headers["X-Trace-Id"] = trace_id

    try:
        reply, intent, trace_raw, _mode, artifact_md, artifact_path, artifact_filename = _execute_turn(
            payload, session_id
        )
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
        err = _turn_error_payload(exc)
        raise HTTPException(status_code=500, detail=err["detail"]) from exc

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
        artifact_md=artifact_md,
        artifact_path=artifact_path,
        artifact_filename=artifact_filename,
    )


@app.post(
    "/api/v1/chat/stream",
    tags=["chat"],
    summary="生成规范或审查报告（流式）",
    description="SSE 流式输出:流水线各步骤实时推送状态/delta 事件。",
    responses={
        200: {"description": "SSE 事件流"},
        401: {"description": "缺少或无效的 API Key"},
        500: {"description": "内部错误"},
    },
)
async def chat_stream_api(
    payload: ChatRequest,
    x_session_id: str | None = Header(default=None, description="客户端会话 ID"),
    x_trace_id: str | None = Header(default=None, alias="x-trace-id", description="分布式追踪 ID"),
):
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
            err = {"type": "error", **_turn_error_payload(exc)}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"X-Trace-Id": trace_id},
    )


@app.post(
    "/api/v1/chat/export",
    response_model=ChatExportResponse,
    tags=["export"],
    summary="导出会话对话记录",
    description="将当前 session 的最近对话轮次导出为 JSONL 文件。",
    responses={
        200: {"description": "导出成功"},
        400: {"description": "缺少 session ID"},
        404: {"description": "未找到该会话的对话记录"},
    },
)
async def chat_export_api(
    x_session_id: str | None = Header(default=None, description="客户端会话 ID"),
    limit: int = 20,
):
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


@app.get(
    "/api/v1/chat/history",
    response_model=ChatHistoryResponse,
    tags=["export"],
    summary="查询会话历史",
    description="获取当前 session 的最近对话轮次，用于前端展示聊天记录。",
    responses={
        200: {"description": "对话记录列表"},
        400: {"description": "缺少 session ID"},
    },
)
async def chat_history_api(
    x_session_id: str | None = Header(default=None, description="客户端会话 ID"),
    limit: int = 50,
):
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
