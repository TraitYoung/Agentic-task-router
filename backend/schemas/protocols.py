from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TaskIntent(BaseModel):
    """输入解析协议 — 轻量版，供前端兼容与 trace 记录使用。"""

    task_type: Literal["dev_pipeline"] = Field(
        default="dev_pipeline",
        description="任务类型。当前固定为 dev_pipeline。",
    )
    urgency_level: int = Field(
        default=1, ge=1, le=5, description="紧急程度，范围 1-5。"
    )
    pain_level: int = Field(
        default=1, ge=1, le=10, description="身心痛感指标，范围 1-10。保留用于未来扩展。"
    )
    raw_input: str = Field(
        ..., description="用户原始输入内容，必须原样保留。"
    )
    quadrant: Literal["Q1", "Q2", "Q3", "Q4"] = Field(
        default="Q4",
        description="艾森豪威尔矩阵象限。保留用于未来记忆系统。",
    )

    @field_validator("pain_level")
    def validate_pain(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("pain_level 必须在 1-10 之间")
        return v

    @field_validator("urgency_level")
    def validate_urgency(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("urgency_level 必须在 1-5 之间")
        return v
