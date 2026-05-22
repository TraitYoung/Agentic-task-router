"""A 方向 orchestrator：discovery → sprint → implementation → delivery → test_code → merge。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, NamedTuple

from config.context_budget import WORKFLOW_USER_TEXT_MAX_CHARS, clip_text
from prompts.dev_pipeline_profiles import detect_dev_profile
from schemas.artifact_pack import (
    build_review_artifact_md,
    build_review_chat_summary,
    build_spec_artifact_md,
    build_spec_chat_summary,
)
from services.pipeline_memory import save_artifact_md

logger = logging.getLogger("specforge.orchestrator")

from .step_agents import (
    DELIVERY_CFG,
    DISCOVERY_CFG,
    IMPLEMENT_CFG,
    MERGE_CFG,
    REVERSE_ENGINEER_CFG,
    SPRINT_CFG,
    TEST_CODE_CFG,
    run_delivery_step,
    run_discovery_step,
    run_implementation_step,
    run_merge_step,
    run_reverse_engineer_step,
    run_sprint_step,
    run_test_code_step,
)


class PipelineResult(NamedTuple):
    summary: str
    artifact_md: str
    artifact_filename: str
    artifact_path: str
    steps: list[dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estimate_tokens(value: Any) -> int:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    return max(1, len(text) // 4) if text else 0


def _memory_mb() -> float:
    try:
        import os
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024, 2)
    except Exception:
        return 0.0


def _trace_step(idx: int, node: str, t_ms: float, summary: dict[str, Any]) -> dict[str, Any]:
    metrics = {
        "estimated_tokens": _estimate_tokens(summary),
        "memory_mb": _memory_mb(),
    }
    enriched_summary = {**summary, "_metrics": metrics}
    logger.info(
        "pipeline step done: node=%s duration_ms=%.2f estimated_tokens=%d memory_mb=%.2f",
        node,
        t_ms,
        metrics["estimated_tokens"],
        metrics["memory_mb"],
    )
    return {
        "index": idx,
        "node": node,
        "ts": _now_iso(),
        "duration_ms": round(t_ms, 2),
        "keys_written": [],
        "summary": enriched_summary,
    }


def _delivery_trace_summary(delivery) -> dict[str, Any]:
    d = delivery.model_dump()
    d["test_cases_count"] = len(delivery.test_cases)
    return d


def _finish_spec(
    *,
    user_text: str,
    spec,
    outline,
    sketch,
    delivery,
    test_bundle,
    merged_notes: str,
    profile: dict[str, Any],
    steps: list[dict[str, Any]],
) -> PipelineResult:
    artifact_md = build_spec_artifact_md(
        spec=spec,
        outline=outline,
        sketch=sketch,
        delivery=delivery,
        merged_notes=merged_notes,
        profile=profile,
        test_bundle=test_bundle,
    )
    summary = build_spec_chat_summary(
        spec=spec,
        outline=outline,
        delivery=delivery,
        merged_notes=merged_notes,
        profile=profile,
        test_bundle=test_bundle,
    )
    filename, rel_path = save_artifact_md(artifact_md, user_text, mode="spec")
    return PipelineResult(summary, artifact_md, filename, rel_path, steps)


def _finish_review(
    *,
    user_text: str,
    spec,
    profile: dict[str, Any],
    steps: list[dict[str, Any]],
) -> PipelineResult:
    artifact_md = build_review_artifact_md(spec=spec, profile=profile)
    summary = build_review_chat_summary(spec=spec, profile=profile)
    filename, rel_path = save_artifact_md(artifact_md, user_text, mode="review")
    return PipelineResult(summary, artifact_md, filename, rel_path, steps)


def _put(q: asyncio.Queue | None, event: dict[str, Any]) -> None:
    if q is not None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


_DEV_STATUS_TEXT: dict[str, tuple[str, str]] = {
    "profile": ("profile", "识别为 {profile} 项目，开始分析..."),
    "discovery": ("discovery", "正在分析需求，拆解用户故事与验收标准..."),
    "discovery_done": ("discovery_done", "需求分析完成"),
    "sprint": ("sprint", "正在设计架构，拆分模块与 Sprint 待办..."),
    "sprint_done": ("sprint_done", "架构设计完成"),
    "implementation": ("implementation", "正在生成实现草案..."),
    "implementation_done": ("implementation_done", "实现草案完成"),
    "delivery": ("delivery", "正在对照代码草案编写测试方案..."),
    "delivery_done": ("delivery_done", "测试方案完成"),
    "test_code": ("test_code", "正在生成可粘贴的测试代码草案..."),
    "test_code_done": ("test_code_done", "测试代码草案完成"),
    "merge": ("merge", "正在汇总发布说明并生成实现包..."),
}


def _emit_status(event_queue: asyncio.Queue | None, key: str, *, profile_name: str = "") -> None:
    step, text = _DEV_STATUS_TEXT[key]
    _put(event_queue, {"type": "status", "step": step, "text": text.format(profile=profile_name)})


def _run_dev_pipeline_core(
    user_text: str,
    llm,
    *,
    retrieval_context: str = "",
    event_queue: asyncio.Queue | None = None,
) -> PipelineResult:
    """Run the forward engineering pipeline; optionally publish status events."""
    t_total = time.perf_counter()
    clipped = clip_text(user_text.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    logger.info(
        "dev_pipeline start: profile=%s text_len=%d retrieval=%s",
        profile["name"],
        len(clipped),
        "yes" if retrieval_context else "no",
    )
    profile_injection = profile["prompt_injection"]
    profile_focus = "、".join(profile["output_focus"])
    steps: list[dict[str, Any]] = []

    _emit_status(event_queue, "profile", profile_name=profile["name"])
    _emit_status(event_queue, "discovery")
    t0 = time.perf_counter()
    spec = run_discovery_step(
        llm=llm,
        raw_text=clipped,
        profile_injection=profile_injection,
        retrieval_context=retrieval_context,
    )
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(1, DISCOVERY_CFG.node, t1, {"profile": profile["name"], "discovery": spec.model_dump()}))
    _emit_status(event_queue, "discovery_done")

    _emit_status(event_queue, "sprint")
    t0 = time.perf_counter()
    outline = run_sprint_step(llm=llm, discovery=spec, profile_focus=profile_focus)
    t2 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(2, SPRINT_CFG.node, t2, {"profile": profile["name"], "sprint_design": outline.model_dump()}))
    _emit_status(event_queue, "sprint_done")

    _emit_status(event_queue, "implementation")
    t0 = time.perf_counter()
    sketch = run_implementation_step(
        llm=llm,
        discovery=spec,
        sprint=outline,
        profile_injection=profile_injection,
    )
    t_impl = (time.perf_counter() - t0) * 1000
    steps.append(
        _trace_step(
            3,
            IMPLEMENT_CFG.node,
            t_impl,
            {"profile": profile["name"], "impl_then_delivery": True, "sketch": sketch.model_dump()},
        )
    )
    _emit_status(event_queue, "implementation_done")

    _emit_status(event_queue, "delivery")
    t0 = time.perf_counter()
    delivery = run_delivery_step(
        llm=llm,
        discovery=spec,
        sprint=outline,
        sketch=sketch,
        profile_focus=profile_focus,
    )
    t_del = (time.perf_counter() - t0) * 1000
    steps.append(
        _trace_step(
            4,
            DELIVERY_CFG.node,
            t_del,
            {"profile": profile["name"], "impl_then_delivery": True, "delivery": _delivery_trace_summary(delivery)},
        )
    )
    _emit_status(event_queue, "delivery_done")

    _emit_status(event_queue, "test_code")
    t0 = time.perf_counter()
    test_bundle = run_test_code_step(
        llm=llm,
        discovery=spec,
        sprint=outline,
        sketch=sketch,
        delivery=delivery,
        profile_focus=profile_focus,
    )
    t_test = (time.perf_counter() - t0) * 1000
    steps.append(
        _trace_step(
            5,
            TEST_CODE_CFG.node,
            t_test,
            {
                "profile": profile["name"],
                "test_bundle": test_bundle.model_dump(),
                "test_files_count": len(test_bundle.files),
            },
        )
    )
    _emit_status(event_queue, "test_code_done")

    _emit_status(event_queue, "merge")
    t0 = time.perf_counter()
    merged_notes = run_merge_step(
        llm=llm,
        discovery=spec,
        sprint=outline,
        sketch=sketch,
        delivery=delivery,
    )
    t4 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(6, MERGE_CFG.node, t4, {"profile": profile["name"], "merge_preview": merged_notes[:300]}))

    logger.info(
        "dev_pipeline done: profile=%s steps=%d total_ms=%d",
        profile["name"],
        len(steps),
        int((time.perf_counter() - t_total) * 1000),
    )
    return _finish_spec(
        user_text=clipped,
        spec=spec,
        outline=outline,
        sketch=sketch,
        delivery=delivery,
        test_bundle=test_bundle,
        merged_notes=merged_notes,
        profile=profile,
        steps=steps,
    )


def run_dev_pipeline(user_text: str, llm, *, retrieval_context: str = "") -> PipelineResult:
    """Return chat summary, SPEC.md artifact, and trace for the forward workflow."""
    return _run_dev_pipeline_core(user_text, llm, retrieval_context=retrieval_context)


def run_reverse_engineer(code: str, llm, *, retrieval_context: str = "") -> PipelineResult:
    """逆向工程：代码 → 摘要 + REVIEW.md + trace。"""
    t_total = time.perf_counter()
    clipped = clip_text(code.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    logger.info(
        "reverse_engineer start: profile=%s code_len=%d retrieval=%s",
        profile["name"],
        len(clipped),
        "yes" if retrieval_context else "no",
    )
    profile_injection = profile["prompt_injection"]
    steps: list[dict[str, Any]] = []

    t0 = time.perf_counter()
    spec = run_reverse_engineer_step(
        llm=llm, code=clipped, profile_injection=profile_injection, retrieval_context=retrieval_context
    )
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(
        _trace_step(
            1,
            REVERSE_ENGINEER_CFG.node,
            t1,
            {"profile": profile["name"], "reverse_engineer": spec.model_dump()},
        )
    )

    logger.info(
        "reverse_engineer done: profile=%s steps=%d total_ms=%d",
        profile["name"],
        len(steps),
        int((time.perf_counter() - t_total) * 1000),
    )
    return _finish_review(user_text=clipped, spec=spec, profile=profile, steps=steps)


def run_dev_pipeline_stream(
    user_text: str, llm, *, retrieval_context: str = "", event_queue: asyncio.Queue | None = None
) -> PipelineResult:
    """Forward workflow variant that publishes progress events to event_queue."""
    return _run_dev_pipeline_core(
        user_text,
        llm,
        retrieval_context=retrieval_context,
        event_queue=event_queue,
    )


def run_reverse_engineer_stream(
    code: str, llm, *, retrieval_context: str = "", event_queue: asyncio.Queue | None = None
) -> PipelineResult:
    """逆向审查流式版。"""
    clipped = clip_text(code.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    profile_injection = profile["prompt_injection"]
    steps: list[dict[str, Any]] = []

    _put(event_queue, {"type": "status", "step": "profile", "text": f"识别为 {profile['name']} 项目，开始审查…"})
    _put(event_queue, {"type": "status", "step": "reverse", "text": "正在审查代码，反向推导需求与问题…"})

    t0 = time.perf_counter()
    spec = run_reverse_engineer_step(
        llm=llm, code=clipped, profile_injection=profile_injection, retrieval_context=retrieval_context
    )
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(1, REVERSE_ENGINEER_CFG.node, t1, {"profile": profile["name"], "reverse_engineer": spec.model_dump()}))
    _put(event_queue, {"type": "status", "step": "reverse_done", "text": "审查完成，正在整理报告…"})

    return _finish_review(user_text=clipped, spec=spec, profile=profile, steps=steps)
