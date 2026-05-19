"""A 方向步骤级模型路由（同一 Key 可按步骤切不同模型）。"""

from __future__ import annotations

from typing import Dict

from langchain_openai import ChatOpenAI

from config.llm_settings import llm_api_key, llm_base_url, llm_step_model

_CACHE: Dict[str, ChatOpenAI] = {}


def step_model_name(step_id: str) -> str:
    return llm_step_model(step_id)


def resolve_step_llm(step_id: str, fallback_llm):
    """
    为步骤返回模型实例。
    - 优先按环境变量选择同 provider 不同模型
    - 若缺关键配置，回退到 fallback_llm
    """
    api_key = llm_api_key()
    base_url = llm_base_url()
    model = step_model_name(step_id)
    if not api_key:
        return fallback_llm

    cache_key = f"{model}|{base_url}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    inst = ChatOpenAI(model=model, api_key=api_key, base_url=base_url, timeout=180, max_retries=2)
    _CACHE[cache_key] = inst
    return inst
