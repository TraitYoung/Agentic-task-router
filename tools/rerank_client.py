"""
外部 Rerank API（Jina / SiliconFlow），避免本地 Cross-Encoder 占显存。

未配置密钥或 RERANK_DISABLED=1 时直接返回前 final_top_k 条（RRF 顺序）。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List


def _post_json(url: str, headers: Dict[str, str], body: Dict[str, Any], timeout: float = 45.0) -> Dict[str, Any]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Rerank HTTP {e.code}: {err_body}") from e


def maybe_rerank(query: str, docs: List[Dict[str, Any]], final_top_k: int) -> List[Dict[str, Any]]:
    if not docs:
        return []
    if final_top_k <= 0:
        return []

    off = os.getenv("RERANK_DISABLED", "").strip().lower() in ("1", "true", "yes", "on")
    if off:
        return docs[:final_top_k]

    provider = (os.getenv("RERANK_PROVIDER") or "jina").strip().lower()
    api_key = (
        os.getenv("RERANK_API_KEY")
        or os.getenv("JINA_API_KEY")
        or os.getenv("SILICONFLOW_API_KEY")
        or ""
    ).strip()
    if not api_key:
        return docs[:final_top_k]

    documents = [(str(d.get("content") or "").strip() or " ") for d in docs]
    top_n = min(final_top_k, len(documents))

    if provider == "siliconflow":
        url = (os.getenv("RERANK_API_URL") or "https://api.siliconflow.cn/v1/rerank").rstrip("/")
        model = os.getenv("RERANK_MODEL") or "BAAI/bge-reranker-v2-m3"
        body: Dict[str, Any] = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        url = (os.getenv("RERANK_API_URL") or "https://api.jina.ai/v1/rerank").rstrip("/")
        model = os.getenv("RERANK_MODEL") or "jina-reranker-v2-base-multilingual"
        body = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        headers = {"Authorization": f"Bearer {api_key}"}

    try:
        data = _post_json(url, headers, body)
    except Exception as e:
        print(f"[Rerank] API failed, fallback to RRF order: {e}")
        return docs[:final_top_k]

    results = data.get("results") or []
    if not isinstance(results, list) or not results:
        return docs[:final_top_k]

    indices: List[int] = []
    for item in results:
        if isinstance(item, dict) and "index" in item:
            try:
                indices.append(int(item["index"]))
            except (TypeError, ValueError):
                continue

    if not indices:
        return docs[:final_top_k]

    reordered: List[Dict[str, Any]] = []
    seen_ids: set[Any] = set()
    for i in indices:
        if 0 <= i < len(docs):
            d = docs[i]
            mid = d.get("id")
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            reordered.append(d)
    if not reordered:
        return docs[:final_top_k]

    return reordered[:final_top_k]


__all__ = ["maybe_rerank"]
