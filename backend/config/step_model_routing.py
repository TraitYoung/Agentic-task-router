"""A 方向步骤级模型路由（同一 Key 可按步骤切不同模型）。"""

from __future__ import annotations

import json
from typing import Dict

from langchain_openai import ChatOpenAI

from config.llm_settings import (
    llm_api_key,
    llm_base_url,
    llm_max_tokens,
    llm_model_kwargs,
    llm_request_timeout,
    llm_step_model,
    llm_structured_model_kwargs,
)

_CACHE: Dict[str, ChatOpenAI] = {}


def step_model_name(step_id: str) -> str:
    return llm_step_model(step_id)


def resolve_step_llm(step_id: str, fallback_llm, *, structured: bool = False):
    """
    为步骤返回模型实例。
    - 优先按环境变量选择同 provider 不同模型
    - 若缺关键配置，回退到 fallback_llm
    - structured=True 时使用 LLM_STRUCTURED_THINKING（若配置）以节省 JSON 输出 token
    """
    api_key = llm_api_key()
    base_url = llm_base_url()
    model = step_model_name(step_id)
    if not api_key:
        return fallback_llm

    max_tokens = llm_max_tokens(step_id)
    model_kwargs = llm_structured_model_kwargs() if structured else llm_model_kwargs()
    kwargs_key = json.dumps(model_kwargs, sort_keys=True, default=str)
    cache_key = f"{model}|{base_url}|{step_id}|{max_tokens}|{structured}|{llm_request_timeout()}|{kwargs_key}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    inst = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=llm_request_timeout(),
        max_retries=2,
        max_tokens=max_tokens,
        model_kwargs=model_kwargs,
    )
    _CACHE[cache_key] = inst
    return inst
