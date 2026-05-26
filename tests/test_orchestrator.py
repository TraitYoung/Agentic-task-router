"""orchestrator：implementation + delivery 并行后再生成 test_code；交互式 checkpoint。"""

import asyncio
from unittest.mock import MagicMock, patch

from agents.dev_pipeline.orchestrator import (
    run_dev_pipeline,
    run_dev_pipeline_interactive_continue,
    run_dev_pipeline_interactive_start,
    run_dev_pipeline_stream,
)
from schemas.workflows import (
    DevCodeSketch,
    DevOutline,
    DevTaskSpec,
    DevTestBundle,
    DevTestFile,
    DevTestsChangelog,
)


def _spec():
    return DevTaskSpec(goal="g", user_stories=["s"])


def _outline():
    return DevOutline(backlog_mvp_ordered=["a"])


def _sketch():
    return DevCodeSketch(language="python", code="x = 1", notes="")


def _delivery():
    return DevTestsChangelog(test_cases=["t1"], definition_of_done=["d1"])


def _bundle():
    return DevTestBundle(files=[DevTestFile(path="tests/test_x.py", code="pass")])


@patch("agents.dev_pipeline.orchestrator.run_merge_step", return_value="merged")
@patch("agents.dev_pipeline.orchestrator.run_test_code_step")
@patch("agents.dev_pipeline.orchestrator.run_delivery_step")
@patch("agents.dev_pipeline.orchestrator.run_implementation_step")
@patch("agents.dev_pipeline.orchestrator.run_sprint_step")
@patch("agents.dev_pipeline.orchestrator.run_discovery_step")
def test_pipeline_parallel_phase_and_real_sketch_for_test_code(
    mock_discovery,
    mock_sprint,
    mock_impl,
    mock_delivery,
    mock_test_code,
    mock_merge,
):
    spec = _spec()
    outline = _outline()
    sketch = _sketch()
    delivery = _delivery()
    bundle = _bundle()

    mock_discovery.return_value = spec
    mock_sprint.return_value = outline
    mock_impl.return_value = sketch
    mock_delivery.return_value = delivery
    mock_test_code.return_value = bundle

    result = run_dev_pipeline("记账 app", MagicMock())

    mock_impl.assert_called_once()
    mock_delivery.assert_called_once()
    call_kwargs = mock_delivery.call_args.kwargs
    assert "sketch" not in call_kwargs
    mock_test_code.assert_called_once()
    assert mock_test_code.call_args.kwargs["sketch"] is sketch
    mock_merge.assert_called_once()

    assert "测试覆盖" in result.summary
    assert "## Generated Test Files" in result.artifact_md
    nodes = [s["node"] for s in result.steps]
    assert nodes.index("workflow.se.implementation_sketch") < nodes.index("workflow.se.test_code")
    assert nodes.index("workflow.se.delivery_review") < nodes.index("workflow.se.test_code")
    assert nodes.index("workflow.se.test_code") < nodes.index("workflow.se.merge")


class _FakeSessionCache:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def save_checkpoint(self, session_id: str, payload: dict) -> str:
        cp_id = payload["checkpoint_id"]
        self._store[cp_id] = payload
        return cp_id

    def get_checkpoint(self, checkpoint_id: str):
        return self._store.get(checkpoint_id)

    def delete_checkpoint(self, checkpoint_id: str, session_id: str | None = None):
        self._store.pop(checkpoint_id, None)


@patch("agents.dev_pipeline.orchestrator.run_discovery_step")
def test_interactive_start_pauses_after_discovery(mock_discovery):
    spec = _spec()
    mock_discovery.return_value = spec
    queue = asyncio.Queue()
    cache = _FakeSessionCache()

    outcome = run_dev_pipeline_interactive_start(
        "记账 app",
        MagicMock(),
        event_queue=queue,
        session_id="sess-1",
        session_cache=cache,
    )

    assert outcome.status == "paused"
    assert outcome.waiting_after == "discovery"
    assert outcome.checkpoint_id

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    types = [e["type"] for e in events]
    assert "partial" in types
    assert "choice" in types
    assert "paused" in types


@patch("agents.dev_pipeline.orchestrator.run_merge_step", return_value="merged")
@patch("agents.dev_pipeline.orchestrator.run_test_code_step")
@patch("agents.dev_pipeline.orchestrator.run_delivery_step")
@patch("agents.dev_pipeline.orchestrator.run_implementation_step")
@patch("agents.dev_pipeline.orchestrator.run_sprint_step")
@patch("agents.dev_pipeline.orchestrator.run_discovery_step")
def test_interactive_continue_runs_next_step_with_direction(
    mock_discovery,
    mock_sprint,
    mock_impl,
    mock_delivery,
    mock_test_code,
    mock_merge,
):
    spec = _spec()
    outline = _outline()
    mock_discovery.return_value = spec
    mock_sprint.return_value = outline

    cache = _FakeSessionCache()
    queue = asyncio.Queue()
    start = run_dev_pipeline_interactive_start(
        "app",
        MagicMock(),
        event_queue=queue,
        session_id="sess-1",
        session_cache=cache,
    )

    while not queue.empty():
        queue.get_nowait()

    outcome = run_dev_pipeline_interactive_continue(
        start.checkpoint_id,
        "B",
        MagicMock(),
        event_queue=queue,
        session_id="sess-1",
        session_cache=cache,
    )

    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    types = [e["type"] for e in events]
    assert "ack" in types
    ack = next(e for e in events if e["type"] == "ack")
    assert ack["next_step"] == "sprint"
    assert ack["choice"] == "B"

    assert outcome.status == "paused"
    assert outcome.waiting_after == "sprint"
    mock_sprint.assert_called_once()
    hints = mock_sprint.call_args.kwargs.get("direction_hints") or []
    assert len(hints) == 1


@patch("agents.dev_pipeline.orchestrator.run_merge_step", return_value="merged")
@patch("agents.dev_pipeline.orchestrator.run_test_code_step")
@patch("agents.dev_pipeline.orchestrator.run_delivery_step")
@patch("agents.dev_pipeline.orchestrator.run_implementation_step")
@patch("agents.dev_pipeline.orchestrator.run_sprint_step")
@patch("agents.dev_pipeline.orchestrator.run_discovery_step")
def test_stream_pipeline_keeps_serial_order_and_status_events(
    mock_discovery,
    mock_sprint,
    mock_impl,
    mock_delivery,
    mock_test_code,
    mock_merge,
):
    spec = _spec()
    outline = _outline()
    sketch = _sketch()
    delivery = _delivery()
    bundle = _bundle()

    mock_discovery.return_value = spec
    mock_sprint.return_value = outline
    mock_impl.return_value = sketch
    mock_delivery.return_value = delivery
    mock_test_code.return_value = bundle

    queue = asyncio.Queue()
    result = run_dev_pipeline_stream("璁拌处 app", MagicMock(), event_queue=queue)

    mock_test_code.assert_called_once()
    assert mock_test_code.call_args.kwargs.get("stream_callback") is not None

    status_steps = []
    while not queue.empty():
        event = queue.get_nowait()
        if event["type"] == "status":
            status_steps.append(event["step"])

    assert "profile" in status_steps
    assert "discovery" in status_steps
    assert "merge" in status_steps

    nodes = [s["node"] for s in result.steps]
    assert nodes == [
        "workflow.se.discovery",
        "workflow.se.sprint_design",
        "workflow.se.implementation_sketch",
        "workflow.se.delivery_review",
        "workflow.se.test_code",
        "workflow.se.merge",
    ]
