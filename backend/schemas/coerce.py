"""LLM 结构化 JSON 入库前的统一容错（截断、列表对象压平）。"""

from __future__ import annotations

import json
from typing import Any


def cap_str(v: object, max_len: int, *, default: str = "") -> str:
    if v is None:
        return default
    if isinstance(v, str) and not v.strip():
        return default
    return str(v)[:max_len]


def list_item_to_str(item: object) -> str:
    """LLM 常把列表项写成 {name, responsibility} 对象，统一压成字符串。"""
    if isinstance(item, dict):
        name = ""
        for key in ("name", "module", "title", "id", "task"):
            if item.get(key):
                name = str(item[key]).strip()
                break
        desc = ""
        for key in ("responsibility", "description", "desc", "role", "summary"):
            if item.get(key):
                desc = str(item[key]).strip()
                break
        if name and desc:
            return f"{name}: {desc}"
        if name:
            return name
        if desc:
            return desc
        return json.dumps(item, ensure_ascii=False)
    return str(item)


def normalize_str_list(v: object, *, limit: int, item_max: int) -> object:
    if not isinstance(v, list):
        return v
    return [list_item_to_str(x)[:item_max] for x in v[:limit]]
