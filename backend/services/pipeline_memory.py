"""Persist useful pipeline outputs into the local memory store."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from repo_paths import REPO_ROOT

Mode = Literal["spec", "review"]

logger = logging.getLogger("specforge.pipeline_memory")


def _safe_slug(text: str, max_len: int = 24) -> str:
    line = (text.splitlines()[0] if text else "session").strip()
    if len(line) > max_len:
        line = line[:max_len]
    slug = "".join(ch for ch in line if ch not in '\\/:*?"<>|' and ord(ch) >= 32).strip()
    return slug or "session"


def save_artifact_md(
    content: str,
    user_prompt: str,
    *,
    mode: str = "spec",
) -> tuple[str, str]:
    """Write output/chats/{ts}_{slug}_SPEC.md or _REVIEW.md. Returns (filename, repo_relative_path)."""
    export_dir = REPO_ROOT / "output" / "chats"
    export_dir.mkdir(parents=True, exist_ok=True)
    suffix = "REVIEW" if mode == "review" else "SPEC"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _safe_slug(user_prompt)
    filename = f"{ts}_{slug}_{suffix}.md"
    path = export_dir / filename
    path.write_text(content, encoding="utf-8")
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    return filename, rel


def extract_profile(trace_raw: list[dict[str, Any]]) -> str:
    if trace_raw and isinstance(trace_raw[0], dict):
        return str(trace_raw[0].get("summary", {}).get("profile", ""))
    return ""


def _save_spec_result(store: Any, trace_raw: list[dict[str, Any]], user_text: str, profile: str) -> None:
    if not trace_raw:
        return

    discovery = trace_raw[0].get("summary", {}).get("discovery", {})
    sprint_design = (
        trace_raw[1].get("summary", {}).get("sprint_design", {})
        if len(trace_raw) > 1
        else {}
    )

    store.save_spec(
        mode="spec",
        profile=profile,
        user_text=user_text[:500],
        goal=str(discovery.get("goal", user_text[:200])),
        user_stories=list(discovery.get("user_stories", [])),
        modules=list(sprint_design.get("modules", [])),
        full_summary=json.dumps(
            {"discovery": discovery, "sprint": sprint_design},
            ensure_ascii=False,
        )[:4000],
    )


def _save_review_issues(store: Any, trace_raw: list[dict[str, Any]], profile: str) -> None:
    if not trace_raw:
        return

    spec = trace_raw[0].get("summary", {}).get("reverse_engineer", {})
    issues: list[dict[str, str]] = []

    for item in spec.get("architecture_issues", []):
        issues.append({"type": "architecture", "text": str(item), "suggestion": ""})
    for item in spec.get("code_quality_issues", []):
        issues.append({"type": "code_quality", "text": str(item), "suggestion": ""})

    suggestions = [str(s) for s in spec.get("improvement_plan", [])]
    for idx, issue in enumerate(issues):
        if idx < len(suggestions):
            issue["suggestion"] = suggestions[idx]

    if issues:
        store.save_issues(profile=profile, issues=issues)


def save_pipeline_memory(
    store: Any,
    *,
    mode: Mode,
    trace_raw: list[dict[str, Any]],
    user_text: str,
) -> None:
    profile = extract_profile(trace_raw)
    try:
        if mode == "review":
            _save_review_issues(store, trace_raw, profile)
        else:
            _save_spec_result(store, trace_raw, user_text, profile)
    except Exception as exc:
        logger.warning("save to spec_store failed: %s", exc)

