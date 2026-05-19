"""结构化流水线步骤失败时携带步骤标识，便于 SSE/日志定位。"""

from __future__ import annotations


class StructuredStepError(Exception):
    """某一步 invoke_structured 失败。"""

    def __init__(self, step_id: str, model_name: str, cause: Exception) -> None:
        self.step_id = step_id
        self.model_name = model_name
        self.cause = cause
        super().__init__(str(cause))

    def user_message(self) -> str:
        return f"步骤「{self.step_id}」（{self.model_name}）失败: {self.cause}"
