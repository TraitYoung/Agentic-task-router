"""A 方向步骤级模型路由（同一 Key 可按步骤切不同模型）。"""

from __future__ import annotations

import json
from typing import Any, Dict

from langchain_openai import ChatOpenAI

from config.settings import Settings

_CACHE: Dict[str, ChatOpenAI] = {}


def step_model_name(step_id: str) -> str:
    return Settings().step_model(step_id)


def resolve_step_llm(step_id: str, fallback_llm, *, structured: bool = False):
    """
    为步骤返回模型实例。
    - 优先按环境变量选择同 provider 不同模型
    - 若缺关键配置，回退到 fallback_llm
    - structured=True 时使用 LLM_STRUCTURED_THINKING（若配置）以节省 JSON 输出 token
    """
    settings = Settings()
    api_key = settings.llm_api_key
    base_url = settings.llm_base_url
    model = step_model_name(step_id)
    if not api_key:
        return fallback_llm

    max_tokens = settings.step_max_tokens(step_id)
    api_kwargs = dict(settings.structured_model_kwargs() if structured else settings.model_kwargs())
    reasoning_effort = api_kwargs.pop("reasoning_effort", None)
    kwargs_key = json.dumps(api_kwargs, sort_keys=True, default=str)
    cache_key = (
        f"{model}|{base_url}|{step_id}|{max_tokens}|{structured}|"
        f"{settings.llm_request_timeout}|{reasoning_effort}|{kwargs_key}"
    )
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    llm_kwargs: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
        "base_url": base_url,
        "timeout": settings.llm_request_timeout,
        "max_retries": 2,
        "max_tokens": max_tokens,
        "model_kwargs": api_kwargs,
    }
    if reasoning_effort:
        llm_kwargs["reasoning_effort"] = reasoning_effort
    inst = ChatOpenAI(**llm_kwargs)
    _CACHE[cache_key] = inst
    return inst
