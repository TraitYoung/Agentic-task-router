"""全链路追踪：API 与 SSE 返回的步骤模型。"""

from typing import Any

from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    """单次图节点（或合成路由步骤）的可序列化快照。"""

    index: int = Field(..., ge=1, description="从 1 递增的步骤序号")
    node: str = Field(..., description="节点名；条件边决策为 __router__")
    ts: str = Field(..., description="UTC ISO8601 时间戳")
    duration_ms: float = Field(..., description="相对上一步结束的本步耗时（毫秒）")
    keys_written: list[str] = Field(default_factory=list, description="该步写入 state 的键")
    summary: dict[str, Any] = Field(
        default_factory=dict,
        description="脱敏摘要：intent 截断、reply 预览等",
    )
