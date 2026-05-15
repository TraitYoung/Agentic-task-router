"""SpecStore 冒烟测试：验证 SQLite FTS5 存储、检索与去重。"""

import tempfile
from pathlib import Path

import pytest

from memory.spec_store import SpecStore


@pytest.fixture
def store():
    """每次测试使用独立临时数据库。"""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "test_spec_store.db"
        s = SpecStore(db_path=db_path)
        yield s
        s._conn.close()


class TestSpecSaveAndSearch:
    def test_save_and_search_spec(self, store):
        store.save_spec(
            mode="spec",
            profile="web_app",
            user_text="做一个登录页面",
            goal="实现用户登录功能",
            user_stories=["作为用户，我想登录"],
            modules=["auth", "ui"],
            full_summary="登录功能的完整规格...",
        )
        results = store.search_specs("登录", mode="spec")
        assert len(results) >= 1
        assert "用户登录" in results[0]["goal"]

    def test_search_spec_without_mode(self, store):
        store.save_spec(
            mode="spec",
            profile="api_service",
            user_text="做一个 REST API",
            goal="构建后端 API 服务",
            user_stories=["作为开发者，我想调用 API"],
            modules=["router", "controller"],
            full_summary="API 规格...",
        )
        results = store.search_specs("REST API")
        assert len(results) >= 1

    def test_search_returns_empty_for_no_match(self, store):
        store.save_spec(
            mode="spec",
            profile="web_app",
            user_text="登录页面",
            goal="登录",
            user_stories=[],
            modules=[],
            full_summary="",
        )
        results = store.search_specs("量子计算")
        assert len(results) == 0

    def test_search_respects_limit(self, store):
        for i in range(10):
            store.save_spec(
                mode="spec",
                profile="web_app",
                user_text=f"测试需求 {i}",
                goal=f"目标 {i}",
                user_stories=[f"故事 {i}"],
                modules=[f"模块 {i}"],
                full_summary="",
            )
        results = store.search_specs("测试", mode="spec", limit=5)
        assert len(results) <= 5


class TestIssueSaveAndSearch:
    def test_save_and_search_issue(self, store):
        store.save_issues(
            profile="web_app",
            issues=[
                {"type": "code_quality", "text": "缺乏错误处理", "suggestion": "添加 try/except"},
                {"type": "architecture", "text": "耦合度过高", "suggestion": "拆分为独立模块"},
            ],
        )
        results = store.search_issues("错误处理")
        assert len(results) >= 1
        assert results[0]["issue_type"] == "code_quality"

    def test_issue_dedup_increments_frequency(self, store):
        store.save_issues(
            profile="web_app",
            issues=[{"type": "code_quality", "text": "缺乏错误处理", "suggestion": ""}],
        )
        store.save_issues(
            profile="web_app",
            issues=[{"type": "code_quality", "text": "缺乏错误处理", "suggestion": ""}],
        )
        results = store.get_top_issues()
        assert len(results) == 1
        assert results[0]["frequency"] == 2

    def test_get_top_issues_orders_by_frequency(self, store):
        store.save_issues(
            profile="web_app",
            issues=[
                {"type": "code_quality", "text": "低频问题", "suggestion": ""},
            ],
        )
        store.save_issues(
            profile="web_app",
            issues=[
                {"type": "architecture", "text": "高频问题", "suggestion": ""},
            ],
        )
        store.save_issues(
            profile="web_app",
            issues=[
                {"type": "architecture", "text": "高频问题", "suggestion": ""},
            ],
        )
        store.save_issues(
            profile="web_app",
            issues=[
                {"type": "architecture", "text": "高频问题", "suggestion": ""},
            ],
        )
        top = store.get_top_issues(limit=2)
        assert top[0]["issue_text"] == "高频问题"
        assert top[0]["frequency"] == 3

    def test_search_issues_respects_profile(self, store):
        store.save_issues(
            profile="api_service",
            issues=[{"type": "architecture", "text": "API 认证缺失", "suggestion": ""}],
        )
        store.save_issues(
            profile="web_app",
            issues=[{"type": "code_quality", "text": "CSS 样式不响应", "suggestion": ""}],
        )
        results = store.search_issues("认证", profile="api_service")
        assert len(results) >= 1
        assert "认证" in results[0]["issue_text"]

    def test_search_issues_empty_query(self, store):
        store.save_issues(
            profile="web_app",
            issues=[{"type": "code_quality", "text": "测试", "suggestion": ""}],
        )
        assert store.search_issues("") == []


class TestEmptyStore:
    def test_search_specs_empty_store(self, store):
        assert store.search_specs("anything") == []

    def test_search_issues_empty_store(self, store):
        assert store.search_issues("anything") == []

    def test_get_top_issues_empty_store(self, store):
        assert store.get_top_issues() == []
