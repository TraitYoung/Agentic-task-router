"""SpecForge 流水线冒烟测试：验证结构化输出模型、上下文预算与项目画像检测。"""

import pytest

from agents.dev_pipeline.step_agents import (
    STRUCTURED_JSON_OUTPUT_HINT,
    _append_json_output_hint,
)
from config.context_budget import clip_text, WORKFLOW_USER_TEXT_MAX_CHARS
from prompts.dev_pipeline_profiles import detect_dev_profile, GENERAL_PROFILE, WEB_APP_PROFILE, API_SERVICE_PROFILE
from schemas.workflows import (
    DevTaskSpec,
    DevOutline,
    DevCodeSketch,
    DevTestsChangelog,
    ReverseEngineerSpec,
    to_implementation_prompt,
    to_review_prompt,
    to_test_prompt,
)


class TestStructuredJsonHint:
    """千问 json_object 模式要求 messages 含 json 关键字，防止线上 400。"""

    def test_hint_contains_json_keyword(self):
        assert "json" in STRUCTURED_JSON_OUTPUT_HINT.lower()

    def test_append_adds_hint_to_system_prompt(self):
        base = "你是需求教练。只根据用户原文抽取结构化结果。"
        combined = _append_json_output_hint(base)
        assert "json" in combined.lower()
        assert base in combined


class TestContextBudget:
    def test_clip_short_text_passes_through(self):
        assert clip_text("hello", 100) == "hello"

    def test_clip_long_text_truncates(self):
        long_text = "x" * 5000
        clipped = clip_text(long_text, 1000)
        assert len(clipped) <= 1000
        assert clipped.endswith("...")

    def test_clip_zero_max_returns_unchanged(self):
        assert clip_text("hello", 0) == "hello"


class TestDevProfiles:
    def test_web_keywords_detect_web_app(self):
        profile = detect_dev_profile("用 react 和 tailwind 做一个 dashboard")
        assert profile["name"] == "web_app"
        assert "前后端分离" in profile["prompt_injection"]

    def test_api_keywords_detect_api_service(self):
        profile = detect_dev_profile("用 fastapi 写一个 rest 接口")
        assert profile["name"] == "api_service"

    def test_no_keywords_returns_general(self):
        profile = detect_dev_profile("做一个工具")
        assert profile["name"] == "general_software_engineering"


class TestDevTaskSpec:
    def test_minimal_spec(self):
        spec = DevTaskSpec(goal="做一个登录页面")
        assert spec.goal == "做一个登录页面"
        assert spec.acceptance_criteria == []

    def test_full_spec(self):
        spec = DevTaskSpec(
            goal="做一个记账 App",
            constraints=["支持多账户", "月度预算"],
            stack_hint="React + FastAPI",
            acceptance_criteria=["用户可以创建账户", "可以记录收支"],
            user_stories=["作为用户，我想记录每天的开销"],
            mvp_sprint_goal="实现基础记账功能",
            measurable_outcomes=["日活用户 > 100"],
        )
        assert len(spec.constraints) <= 8
        assert len(spec.acceptance_criteria) <= 6

    def test_max_length_rejects_excess(self):
        with pytest.raises(Exception):
            DevTaskSpec(
                goal="test",
                constraints=[f"constraint_{i}" for i in range(20)],
            )

    def test_field_validator_caps_item_length(self):
        spec = DevTaskSpec(
            goal="test",
            constraints=["x" * 1000],
            acceptance_criteria=["y" * 1000],
        )
        assert len(spec.constraints[0]) <= 400
        assert len(spec.acceptance_criteria[0]) <= 400


class TestDevOutline:
    def test_minimal_outline(self):
        outline = DevOutline()
        assert outline.modules == []
        assert outline.backlog_mvp_ordered == []

    def test_max_length_rejects_excess(self):
        with pytest.raises(Exception):
            DevOutline(modules=[f"mod_{i}" for i in range(20)])

    def test_field_validator_caps_item_length(self):
        outline = DevOutline(risks=["x" * 1000])
        assert len(outline.risks[0]) <= 400


class TestDevTestsChangelog:
    def test_minimal(self):
        delivery = DevTestsChangelog()
        assert delivery.test_cases == []


class TestReverseEngineerSpec:
    def test_minimal(self):
        spec = ReverseEngineerSpec(inferred_goal="分析这段代码")
        assert spec.inferred_goal == "分析这段代码"

    def test_max_length_rejects_excess(self):
        with pytest.raises(Exception):
            ReverseEngineerSpec(
                inferred_goal="test",
                inferred_user_stories=[f"story_{i}" for i in range(20)],
            )

    def test_field_validator_caps_item_length(self):
        spec = ReverseEngineerSpec(
            inferred_goal="test",
            architecture_issues=["x" * 1000],
            code_quality_issues=["y" * 1000],
        )
        assert len(spec.architecture_issues[0]) <= 400
        assert len(spec.code_quality_issues[0]) <= 400


class TestPromptGeneration:
    def test_implementation_prompt(self):
        spec = DevTaskSpec(goal="做一个 App", user_stories=["作为用户，我想登录"])
        outline = DevOutline(backlog_mvp_ordered=["实现登录页面", "实现 API"])
        prompt = to_implementation_prompt(spec, outline)
        assert "做一个 App" in prompt
        assert "作为用户，我想登录" in prompt
        assert "实现登录页面" in prompt

    def test_review_prompt(self):
        rev = ReverseEngineerSpec(
            inferred_goal="管理用户",
            architecture_issues=["耦合过高"],
            code_quality_issues=["命名不规范"],
            improvement_plan=["拆分模块"],
        )
        prompt = to_review_prompt(rev)
        assert "耦合过高" in prompt
        assert "命名不规范" in prompt
        assert "拆分模块" in prompt

    def test_test_prompt(self):
        delivery = DevTestsChangelog(
            test_cases=["测试登录成功", "测试登录失败"],
            definition_of_done=["所有测试通过"],
            changelog_entry="v1.0 初始版本",
        )
        prompt = to_test_prompt(delivery)
        assert "测试登录成功" in prompt
        assert "所有测试通过" in prompt
