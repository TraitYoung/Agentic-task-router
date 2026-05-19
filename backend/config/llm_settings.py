"""LLM 环境变量集中读取：主配置为 LLM_*，兼容 QWEN_* / AX_LLM_* 旧部署。"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_LLM_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_LLM_MODEL = "kimi-k2.6"
DEFAULT_LLM_REQUEST_TIMEOUT = 300

_STEP_MODEL_ENV: dict[str, tuple[str, ...]] = {
    "discovery": ("LLM_DISCOVERY_MODEL", "AX_LLM_DISCOVERY_MODEL"),
    "sprint_design": ("LLM_SPRINT_MODEL", "AX_LLM_SPRINT_MODEL"),
    "implementation_sketch": ("LLM_IMPLEMENTATION_MODEL", "AX_LLM_IMPLEMENTATION_MODEL"),
    "delivery_review": ("LLM_DELIVERY_MODEL", "AX_LLM_DELIVERY_MODEL"),
    "merge": ("LLM_MERGE_MODEL", "AX_LLM_MERGE_MODEL"),
}

# Kimi K2.6：结构化 JSON 步骤适中，merge 汇总可更长
_STEP_MAX_TOKENS: dict[str, int] = {
    "discovery": 8192,
    "sprint_design": 8192,
    "implementation_sketch": 8192,
    "delivery_review": 8192,
    "merge": 16384,
    "reverse_engineer": 8192,
}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


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


def llm_request_timeout() -> int:
    return _env_int("LLM_REQUEST_TIMEOUT", DEFAULT_LLM_REQUEST_TIMEOUT)


def llm_max_tokens(step_id: str) -> int:
    default = _env_int("LLM_MAX_TOKENS", 8192)
    return _STEP_MAX_TOKENS.get(step_id, default)


def llm_thinking_mode() -> str:
    """default | disabled — 默认保持 Kimi 官方思考模式开启。"""
    mode = os.getenv("LLM_THINKING", "default").strip().lower()
    if mode in ("disabled", "off", "false", "0"):
        return "disabled"
    return "default"


def llm_model_kwargs() -> dict[str, Any]:
    """传给 ChatOpenAI 的 model_kwargs；temperature/top_p 使用模型默认，不显式覆盖。"""
    if llm_thinking_mode() == "disabled":
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {}


def llm_structured_thinking_mode() -> str | None:
    """
    结构化 JSON 步骤的思考模式。
    未设置 LLM_STRUCTURED_THINKING 时继承 LLM_THINKING；设为 disabled 可为 JSON 留出更多输出 token。
    """
    raw = os.getenv("LLM_STRUCTURED_THINKING", "").strip().lower()
    if not raw:
        return None
    if raw in ("disabled", "off", "false", "0"):
        return "disabled"
    if raw in ("default", "on", "enabled", "true", "1"):
        return "default"
    return None


def llm_structured_model_kwargs() -> dict[str, Any]:
    mode = llm_structured_thinking_mode()
    if mode is None:
        return llm_model_kwargs()
    if mode == "disabled":
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {}


def llm_provider_label() -> str:
    base = llm_base_url().lower()
    if "moonshot" in base:
        return "moonshot"
    if "dashscope" in base:
        return "dashscope"
    return "openai_compatible"


def has_llm_api_key() -> bool:
    return bool(llm_api_key())


def llm_env_health() -> dict[str, object]:
    """供 /api/v1/health 返回的 LLM 相关字段。"""
    return {
        "has_llm_key": has_llm_api_key(),
        "llm_model": llm_default_model(),
        "llm_base_url": llm_base_url(),
        "llm_provider": llm_provider_label(),
        "llm_thinking": llm_thinking_mode(),
        "llm_structured_thinking": llm_structured_thinking_mode() or llm_thinking_mode(),
        "llm_request_timeout": llm_request_timeout(),
    }
