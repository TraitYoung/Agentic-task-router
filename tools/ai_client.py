import os
from pathlib import Path
from typing import List

import numpy as np
from dotenv import load_dotenv
from langchain_community.embeddings.dashscope import DashScopeEmbeddings


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# 复用你已有的千问配置（与 agents/router.py 一致）
_QWEN_API_KEY = os.getenv("QWEN_API_KEY")

if not _QWEN_API_KEY:
    raise ValueError("未检测到 QWEN_API_KEY，请在项目根目录 .env 中配置该值。")

# 千问官方 DashScope embedding，text-embedding-v2（1536 维）
_embeddings_client = DashScopeEmbeddings(
    model="text-embedding-v2",
    dashscope_api_key=_QWEN_API_KEY,
)


def get_embedding(text: str) -> np.ndarray:
    """
    调用 Qwen DashScope text-embedding-v2，返回 1536 维 float32 向量。
    """
    vec: List[float] = _embeddings_client.embed_query(text)
    return np.asarray(vec, dtype=np.float32)


__all__ = ["get_embedding"]

