from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TaskIntent(BaseModel):
    """核心输入解析协议 (V15.0)"""

    task_type: Literal["logic", "emotion", "strategy", "unknown"] = Field(
        ...,
        description="""任务分类路由标识。只能是以下四个值之一：
        - logic: 涉及代码审计、数学推演、逻辑纠错等专业硬核任务。
        - emotion: 单纯的情绪发泄、求安慰、吐槽，不包含具体的专业问题。
        - strategy: 宏观规划、复习策略、方法论探讨。
        - unknown: 无法稳定判断时使用。
        绝对禁止输出 logic、emotion、strategy、unknown 之外的任何新标签。""",
    )
    urgency_level: int = Field(
        default=1, ge=1, le=5, description="紧急程度，范围只能是 1 到 5。"
    )
    pain_level: int = Field(
        default=1,
        ge=1,
        le=10,
        description="""身心痛感指标，范围只能是 1 到 10。
        - 1-3: 正常状态，或轻微脑力疲劳。
        - 4-6: 中度疲劳、情绪见底、抱怨、想哭、受挫，但没有严重躯体化症状。
        - 7-10: 只有明确提到严重生理反应，例如心脏狂跳、手抖、极度疼痛、呼吸困难、濒临昏厥等，才能打到这个区间。""",
    )
    raw_input: str = Field(
        ..., description="用户原始输入内容，必须原样保留，不允许省略。"
    )

    # 【新增：豪威尔记忆矩阵象限】
    quadrant: Literal["Q1", "Q2", "Q3", "Q4"] = Field(
        default="Q4",
        description=(
            "艾森豪威尔矩阵象限。"
            "Q1: 紧急重要(如健康预警), "
            "Q2: 重要不紧急(如技术积累), "
            "Q3: 紧急不重要(琐事), "
            "Q4: 不重要不紧急(废话)"
        ),
    )

    @field_validator("pain_level")
    def validate_pain(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("pain_level 必须在 1-10 之间")
        if v > 6:
            print(f"[WARNING] 触发医疗红线！当前痛感判定为: {v}")
        return v

    @field_validator("urgency_level")
    def validate_urgency(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("urgency_level 必须在 1-5 之间")
        return v