"""集中配置管理：pydantic-settings 单一事实来源，兼容 QWEN_* / AX_LLM_* 旧部署。

设计要点：
- 不设 env_file（由 main.py 中的 python-dotenv 统一加载 .env）
- 不缓存单例（每次 get_settings() 返回新实例，确保 monkeypatch 在测试中生效）
- 所有旧环境变量回退链在 model_validator 中处理
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_LLM_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_LLM_MODEL = "kimi-k2.6"
DEFAULT_LLM_REQUEST_TIMEOUT = 300
DEFAULT_LLM_MAX_TOKENS = 8192

_STEP_MODEL_ENV: dict[str, tuple[str, ...]] = {
    "discovery": ("LLM_DISCOVERY_MODEL", "AX_LLM_DISCOVERY_MODEL"),
    "sprint_design": ("LLM_SPRINT_MODEL", "AX_LLM_SPRINT_MODEL"),
    "implementation_sketch": ("LLM_IMPLEMENTATION_MODEL", "AX_LLM_IMPLEMENTATION_MODEL"),
    "delivery_review": ("LLM_DELIVERY_MODEL", "AX_LLM_DELIVERY_MODEL"),
    "test_code": ("LLM_TEST_CODE_MODEL", "AX_LLM_TEST_CODE_MODEL"),
    "merge": ("LLM_MERGE_MODEL", "AX_LLM_MERGE_MODEL"),
}

_STEP_MAX_TOKENS: dict[str, int] = {
    "discovery": 8192,
    "sprint_design": 8192,
    "implementation_sketch": 8192,
    "delivery_review": 8192,
    "test_code": 8192,
    "merge": 16384,
    "reverse_engineer": 8192,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────
    llm_api_key: str = ""
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_request_timeout: int = DEFAULT_LLM_REQUEST_TIMEOUT
    llm_max_tokens: int = DEFAULT_LLM_MAX_TOKENS
    llm_thinking: str = "default"
    llm_structured_thinking: str = ""
    llm_structured_mode: str = ""

    llm_discovery_model: str = ""
    llm_sprint_model: str = ""
    llm_implementation_model: str = ""
    llm_delivery_model: str = ""
    llm_test_code_model: str = ""
    llm_merge_model: str = ""

    # ── Application ──────────────────────────────
    cors_origins: str = ""
    redis_url: str = "redis://localhost:6379/0"
    api_keys: str = ""
    log_format: str = "json"

    # ── Workflow budget ──────────────────────────
    ax_workflow_user_max_chars: int = 8000
    ax_workflow_step_json_max_chars: int = 2500

    @model_validator(mode="before")
    @classmethod
    def _apply_fallback_chain(cls, data: Any) -> Any:
        """将 QWEN_* / AX_LLM_* 旧环境变量回退到 LLM_* 主字段。"""
        if not isinstance(data, dict):
            return data

        _fb(data, "llm_api_key", "AX_LLM_API_KEY", "QWEN_API_KEY")
        _fb(data, "llm_base_url", "AX_LLM_BASE_URL", "QWEN_BASE_URL")
        _fb(data, "llm_model", "AX_LLM_DEFAULT_MODEL", "QWEN_MODEL")

        for step_key, env_names in _STEP_MODEL_ENV.items():
            field = _step_field_name(step_key)
            if not data.get(field):
                for name in env_names:
                    val = os.getenv(name, "").strip()
                    if val:
                        data[field] = val
                        break
        return data

    # ── Derived helpers ──────────────────────────

    def has_api_key(self) -> bool:
        return bool(self.llm_api_key)

    def step_model(self, step_id: str) -> str:
        field = _step_field_name(step_id)
        val = getattr(self, field, "")
        return val if val else self.llm_model

    def step_max_tokens(self, step_id: str) -> int:
        return _STEP_MAX_TOKENS.get(step_id, self.llm_max_tokens)

    def thinking_mode(self) -> str:
        mode = self.llm_thinking.strip().lower()
        if mode in ("disabled", "off", "false", "0"):
            return "disabled"
        return "default"

    def structured_thinking_mode(self) -> str | None:
        raw = self.llm_structured_thinking.strip().lower()
        if not raw:
            return None
        if raw in ("disabled", "off", "false", "0"):
            return "disabled"
        if raw in ("default", "on", "enabled", "true", "1"):
            return "default"
        return None

    def model_kwargs(self) -> dict[str, Any]:
        if self.thinking_mode() == "disabled":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {}

    def structured_model_kwargs(self) -> dict[str, Any]:
        mode = self.structured_thinking_mode()
        if mode is None:
            return self.model_kwargs()
        if mode == "disabled":
            return {"extra_body": {"thinking": {"type": "disabled"}}}
        return {}

    def uses_json_prompt_structured(self) -> bool:
        mode = self.llm_structured_mode.strip().lower()
        base = self.llm_base_url.lower()
        if mode in ("native", "openai", "dashscope"):
            return False
        if mode in ("json_prompt", "prompt", "moonshot"):
            return True
        if "dashscope" in base:
            return False
        return "moonshot" in base

    def provider_label(self) -> str:
        base = self.llm_base_url.lower()
        if "moonshot" in base:
            return "moonshot"
        if "dashscope" in base:
            return "dashscope"
        return "openai_compatible"

    def llm_env_health(self) -> dict[str, object]:
        return {
            "has_llm_key": self.has_api_key(),
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "llm_provider": self.provider_label(),
            "llm_thinking": self.thinking_mode(),
            "llm_structured_thinking": self.structured_thinking_mode() or self.thinking_mode(),
            "llm_request_timeout": self.llm_request_timeout,
        }


# ── helpers ──────────────────────────────────────

def _step_field_name(step_id: str) -> str:
    return f"llm_{step_id.replace('_sketch', '').replace('_design', '').replace('_review', '')}_model"


def _fb(data: dict, primary: str, *fallback_keys: str) -> None:
    if data.get(primary):
        return
    for key in fallback_keys:
        val = os.getenv(key, "").strip()
        if val:
            data[primary] = val
            return


def get_settings() -> Settings:
    """返回新 Settings 实例，每次调用从 os.environ 重新读取。"""
    return Settings()
