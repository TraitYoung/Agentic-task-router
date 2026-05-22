import asyncio

from schemas.trace import TraceStep


class FakeStore:
    def __init__(self):
        self.saved_specs = []
        self.saved_issues = []

    def search_specs(self, query, mode="", limit=5):
        return [
            {
                "goal": "实现登录流程",
                "user_stories": '["用户可以登录", "用户可以退出"]',
                "modules": '["auth api", "login page"]',
            }
        ]

    def get_top_issues(self, limit=8):
        return [
            {
                "issue_type": "architecture",
                "issue_text": "main.py 职责过多",
                "frequency": 3,
            }
        ]

    def save_spec(self, **kwargs):
        self.saved_specs.append(kwargs)

    def save_issues(self, **kwargs):
        self.saved_issues.append(kwargs)

    def search_knowledge(self, query, limit=5):
        return []


def test_spec_retrieval_context_formats_prior_specs():
    from services.retrieval_context import build_retrieval_context

    context = build_retrieval_context(FakeStore(), mode="spec", text="登录")

    assert "目标:实现登录流程" in context
    assert "用户故事:用户可以登录, 用户可以退出" in context
    assert "模块:auth api, login page" in context


def test_review_retrieval_context_formats_top_issues():
    from services.retrieval_context import build_retrieval_context

    context = build_retrieval_context(FakeStore(), mode="review", text="ignored")

    assert "高频问题模式" in context
    assert "[architecture] main.py 职责过多" in context
    assert "出现 3 次" in context


def test_pipeline_memory_saves_spec_and_review_outputs():
    from services.pipeline_memory import save_pipeline_memory

    store = FakeStore()
    spec_trace = [
        {
            "summary": {
                "profile": "web_app",
                "discovery": {"goal": "构建聊天应用", "user_stories": ["发消息"]},
            }
        },
        {"summary": {"sprint_design": {"modules": ["api", "ui"]}}},
    ]
    review_trace = [
        {
            "summary": {
                "profile": "api_service",
                "reverse_engineer": {
                    "architecture_issues": ["路由层过重"],
                    "code_quality_issues": ["错误处理不一致"],
                    "improvement_plan": ["抽 service", "统一异常"],
                },
            }
        }
    ]

    save_pipeline_memory(store, mode="spec", trace_raw=spec_trace, user_text="做聊天")
    save_pipeline_memory(store, mode="review", trace_raw=review_trace, user_text="code")

    assert store.saved_specs[0]["profile"] == "web_app"
    assert store.saved_specs[0]["goal"] == "构建聊天应用"
    assert store.saved_specs[0]["modules"] == ["api", "ui"]
    assert store.saved_issues[0]["profile"] == "api_service"
    assert store.saved_issues[0]["issues"] == [
        {"type": "architecture", "text": "路由层过重", "suggestion": "抽 service"},
        {"type": "code_quality", "text": "错误处理不一致", "suggestion": "统一异常"},
    ]


class FakeSessionCache:
    def __init__(self):
        self.turns = []

    def append_turn(self, *, session_id, user_text, assistant_text):
        self.turns.append(
            {
                "session_id": session_id,
                "user_text": user_text,
                "assistant_text": assistant_text,
            }
        )


class FakePipeline:
    summary = "summary"
    artifact_md = "# md"
    artifact_path = "output/chats/spec.md"
    artifact_filename = "spec.md"
    steps = [
        {
            "index": 1,
            "node": "workflow.se.discovery",
            "ts": "2026-01-01T00:00:00+00:00",
            "duration_ms": 1.0,
            "keys_written": [],
            "summary": {"profile": "web_app"},
        }
    ]


def test_chat_turn_runner_records_session_and_emits_stream_meta():
    from services.chat_turns import ChatTurnRunner

    session_cache = FakeSessionCache()
    store = FakeStore()

    runner = ChatTurnRunner(
        store_factory=lambda: store,
        session_cache=session_cache,
        resolve_llm=lambda step_id, fallback: object(),
        run_spec=lambda text, llm, retrieval_context="": FakePipeline(),
        run_review=lambda text, llm, retrieval_context="": FakePipeline(),
        run_spec_stream=lambda text, llm, retrieval_context="", event_queue=None: FakePipeline(),
        run_review_stream=lambda text, llm, retrieval_context="", event_queue=None: FakePipeline(),
    )

    result = runner.execute("spec", "hello", "sid-1")

    assert result.reply == "summary"
    assert session_cache.turns[0]["session_id"] == "sid-1"
    assert [TraceStep.model_validate(s).node for s in result.trace_raw] == [
        "workflow.se.discovery"
    ]

    async def collect():
        events = []
        async for event in runner.execute_stream("spec", "hello", "sid-2"):
            events.append(event)
        return events

    events = asyncio.run(collect())
    assert events[-1] == {"type": "done"}
    assert any(event["type"] == "artifact" for event in events)
    assert any(event["type"] == "meta" and event["mode"] == "spec" for event in events)
