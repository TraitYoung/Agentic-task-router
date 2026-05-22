"""orchestrator：串行 implementation → delivery → test_code。"""

import asyncio
from unittest.mock import MagicMock, patch

from agents.dev_pipeline.orchestrator import run_dev_pipeline, run_dev_pipeline_stream
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
def test_pipeline_serial_order_and_real_sketch_for_delivery(
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
    assert call_kwargs["sketch"] is sketch
    assert call_kwargs["sketch"].code == "x = 1"
    mock_test_code.assert_called_once()
    assert mock_test_code.call_args.kwargs["sketch"] is sketch
    mock_merge.assert_called_once()

    assert "测试覆盖" in result.summary
    assert "## Generated Test Files" in result.artifact_md
    nodes = [s["node"] for s in result.steps]
    assert nodes.index("workflow.se.implementation_sketch") < nodes.index("workflow.se.delivery_review")
    assert nodes.index("workflow.se.delivery_review") < nodes.index("workflow.se.test_code")
    assert nodes.index("workflow.se.test_code") < nodes.index("workflow.se.merge")


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
