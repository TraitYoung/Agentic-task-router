"""API Key 认证中间件：轻量 x-api-key 头校验。

- api_keys 为空时认证关闭（开发模式）
- /health, /metrics, /docs, /openapi.json 始终免认证
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from config.settings import get_settings
from schemas.error_codes import ErrorCode, ErrorResponse

AUTH_EXEMPT_PATHS = {
    "/api/v1/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
    "/redoc",
}


async def api_key_middleware(request: Request, call_next):
    """验证 x-api-key 头，未配置 key 时直接放行。"""
    settings = get_settings()

    # 免认证路径
    if request.url.path in AUTH_EXEMPT_PATHS or not settings.api_keys:
        return await call_next(request)

    api_key = request.headers.get("x-api-key", "").strip()
    valid_keys = {k.strip() for k in settings.api_keys.split(",") if k.strip()}

    if api_key not in valid_keys:
        return JSONResponse(
            status_code=401,
            content=ErrorResponse(
                error_code=ErrorCode.AUTH_INVALID,
                message="Invalid or missing API key",
                details={"header": "x-api-key"},
            ).model_dump(),
        )

    return await call_next(request)
