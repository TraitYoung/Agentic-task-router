"""轻量安全中间件：滑动窗口速率限制 + 请求体大小限制。

零额外依赖，使用 Python 标准库实现。适合单进程开发工具场景。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from core_logging import session_id_var, trace_id_var
from schemas.error_codes import ErrorCode, ErrorResponse

logger = logging.getLogger("specforge.request")


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """内存滑动窗口速率限制。

    规则:
      - /api/v1/chat, /api/v1/chat/stream: 10 req / 60s
      - 其他: 30 req / 60s
    """

    def __init__(self, app, **kwargs) -> None:
        super().__init__(app)
        self._buckets: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._last_cleanup = time.monotonic()

    def _cleanup(self) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < 120:
            return
        self._last_cleanup = now
        cutoff = now - 120
        for ip_buckets in self._buckets.values():
            for path in list(ip_buckets):
                ip_buckets[path] = [t for t in ip_buckets[path] if t > cutoff]
                if not ip_buckets[path]:
                    del ip_buckets[path]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        limits: dict[str, int] = {
            "/api/v1/chat": 10,
            "/api/v1/chat/stream": 10,
            "/api/v1/health": 60,
        }
        max_req = limits.get(path, 30)
        window = 60.0

        ip = _client_ip(request)
        now = time.monotonic()
        timestamps = self._buckets[ip][path]

        # 剔除窗口外的记录
        cutoff = now - window
        timestamps[:] = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= max_req:
            err = ErrorResponse(
                error_code=ErrorCode.RATE_LIMIT,
                message="rate limit exceeded",
                details={"retry_after_seconds": int(window)},
            )
            return JSONResponse(
                content=err.model_dump(),
                status_code=429,
                headers={"Retry-After": str(int(window))},
            )

        timestamps.append(now)
        self._cleanup()
        return await call_next(request)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """Request-level access log with trace id and duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = request.headers.get("x-trace-id", "").strip() or "-"
        session_id = request.headers.get("x-session-id", "").strip() or "-"
        path = request.url.path
        method = request.method
        ip = _client_ip(request)

        # 注入 contextvars，供下游日志自动携带
        for_token = trace_id_var.set(trace_id)
        for_session = session_id_var.set(session_id)

        started = time.perf_counter()
        logger.info("request start: method=%s path=%s client_ip=%s", method, path, ip)
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "request failed: method=%s path=%s duration_ms=%.2f client_ip=%s",
                method,
                path,
                duration_ms,
                ip,
            )
            # 重置 contextvars
            trace_id_var.reset(for_token)
            session_id_var.reset(for_session)
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "request done: method=%s path=%s status=%d duration_ms=%.2f client_ip=%s",
            method,
            path,
            response.status_code,
            duration_ms,
            ip,
        )
        if trace_id != "-":
            response.headers.setdefault("X-Trace-Id", trace_id)

        trace_id_var.reset(for_token)
        session_id_var.reset(for_session)
        return response
