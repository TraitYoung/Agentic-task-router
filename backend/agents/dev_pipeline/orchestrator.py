"""A 方向 orchestrator：阶段1配置化 + 阶段2并行实现/测试并汇总。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, NamedTuple

from config.context_budget import WORKFLOW_USER_TEXT_MAX_CHARS, clip_text
from prompts.dev_pipeline_profiles import detect_dev_profile
from schemas.artifact_pack import (
    build_review_artifact_md,
    build_review_chat_summary,
    build_spec_artifact_md,
    build_spec_chat_summary,
    save_artifact_md,
)

logger = logging.getLogger("specforge.orchestrator")

from .step_agents import (
    DELIVERY_CFG,
    DISCOVERY_CFG,
    IMPLEMENT_CFG,
    MERGE_CFG,
    REVERSE_ENGINEER_CFG,
    SPRINT_CFG,
    run_delivery_step,
    run_discovery_step,
    run_implementation_step,
    run_merge_step,
    run_reverse_engineer_step,
    run_sprint_step,
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


def _finish_spec(
    *,
    user_text: str,
    spec,
    outline,
    sketch,
    delivery,
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
    )
    summary = build_spec_chat_summary(spec=spec, outline=outline, merged_notes=merged_notes, profile=profile)
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


def run_dev_pipeline(user_text: str, llm, *, retrieval_context: str = "") -> PipelineResult:
    """返回聊天摘要、SPEC.md 实现包与 trace。"""
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

    t0 = time.perf_counter()
    spec = run_discovery_step(
        llm=llm, raw_text=clipped, profile_injection=profile_injection, retrieval_context=retrieval_context
    )
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(1, DISCOVERY_CFG.node, t1, {"profile": profile["name"], "discovery": spec.model_dump()}))

    t0 = time.perf_counter()
    outline = run_sprint_step(llm=llm, discovery=spec, profile_focus=profile_focus)
    t2 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(2, SPRINT_CFG.node, t2, {"profile": profile["name"], "sprint_design": outline.model_dump()}))

    def _impl():
        return run_implementation_step(
            llm=llm,
            discovery=spec,
            sprint=outline,
            profile_injection=profile_injection,
        )

    def _delivery_seed():
        from schemas.workflows import DevCodeSketch

        seed = DevCodeSketch(language="text", code="", notes="parallel-seed")
        return run_delivery_step(
            llm=llm,
            discovery=spec,
            sprint=outline,
            sketch=seed,
            profile_focus=profile_focus,
        )

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        sketch = ex.submit(_impl).result()
        delivery = ex.submit(_delivery_seed).result()
    t3 = (time.perf_counter() - t0) * 1000
    steps.append(
        _trace_step(
            3,
            IMPLEMENT_CFG.node,
            t3,
            {"profile": profile["name"], "parallel_group": "impl_delivery", "sketch": sketch.model_dump()},
        )
    )
    steps.append(
        _trace_step(
            4,
            DELIVERY_CFG.node,
            t3,
            {"profile": profile["name"], "parallel_group": "impl_delivery", "delivery": delivery.model_dump()},
        )
    )

    t0 = time.perf_counter()
    merged_notes = run_merge_step(
        llm=llm,
        discovery=spec,
        sprint=outline,
        sketch=sketch,
        delivery=delivery,
    )
    t4 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(5, MERGE_CFG.node, t4, {"profile": profile["name"], "merge_preview": merged_notes[:300]}))

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
        merged_notes=merged_notes,
        profile=profile,
        steps=steps,
    )


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


def _put(q: asyncio.Queue | None, event: dict[str, Any]) -> None:
    if q is not None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def run_dev_pipeline_stream(
    user_text: str, llm, *, retrieval_context: str = "", event_queue: asyncio.Queue | None = None
) -> PipelineResult:
    """正向工程流式版：进度经 event_queue；merge 不向前端推 token。"""
    clipped = clip_text(user_text.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    profile_injection = profile["prompt_injection"]
    profile_focus = "、".join(profile["output_focus"])
    steps: list[dict[str, Any]] = []

    _put(event_queue, {"type": "status", "step": "profile", "text": f"识别为 {profile['name']} 项目，开始分析…"})

    _put(event_queue, {"type": "status", "step": "discovery", "text": "正在分析需求，拆解用户故事与验收标准…"})
    t0 = time.perf_counter()
    spec = run_discovery_step(
        llm=llm, raw_text=clipped, profile_injection=profile_injection, retrieval_context=retrieval_context
    )
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(1, DISCOVERY_CFG.node, t1, {"profile": profile["name"], "discovery": spec.model_dump()}))
    _put(event_queue, {"type": "status", "step": "discovery_done", "text": "需求分析完成"})

    _put(event_queue, {"type": "status", "step": "sprint", "text": "正在设计架构，拆分模块与 Sprint 待办…"})
    t0 = time.perf_counter()
    outline = run_sprint_step(llm=llm, discovery=spec, profile_focus=profile_focus)
    t2 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(2, SPRINT_CFG.node, t2, {"profile": profile["name"], "sprint_design": outline.model_dump()}))
    _put(event_queue, {"type": "status", "step": "sprint_done", "text": "架构设计完成"})

    _put(event_queue, {"type": "status", "step": "parallel", "text": "正在并行生成代码草案与测试方案…"})

    def _impl():
        return run_implementation_step(llm=llm, discovery=spec, sprint=outline, profile_injection=profile_injection)

    def _delivery_seed():
        from schemas.workflows import DevCodeSketch

        seed = DevCodeSketch(language="text", code="", notes="parallel-seed")
        return run_delivery_step(llm=llm, discovery=spec, sprint=outline, sketch=seed, profile_focus=profile_focus)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        sketch = ex.submit(_impl).result()
        delivery = ex.submit(_delivery_seed).result()
    t3 = (time.perf_counter() - t0) * 1000
    steps.append(
        _trace_step(3, IMPLEMENT_CFG.node, t3, {"profile": profile["name"], "parallel_group": "impl_delivery", "sketch": sketch.model_dump()})
    )
    steps.append(
        _trace_step(4, DELIVERY_CFG.node, t3, {"profile": profile["name"], "parallel_group": "impl_delivery", "delivery": delivery.model_dump()})
    )
    _put(event_queue, {"type": "status", "step": "parallel_done", "text": "代码草案与测试方案生成完成"})

    _put(event_queue, {"type": "status", "step": "merge", "text": "正在汇总发布说明并生成实现包…"})

    t2_start = time.perf_counter()
    merged_notes = run_merge_step(
        llm=llm, discovery=spec, sprint=outline, sketch=sketch, delivery=delivery, stream_callback=None
    )
    t4 = (time.perf_counter() - t2_start) * 1000
    steps.append(_trace_step(5, MERGE_CFG.node, t4, {"profile": profile["name"], "merge_preview": merged_notes[:300]}))

    return _finish_spec(
        user_text=clipped,
        spec=spec,
        outline=outline,
        sketch=sketch,
        delivery=delivery,
        merged_notes=merged_notes,
        profile=profile,
        steps=steps,
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
