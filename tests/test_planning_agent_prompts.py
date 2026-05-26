from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PlanningAgentPromptTests(unittest.TestCase):
    def test_discovery_prompt_requires_feature_coverage_dimensions(self):
        source = (ROOT / "backend" / "agents" / "dev_pipeline" / "step_agents.py").read_text(
            encoding="utf-8"
        )
        discovery_fn = source[source.index("def run_discovery_step") : source.index("def run_sprint_step")]

        for phrase in (
            "用户角色",
            "核心对象",
            "主流程",
            "异常/空状态",
            "权限",
            "验收标准必须可测试",
        ):
            self.assertIn(phrase, discovery_fn)

    def test_sprint_prompt_requires_functional_slices_and_backlog_shape(self):
        source = (ROOT / "backend" / "agents" / "dev_pipeline" / "step_agents.py").read_text(
            encoding="utf-8"
        )
        sprint_fn = source[source.index("def run_sprint_step") : source.index("def run_implementation_step")]

        for phrase in (
            "功能切片",
            "页面/API/数据",
            "CRUD",
            "状态流转",
            "错误处理",
            "每条 backlog",
        ):
            self.assertIn(phrase, sprint_fn)

    def test_planning_schemas_allow_richer_feature_lists(self):
        source = (ROOT / "backend" / "schemas" / "workflows.py").read_text(encoding="utf-8")

        self.assertIn("acceptance_criteria: List[str] = Field(default_factory=list, max_length=8)", source)
        self.assertIn("user_stories: List[str] = Field(", source)
        self.assertIn("max_length=8", source)
        self.assertIn("backlog_mvp_ordered: List[str] = Field(", source)
        self.assertIn("max_length=12", source)


if __name__ == "__main__":
    unittest.main()
