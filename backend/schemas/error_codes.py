"""统一错误码枚举与标准化错误响应模型。

所有 API 错误返回均使用 ErrorResponse 格式：
    {error_code, message, details, trace_id}
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    RATE_LIMIT = "RATE_LIMIT"
    INVALID_INPUT = "INVALID_INPUT"
    LLM_FAILURE = "LLM_FAILURE"
    NOT_FOUND = "NOT_FOUND"
    MISSING_SESSION = "MISSING_SESSION"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID = "AUTH_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class ErrorResponse(BaseModel):
    error_code: ErrorCode = Field(..., description="机器可读错误码")
    message: str = Field(..., description="人类可读错误描述")
    details: dict[str, Any] | None = Field(default=None, description="额外上下文（字段名、约束等）")
    trace_id: str = Field(default="", description="请求追踪 ID")
