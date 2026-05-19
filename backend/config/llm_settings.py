"""LLM 环境变量集中读取：主配置为 LLM_*，兼容 QWEN_* / AX_LLM_* 旧部署。"""

from __future__ import annotations

import os

DEFAULT_LLM_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_LLM_MODEL = "kimi-k2.6"

_STEP_MODEL_ENV: dict[str, tuple[str, ...]] = {
    "discovery": ("LLM_DISCOVERY_MODEL", "AX_LLM_DISCOVERY_MODEL"),
    "sprint_design": ("LLM_SPRINT_MODEL", "AX_LLM_SPRINT_MODEL"),
    "implementation_sketch": ("LLM_IMPLEMENTATION_MODEL", "AX_LLM_IMPLEMENTATION_MODEL"),
    "delivery_review": ("LLM_DELIVERY_MODEL", "AX_LLM_DELIVERY_MODEL"),
    "merge": ("LLM_MERGE_MODEL", "AX_LLM_MERGE_MODEL"),
}


def _first_nonempty(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def llm_api_key() -> str:
    return _first_nonempty("LLM_API_KEY", "AX_LLM_API_KEY", "QWEN_API_KEY")


def llm_base_url() -> str:
    return _first_nonempty(
        "LLM_BASE_URL",
        "AX_LLM_BASE_URL",
        "QWEN_BASE_URL",
        default=DEFAULT_LLM_BASE_URL,
    )


def llm_default_model() -> str:
    return _first_nonempty(
        "LLM_MODEL",
        "AX_LLM_DEFAULT_MODEL",
        "QWEN_MODEL",
        default=DEFAULT_LLM_MODEL,
    )


def llm_step_model(step_id: str) -> str:
    default = llm_default_model()
    keys = _STEP_MODEL_ENV.get(step_id)
    if not keys:
        return default
    return _first_nonempty(*keys, default=default)


def has_llm_api_key() -> bool:
    return bool(llm_api_key())


def llm_env_health() -> dict[str, object]:
    """供 /api/v1/health 返回的 LLM 相关字段。"""
    return {
        "has_llm_key": has_llm_api_key(),
        "llm_model": llm_default_model(),
        "llm_base_url": llm_base_url(),
    }
