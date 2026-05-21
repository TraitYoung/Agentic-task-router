"""artifact_pack：摘要与 SPEC.md 实现包。"""

from schemas.artifact_pack import (
    build_spec_artifact_md,
    build_spec_chat_summary,
    extract_implementation_prompt,
    extract_test_prompt,
)
from schemas.workflows import (
    DevCodeSketch,
    DevOutline,
    DevTaskSpec,
    DevTestBundle,
    DevTestFile,
    DevTestsChangelog,
)


def _minimal_spec():
    return DevTaskSpec(
        goal="做一个记账 App",
        constraints=["本地优先"],
        stack_hint="React + Dexie",
        acceptance_criteria=["可记录收支"],
        user_stories=["As a user I want to log expense"],
        mvp_sprint_goal="MVP 记账",
        measurable_outcomes=["首笔记录 ≤3 步"],
    )


def _minimal_outline():
    return DevOutline(
        modules=["db: IndexedDB"],
        backlog_mvp_ordered=["初始化工程", "实现 CRUD"],
        risks=["iOS 隐私模式"],
    )


def test_artifact_contains_implementation_prompt_and_code():
    spec = _minimal_spec()
    outline = _minimal_outline()
    sketch = DevCodeSketch(language="typescript", code="export const x = 1;", notes="vite")
    delivery = DevTestsChangelog(test_cases=["用例1"], changelog_entry="init")
    md = build_spec_artifact_md(
        spec=spec,
        outline=outline,
        sketch=sketch,
        delivery=delivery,
        merged_notes="Release: MVP ready.",
        profile={"name": "web_app", "output_focus": ["前后端"]},
    )
    assert "## Cursor / Copilot — Implementation Prompt" in md
    assert "做一个记账 App" in md
    assert "```typescript" in md
    assert "export const x = 1" in md
    assert "Release: MVP ready" in md
    assert '"goal":' not in md


def test_artifact_includes_generated_test_files():
    spec = _minimal_spec()
    outline = _minimal_outline()
    delivery = DevTestsChangelog()
    bundle = DevTestBundle(
        files=[DevTestFile(path="src/__tests__/app.test.ts", code="expect(1).toBe(1);")]
    )
    md = build_spec_artifact_md(
        spec=spec,
        outline=outline,
        sketch=DevCodeSketch(),
        delivery=delivery,
        merged_notes="ok",
        profile={"name": "general", "output_focus": []},
        test_bundle=bundle,
    )
    assert "## Generated Test Files" in md
    assert "src/__tests__/app.test.ts" in md
    assert "expect(1).toBe(1)" in md


def test_chat_summary_lists_test_cases_and_dod():
    spec = _minimal_spec()
    outline = _minimal_outline()
    delivery = DevTestsChangelog(
        test_cases=["登录流程", "记账 CRUD", "导出 CSV"],
        definition_of_done=["单元测试通过", "无 P0 bug"],
    )
    summary = build_spec_chat_summary(
        spec=spec,
        outline=outline,
        delivery=delivery,
        merged_notes="发布说明",
        profile={"name": "general", "output_focus": []},
    )
    assert "测试覆盖" in summary
    assert "登录流程" in summary
    assert "单元测试通过" in summary
    assert "复制测试 Prompt" in summary


def test_chat_summary_is_shorter_than_artifact():
    spec = _minimal_spec()
    outline = _minimal_outline()
    delivery = DevTestsChangelog()
    artifact = build_spec_artifact_md(
        spec=spec,
        outline=outline,
        sketch=DevCodeSketch(),
        delivery=delivery,
        merged_notes="x" * 500,
        profile={"name": "general", "output_focus": []},
    )
    summary = build_spec_chat_summary(
        spec=spec,
        outline=outline,
        delivery=delivery,
        merged_notes="x" * 500,
        profile={"name": "general", "output_focus": []},
    )
    assert len(summary) < len(artifact)
    assert len(summary) < 2500
    assert "SPEC.md" in summary


def test_extract_implementation_prompt_section():
    md = "## Cursor / Copilot — Implementation Prompt\n\nHello prompt\n\n## Starter Code"
    assert extract_implementation_prompt(md) == "Hello prompt"


def test_extract_test_prompt_section():
    md = "## Cursor / Copilot — Test Prompt\n\nTest body\n\n## Release Notes"
    assert extract_test_prompt(md) == "Test body"
