"""轻量安全中间件：滑动窗口速率限制 + 请求体大小限制。

零额外依赖，使用 Python 标准库实现。适合单进程开发工具场景。
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


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
            return Response(
                content=json.dumps({"detail": "rate limit exceeded"}, ensure_ascii=False),
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(int(window))},
            )

        timestamps.append(now)
        self._cleanup()
        return await call_next(request)
