"""聊天摘要与 SPEC.md / REVIEW.md 实现包组装。"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping

from config.context_budget import clip_text
from schemas.workflows import (
    DevCodeSketch,
    DevOutline,
    DevTaskSpec,
    DevTestBundle,
    DevTestsChangelog,
    ReverseEngineerSpec,
    to_implementation_prompt,
    to_review_prompt,
    to_test_prompt,
)

IMPLEMENTATION_PROMPT_HEADING = "## Cursor / Copilot — Implementation Prompt"
TEST_PROMPT_HEADING = "## Cursor / Copilot — Test Prompt"
GENERATED_TEST_FILES_HEADING = "## Generated Test Files"
REVIEW_PROMPT_HEADING = "## Cursor / Copilot — Improvement Prompt"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bullet_list(items: list[str], *, limit: int) -> str:
    if not items:
        return "- （无）"
    return "\n".join(f"- {x}" for x in items[:limit])


def _numbered_list(items: list[str], *, limit: int) -> str:
    if not items:
        return "1. （无）"
    return "\n".join(f"{i + 1}. {x}" for i, x in enumerate(items[:limit]))


def _lang_from_path(path: str, fallback: str = "text") -> str:
    lower = path.lower()
    if lower.endswith((".ts", ".tsx")):
        return "typescript"
    if lower.endswith(".py"):
        return "python"
    if lower.endswith((".js", ".jsx")):
        return "javascript"
    if lower.endswith(".go"):
        return "go"
    return fallback


def _format_generated_test_files(bundle: DevTestBundle | None) -> str:
    if bundle is None or not bundle.files:
        return ""
    parts: list[str] = [GENERATED_TEST_FILES_HEADING, ""]
    lang_fallback = "typescript"
    for item in bundle.files:
        if not item.path.strip() and not item.code.strip():
            continue
        lang = _lang_from_path(item.path, lang_fallback)
        parts.extend(
            [
                f"### {item.path or 'tests/example.test.ts'}",
                "",
                f"```{lang}",
                item.code.strip() or "// （测试草稿为空，请按 Test Prompt 编写）",
                "```",
                "",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def format_test_bundle_plain(bundle: DevTestBundle | None) -> str:
    """合并所有测试文件为纯文本，供「复制测试代码」使用。"""
    if bundle is None or not bundle.files:
        return ""
    chunks: list[str] = []
    for item in bundle.files:
        if not item.code.strip():
            continue
        header = f"// {item.path}\n" if item.path.strip() else ""
        chunks.append(f"{header}{item.code.strip()}")
    return "\n\n".join(chunks)


def build_spec_artifact_md(
    *,
    spec: DevTaskSpec,
    outline: DevOutline,
    sketch: DevCodeSketch,
    delivery: DevTestsChangelog,
    merged_notes: str,
    profile: Mapping[str, Any],
    test_bundle: DevTestBundle | None = None,
) -> str:
    profile_name = str(profile.get("name", "general"))
    profile_focus = "、".join(profile.get("output_focus", []) or [])
    impl_prompt = to_implementation_prompt(spec, outline)
    test_prompt = to_test_prompt(delivery)
    lang = sketch.language or "text"
    code_block = sketch.code.strip() or "// （草案为空，请按 Implementation Prompt 实现）"

    appendix = [
        "### User stories",
        _bullet_list(spec.user_stories, limit=6),
        "",
        "### Acceptance criteria",
        _bullet_list(spec.acceptance_criteria, limit=6),
        "",
        "### Modules",
        _bullet_list(outline.modules, limit=12),
        "",
        "### Risks",
        _bullet_list(outline.risks, limit=6),
        "",
        "### Definition of done",
        _bullet_list(delivery.definition_of_done, limit=8),
    ]

    test_files_section = _format_generated_test_files(test_bundle)
    sections = [
        "# SpecForge · Implementation Pack",
        "",
        "## Meta",
        f"- profile: `{profile_name}`",
        f"- focus: {profile_focus or '—'}",
        f"- stack: {spec.stack_hint or '—'}",
        f"- generated_at: {_now_iso()}",
        "",
        "## Summary",
        f"**Goal:** {spec.goal}",
        "",
        f"**MVP slice:** {spec.mvp_sprint_goal or '—'}",
        "",
        "**Top backlog:**",
        _numbered_list(outline.backlog_mvp_ordered, limit=8),
        "",
        IMPLEMENTATION_PROMPT_HEADING,
        "",
        impl_prompt,
        "",
        f"## Starter Code ({lang})",
        "",
        f"```{lang}",
        code_block,
        "```",
        "",
        sketch.notes.strip(),
        "",
        TEST_PROMPT_HEADING,
        "",
        test_prompt,
        "",
    ]
    if test_files_section:
        sections.extend([test_files_section, ""])
    sections.extend(
        [
            "## Release Notes",
            "",
            merged_notes.strip(),
            "",
            "## Appendix",
            "",
            "\n".join(appendix),
            "",
        ]
    )
    return "\n".join(sections)


def build_spec_chat_summary(
    *,
    spec: DevTaskSpec,
    outline: DevOutline,
    delivery: DevTestsChangelog,
    merged_notes: str,
    profile: Mapping[str, Any],
    test_bundle: DevTestBundle | None = None,
) -> str:
    profile_name = str(profile.get("name", "general"))
    release = clip_text(merged_notes.strip(), 1200)
    title = spec.goal.split("。")[0].split(".")[0][:60] or "工程规格"
    test_count = len(delivery.test_cases)
    file_count = len(test_bundle.files) if test_bundle else 0
    test_hint = f"含 {file_count} 个测试文件草稿" if file_count else "含测试 Prompt"

    return "\n".join(
        [
            f"## {title} — 已生成",
            "",
            f"**画像:** `{profile_name}`",
            "",
            f"**目标:** {spec.goal}",
            "",
            f"**本迭代 MVP:** {spec.mvp_sprint_goal or '—'}",
            "",
            "**待办（前 5 条）:**",
            _numbered_list(outline.backlog_mvp_ordered, limit=5),
            "",
            f"**测试覆盖（{test_count} 条，前 5 条）:**",
            _numbered_list(delivery.test_cases, limit=5),
            "",
            "**DoD（前 3 条）:**",
            _bullet_list(delivery.definition_of_done, limit=3),
            "",
            "**风险（前 3 条）:**",
            _bullet_list(outline.risks, limit=3),
            "",
            "**发布说明:**",
            release,
            "",
            "---",
            f"完整 **SPEC.md** 已就绪（{test_hint}）。请使用下方按钮 **复制实现 Prompt** / **复制测试 Prompt** / **下载 SPEC.md**。",
        ]
    )


def build_review_artifact_md(*, spec: ReverseEngineerSpec, profile: Mapping[str, Any]) -> str:
    profile_name = str(profile.get("name", "general"))
    review_prompt = to_review_prompt(spec)
    return "\n".join(
        [
            "# SpecForge · Code Review Pack",
            "",
            "## Meta",
            f"- profile: `{profile_name}`",
            f"- generated_at: {_now_iso()}",
            "",
            "## Inferred goal",
            spec.inferred_goal or "—",
            "",
            "## User stories",
            _bullet_list(spec.inferred_user_stories, limit=6),
            "",
            "## Architecture issues",
            _bullet_list(spec.architecture_issues, limit=8),
            "",
            "## Code quality issues",
            _bullet_list(spec.code_quality_issues, limit=8),
            "",
            "## Missing tests",
            _bullet_list(spec.missing_tests, limit=10),
            "",
            "## Improvement plan",
            _numbered_list(spec.improvement_plan, limit=6),
            "",
            REVIEW_PROMPT_HEADING,
            "",
            review_prompt,
            "",
        ]
    )


def build_review_chat_summary(*, spec: ReverseEngineerSpec, profile: Mapping[str, Any]) -> str:
    profile_name = str(profile.get("name", "general"))
    issues = spec.architecture_issues[:2] + spec.code_quality_issues[:2]
    return "\n".join(
        [
            "## 代码审查 — 已完成",
            "",
            f"**画像:** `{profile_name}`",
            "",
            f"**推测目标:** {spec.inferred_goal or '—'}",
            "",
            "**改进计划（前 5 条）:**",
            _numbered_list(spec.improvement_plan, limit=5),
            "",
            "**主要问题:**",
            _bullet_list(issues, limit=4),
            "",
            "---",
            "完整 **REVIEW.md** 已生成。请使用下方按钮复制改进 Prompt 或下载全文。",
        ]
    )


def extract_section(md: str, heading: str) -> str:
    """从 artifact markdown 提取指定 ## 标题下的正文（到下一个同级标题为止）。"""
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(md)
    return m.group(1).strip() if m else ""


def extract_implementation_prompt(artifact_md: str) -> str:
    return extract_section(artifact_md, IMPLEMENTATION_PROMPT_HEADING)


def extract_test_prompt(artifact_md: str) -> str:
    return extract_section(artifact_md, TEST_PROMPT_HEADING)


def extract_generated_test_files(artifact_md: str) -> str:
    return extract_section(artifact_md, GENERATED_TEST_FILES_HEADING)


def extract_review_prompt(artifact_md: str) -> str:
    return extract_section(artifact_md, REVIEW_PROMPT_HEADING)
