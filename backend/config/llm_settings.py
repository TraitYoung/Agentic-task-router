"""LLM 环境变量集中读取：主配置为 LLM_*，兼容 QWEN_* / AX_LLM_* 旧部署。

所有函数已迁移至 config.settings.Settings，此处保留向后兼容的函数签名。"""

from __future__ import annotations

from typing import Any

from config.settings import Settings

DEFAULT_LLM_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_LLM_MODEL = "kimi-k2.6"
DEFAULT_LLM_REQUEST_TIMEOUT = 300


def llm_api_key() -> str:
    return Settings().llm_api_key


def llm_base_url() -> str:
    return Settings().llm_base_url


def llm_default_model() -> str:
    return Settings().llm_model


def llm_step_model(step_id: str) -> str:
    return Settings().step_model(step_id)


def llm_request_timeout() -> int:
    return Settings().llm_request_timeout


def llm_max_tokens(step_id: str) -> int:
    return Settings().step_max_tokens(step_id)


def llm_thinking_mode() -> str:
    return Settings().thinking_mode()


def llm_model_kwargs() -> dict[str, Any]:
    return Settings().model_kwargs()


def llm_structured_thinking_mode() -> str | None:
    return Settings().structured_thinking_mode()


def llm_structured_model_kwargs() -> dict[str, Any]:
    return Settings().structured_model_kwargs()


def llm_provider_label() -> str:
    return Settings().provider_label()


def has_llm_api_key() -> bool:
    return Settings().has_api_key()


def llm_env_health() -> dict[str, object]:
    return Settings().llm_env_health()
