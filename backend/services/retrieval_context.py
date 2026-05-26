"""RAG 检索上下文构建器。

检索链路：
  1. 用户输入（spec 模式：产品想法；review 模式：代码片段）
  2. SQLite FTS5 全文检索 — 匹配历史 spec（goal/user_stories/modules）或历史 review issues
  3. 检索结果注入 pipeline prompt 的 retrieval_context 字段
  4. 各 Step Agent 在 system prompt 中接收该上下文，作为"历史经验"辅助生成

spec 模式下检索 Top-3 相似历史 spec，提取其 goal + user_stories + modules 作为参考。
review 模式下检索 Top-8 高频 issue 及其 suggestion，帮助发现重复问题模式。

FTS5 对中文分词有限（内置 tokenizer），自动降级到 LIKE 通配符模糊匹配，
确保中文查询不因分词问题漏检。
"""

from __future__ import annotations

import json
from typing import Any, Literal

from services.project_knowledge import ensure_project_knowledge_indexed

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


def _knowledge_context(store: Any, text: str) -> str:
    docs = store.search_knowledge(text, limit=3)
    if not docs:
        return ""
    parts: list[str] = []
    for doc in docs:
        snippet = doc["content"][:300]
        source = doc.get("source") or "knowledge"
        parts.append(f"- [{doc['title']}] source={source}\n  {snippet}")
    return "相关知识文档（README/docs/API/codebase/history index）:\n" + "\n".join(parts)


def build_retrieval_context(store: Any, *, mode: Mode, text: str) -> str:
    ensure_project_knowledge_indexed(store)
    parts: list[str] = []
    if mode == "review":
        ctx = _review_context(store)
    else:
        ctx = _spec_context(store, text)
    if ctx:
        parts.append(ctx)
    kn_ctx = _knowledge_context(store, text)
    if kn_ctx:
        parts.append(kn_ctx)
    return "\n\n".join(parts)
