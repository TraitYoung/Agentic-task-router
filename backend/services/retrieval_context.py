"""Build retrieval context snippets for pipeline prompts."""

from __future__ import annotations

import json
from typing import Any, Literal

Mode = Literal["spec", "review"]


def parse_json_list(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _spec_context(store: Any, text: str) -> str:
    past_specs = store.search_specs(text, mode="spec", limit=3)
    if not past_specs:
        return ""

    parts: list[str] = []
    for spec in past_specs:
        stories = parse_json_list(spec.get("user_stories", "[]"))
        modules = parse_json_list(spec.get("modules", "[]"))
        parts.append(
            f"- 目标:{spec['goal']}\n"
            f"  用户故事:{', '.join(stories) if stories else '无'}\n"
            f"  模块:{', '.join(modules) if modules else '无'}"
        )
    return "\n".join(parts)


def _review_context(store: Any) -> str:
    top_issues = store.get_top_issues(limit=8)
    if not top_issues:
        return ""
    return "高频问题模式（按频率降序）:\n" + "\n".join(
        f"- [{issue['issue_type']}] {issue['issue_text']}（出现 {issue['frequency']} 次）"
        for issue in top_issues
    )


def build_retrieval_context(store: Any, *, mode: Mode, text: str) -> str:
    if mode == "review":
        return _review_context(store)
    return _spec_context(store, text)

