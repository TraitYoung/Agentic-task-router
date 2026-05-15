"""A 方向步骤级模型路由（同一 Key 可按步骤切不同模型）。"""

from __future__ import annotations

import os
from typing import Dict

from langchain_openai import ChatOpenAI

_CACHE: Dict[str, ChatOpenAI] = {}


def _env(name: str, default: str) -> str:
    v = os.getenv(name, "").strip()
    return v or default


def step_model_name(step_id: str) -> str:
    default_model = _env("AX_LLM_DEFAULT_MODEL", _env("QWEN_MODEL", "qwen-plus"))
    mapping = {
        "discovery": _env("AX_LLM_DISCOVERY_MODEL", default_model),
        "sprint_design": _env("AX_LLM_SPRINT_MODEL", default_model),
        "implementation_sketch": _env("AX_LLM_IMPLEMENTATION_MODEL", default_model),
        "delivery_review": _env("AX_LLM_DELIVERY_MODEL", default_model),
        "merge": _env("AX_LLM_MERGE_MODEL", default_model),
    }
    return mapping.get(step_id, default_model)


def resolve_step_llm(step_id: str, fallback_llm):
    """
    为步骤返回模型实例。
    - 优先按环境变量选择同 provider 不同模型
    - 若缺关键配置，回退到 fallback_llm
    """
    api_key = _env("AX_LLM_API_KEY", _env("QWEN_API_KEY", ""))
    base_url = _env("AX_LLM_BASE_URL", _env("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    model = step_model_name(step_id)
    if not api_key:
        return fallback_llm

    cache_key = f"{model}|{base_url}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    inst = ChatOpenAI(model=model, api_key=api_key, base_url=base_url)
    _CACHE[cache_key] = inst
    return inst

