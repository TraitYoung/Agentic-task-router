"""Multi-Agent 流水线编排器。

正向工程（spec）6 步顺序流水线：
  Discovery Agent  → 需求分析，拆分用户故事与验收条件
  Sprint Agent     → 架构设计，输出模块划分与 Sprint 待办
  Implementation   → 代码实现草案（含目录结构 + 组件接口）
  Delivery Agent   → 对照草案编写测试方案与 DoD 清单
  Test Code Agent  → 生成可粘贴的测试代码草案
  Merge Agent      → 汇总发布说明，合并为 SPEC.md 工件

逆向审查（review）单步：
  Reverse Engineer Agent → 从代码反推架构/需求，输出 REVIEW.md

每个 Agent：
  - 独立 system prompt（step_agents.py）
  - 独立结构化输出 schema（schemas/workflows.py）
  - 可按步骤路由到不同模型（config/step_model_routing.py）
  - 接收 RAG 检索上下文（历史 spec/高频 issue）作为参考
  - 支持同步 + SSE 流式双模式（共享同一核心函数）
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Literal, NamedTuple

from config.context_budget import WORKFLOW_USER_TEXT_MAX_CHARS, clip_text
from prompts.dev_pipeline_profiles import detect_dev_profile
from schemas.artifact_pack import (
    build_delivery_partial_md,
    build_discovery_partial_md,
    build_implementation_partial_md,
    build_review_artifact_md,
    build_review_chat_summary,
    build_spec_artifact_md,
    build_spec_chat_summary,
    build_sprint_partial_md,
    build_test_code_partial_md,
)
from schemas.workflows import (
    DevCodeSketch,
    DevOutline,
    DevTaskSpec,
    DevTestBundle,
    DevTestsChangelog,
)
from services.pipeline_memory import save_artifact_md

logger = logging.getLogger("specforge.orchestrator")

from .step_directions import (
    NEXT_STEP,
    PAUSE_AFTER_STEPS,
    ChoiceId,
    get_choice_options,
    resolve_direction_hints,
)
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


class PipelineCheckpointOutcome(NamedTuple):
    status: Literal["paused", "complete"]
    result: PipelineResult | None
    checkpoint_id: str | None
    waiting_after: str | None


_PARTIAL_BUILDERS = {
    "discovery": lambda r: build_discovery_partial_md(r["discovery"]),
    "sprint": lambda r: build_sprint_partial_md(r["outline"]),
    "implementation": lambda r: build_implementation_partial_md(r["sketch"]),
    "delivery": lambda r: build_delivery_partial_md(r["delivery"]),
    "test_code": lambda r: build_test_code_partial_md(r["test_bundle"]),
}


def _hydrate_results(results: dict[str, Any]) -> dict[str, Any]:
    hydrated: dict[str, Any] = {}
    if "discovery" in results:
        hydrated["discovery"] = DevTaskSpec.model_validate(results["discovery"])
    if "outline" in results:
        hydrated["outline"] = DevOutline.model_validate(results["outline"])
    if "sketch" in results:
        hydrated["sketch"] = DevCodeSketch.model_validate(results["sketch"])
    if "delivery" in results:
        hydrated["delivery"] = DevTestsChangelog.model_validate(results["delivery"])
    if "test_bundle" in results:
        hydrated["test_bundle"] = DevTestBundle.model_validate(results["test_bundle"])
    return hydrated


def _serialize_results(hydrated: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in hydrated.items():
        if hasattr(val, "model_dump"):
            out[key] = val.model_dump()
        else:
            out[key] = val
    return out


def _partial_md_for_step(completed_step: str, hydrated: dict[str, Any]) -> str:
    builder = _PARTIAL_BUILDERS.get(completed_step)
    if builder is None:
        return ""
    return builder(hydrated)


def _emit_pause(
    *,
    event_queue: asyncio.Queue | None,
    completed_step: str,
    partial_md: str,
    checkpoint_id: str,
    summary: dict[str, Any] | None = None,
) -> None:
    _put(
        event_queue,
        {
            "type": "partial",
            "step": completed_step,
            "markdown": partial_md,
            "summary": summary or {},
        },
    )
    _put(
        event_queue,
        {
            "type": "choice",
            "checkpoint_id": checkpoint_id,
            "step": completed_step,
            "options": get_choice_options(completed_step),
        },
    )
    _put(event_queue, {"type": "paused"})


def _run_single_pipeline_step(
    step_name: str,
    *,
    llm,
    hydrated: dict[str, Any],
    profile: dict[str, Any],
    retrieval_context: str,
    direction_hints: list[str] | None,
    event_queue: asyncio.Queue | None,
) -> tuple[Any, dict[str, Any], float]:
    """Run one pipeline step; return (result_obj, trace_summary, duration_ms)."""
    profile_injection = profile["prompt_injection"]
    profile_focus = "、".join(profile["output_focus"])
    profile_name = profile["name"]

    if step_name == "discovery":
        _emit_status(event_queue, "discovery")
        t0 = time.perf_counter()
        spec = run_discovery_step(
            llm=llm,
            raw_text=hydrated["user_text"],
            profile_injection=profile_injection,
            retrieval_context=retrieval_context,
        )
        t_ms = (time.perf_counter() - t0) * 1000
        trace = _trace_step(1, DISCOVERY_CFG.node, t_ms, {"profile": profile_name, "discovery": spec.model_dump()})
        _emit_status(event_queue, "discovery_done")
        return spec, trace, t_ms

    spec = hydrated["discovery"]
    outline = hydrated.get("outline")
    sketch = hydrated.get("sketch")
    delivery = hydrated.get("delivery")

    if step_name == "sprint":
        _emit_status(event_queue, "sprint")
        t0 = time.perf_counter()
        outline = run_sprint_step(
            llm=llm,
            discovery=spec,
            profile_focus=profile_focus,
            direction_hints=direction_hints,
        )
        t_ms = (time.perf_counter() - t0) * 1000
        trace = _trace_step(2, SPRINT_CFG.node, t_ms, {"profile": profile_name, "sprint_design": outline.model_dump()})
        _emit_status(event_queue, "sprint_done")
        return outline, trace, t_ms

    if step_name == "implementation":
        _emit_status(event_queue, "implementation")
        t0 = time.perf_counter()
        sketch = run_implementation_step(
            llm=llm,
            discovery=spec,
            sprint=outline,
            profile_injection=profile_injection,
            direction_hints=direction_hints,
        )
        t_ms = (time.perf_counter() - t0) * 1000
        trace = _trace_step(
            3,
            IMPLEMENT_CFG.node,
            t_ms,
            {"profile": profile_name, "impl_then_delivery": True, "sketch": sketch.model_dump()},
        )
        _emit_status(event_queue, "implementation_done")
        return sketch, trace, t_ms

    if step_name == "delivery":
        _emit_status(event_queue, "delivery")
        t0 = time.perf_counter()
        delivery = run_delivery_step(
            llm=llm,
            discovery=spec,
            sprint=outline,
            profile_focus=profile_focus,
            direction_hints=direction_hints,
        )
        t_ms = (time.perf_counter() - t0) * 1000
        trace = _trace_step(
            4,
            DELIVERY_CFG.node,
            t_ms,
            {"profile": profile_name, "impl_then_delivery": True, "delivery": _delivery_trace_summary(delivery)},
        )
        _emit_status(event_queue, "delivery_done")
        return delivery, trace, t_ms

    if step_name == "test_code":
        _emit_status(event_queue, "test_code")
        t0 = time.perf_counter()
        stream_cb = None
        if event_queue is not None:
            stream_cb = lambda token: _put(
                event_queue, {"type": "delta", "step": "test_code", "content": token}
            )
        test_bundle = run_test_code_step(
            llm=llm,
            discovery=spec,
            sprint=outline,
            sketch=sketch,
            delivery=delivery,
            profile_focus=profile_focus,
            direction_hints=direction_hints,
            stream_callback=stream_cb,
        )
        t_ms = (time.perf_counter() - t0) * 1000
        trace = _trace_step(
            5,
            TEST_CODE_CFG.node,
            t_ms,
            {
                "profile": profile_name,
                "test_bundle": test_bundle.model_dump(),
                "test_files_count": len(test_bundle.files),
            },
        )
        _emit_status(event_queue, "test_code_done")
        return test_bundle, trace, t_ms

    if step_name == "merge":
        _emit_status(event_queue, "merge")
        t0 = time.perf_counter()
        stream_cb = None
        if event_queue is not None:
            stream_cb = lambda token: _put(
                event_queue, {"type": "delta", "step": "merge", "content": token}
            )
        merged_notes = run_merge_step(
            llm=llm,
            discovery=spec,
            sprint=outline,
            sketch=sketch,
            delivery=delivery,
            stream_callback=stream_cb,
            direction_hints=direction_hints,
        )
        t_ms = (time.perf_counter() - t0) * 1000
        trace = _trace_step(6, MERGE_CFG.node, t_ms, {"profile": profile_name, "merge_preview": merged_notes[:300]})
        return merged_notes, trace, t_ms

    raise ValueError(f"unknown pipeline step: {step_name}")


def _run_implementation_delivery_parallel(
    *,
    llm,
    hydrated: dict[str, Any],
    profile: dict[str, Any],
    retrieval_context: str,
    direction_hints: list[str] | None,
    event_queue: asyncio.Queue | None,
) -> tuple[DevCodeSketch, DevTestsChangelog, list[dict[str, Any]]]:
    results: dict[str, Any] = {}
    traces: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_step = {
            executor.submit(
                _run_single_pipeline_step,
                step_name,
                llm=llm,
                hydrated=hydrated,
                profile=profile,
                retrieval_context=retrieval_context,
                direction_hints=direction_hints,
                event_queue=event_queue,
            ): step_name
            for step_name in ("implementation", "delivery")
        }
        for future in as_completed(future_to_step):
            step_name = future_to_step[future]
            result_obj, trace, _ = future.result()
            results[step_name] = result_obj
            traces.append(trace)

    traces.sort(key=lambda item: int(item.get("index", 0)))
    return results["implementation"], results["delivery"], traces


def _result_key_for_step(step_name: str) -> str:
    return {
        "discovery": "discovery",
        "sprint": "outline",
        "implementation": "sketch",
        "delivery": "delivery",
        "test_code": "test_bundle",
    }[step_name]


def _build_checkpoint_payload(
    *,
    session_id: str,
    user_text: str,
    profile: dict[str, Any],
    retrieval_context: str,
    waiting_after: str,
    choices: dict[str, str],
    hydrated: dict[str, Any],
    trace_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    checkpoint_id = str(uuid.uuid4())
    results = _serialize_results({k: v for k, v in hydrated.items() if k != "user_text"})
    return {
        "checkpoint_id": checkpoint_id,
        "session_id": session_id,
        "user_text": user_text,
        "profile": profile,
        "retrieval_context": retrieval_context,
        "waiting_after": waiting_after,
        "choices": choices,
        "results": results,
        "trace_steps": trace_steps,
    }


def _save_checkpoint_safe(session_cache: Any, session_id: str, payload: dict[str, Any]) -> None:
    try:
        session_cache.save_checkpoint(session_id, payload)
    except Exception as exc:
        raise RuntimeError(f"checkpoint save failed (is Redis running?): {exc}") from exc


def run_dev_pipeline_interactive_start(
    user_text: str,
    llm,
    *,
    retrieval_context: str = "",
    event_queue: asyncio.Queue | None = None,
    session_id: str,
    session_cache: Any,
) -> PipelineCheckpointOutcome:
    clipped = clip_text(user_text.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    _emit_status(event_queue, "profile", profile_name=profile["name"])

    hydrated: dict[str, Any] = {"user_text": clipped}
    trace_steps: list[dict[str, Any]] = []

    spec, trace, _ = _run_single_pipeline_step(
        "discovery",
        llm=llm,
        hydrated=hydrated,
        profile=profile,
        retrieval_context=retrieval_context,
        direction_hints=None,
        event_queue=event_queue,
    )
    hydrated["discovery"] = spec
    trace_steps.append(trace)

    payload = _build_checkpoint_payload(
        session_id=session_id,
        user_text=clipped,
        profile=profile,
        retrieval_context=retrieval_context,
        waiting_after="discovery",
        choices={},
        hydrated=hydrated,
        trace_steps=trace_steps,
    )
    _save_checkpoint_safe(session_cache, session_id, payload)
    partial_md = _partial_md_for_step("discovery", hydrated)
    _emit_pause(
        event_queue=event_queue,
        completed_step="discovery",
        partial_md=partial_md,
        checkpoint_id=payload["checkpoint_id"],
        summary=spec.model_dump(),
    )
    return PipelineCheckpointOutcome("paused", None, payload["checkpoint_id"], "discovery")


def run_dev_pipeline_interactive_continue(
    checkpoint_id: str,
    choice: ChoiceId,
    llm,
    *,
    event_queue: asyncio.Queue | None = None,
    session_id: str,
    session_cache: Any,
) -> PipelineCheckpointOutcome:
    payload = session_cache.get_checkpoint(checkpoint_id)
    if not payload:
        raise ValueError("checkpoint not found or expired")
    if str(payload.get("session_id")) != session_id:
        raise ValueError("checkpoint session mismatch")

    waiting_after = str(payload["waiting_after"])
    if waiting_after not in PAUSE_AFTER_STEPS:
        raise ValueError(f"invalid waiting_after: {waiting_after}")

    choices = dict(payload.get("choices") or {})
    choices[waiting_after] = choice

    user_text = str(payload["user_text"])
    profile = dict(payload["profile"])
    retrieval_context = str(payload.get("retrieval_context") or "")
    trace_steps: list[dict[str, Any]] = list(payload.get("trace_steps") or [])

    hydrated = _hydrate_results(dict(payload.get("results") or {}))
    hydrated["user_text"] = user_text

    next_step = NEXT_STEP[waiting_after]
    direction_hints = resolve_direction_hints(waiting_after, choice)

    _put(
        event_queue,
        {
            "type": "ack",
            "action": "continue",
            "choice": choice,
            "next_step": next_step,
            "step": waiting_after,
        },
    )

    if waiting_after == "sprint":
        sketch, delivery, parallel_traces = _run_implementation_delivery_parallel(
            llm=llm,
            hydrated=hydrated,
            profile=profile,
            retrieval_context=retrieval_context,
            direction_hints=direction_hints,
            event_queue=event_queue,
        )
        hydrated["sketch"] = sketch
        hydrated["delivery"] = delivery
        trace_steps.extend(parallel_traces)

        old_checkpoint_id = checkpoint_id
        new_payload = _build_checkpoint_payload(
            session_id=session_id,
            user_text=user_text,
            profile=profile,
            retrieval_context=retrieval_context,
            waiting_after="delivery",
            choices=choices,
            hydrated=hydrated,
            trace_steps=trace_steps,
        )
        session_cache.delete_checkpoint(old_checkpoint_id, session_id)
        _save_checkpoint_safe(session_cache, session_id, new_payload)

        _put(
            event_queue,
            {
                "type": "partial",
                "step": "implementation",
                "markdown": _partial_md_for_step("implementation", hydrated),
                "summary": sketch.model_dump(),
            },
        )
        _emit_pause(
            event_queue=event_queue,
            completed_step="delivery",
            partial_md=_partial_md_for_step("delivery", hydrated),
            checkpoint_id=new_payload["checkpoint_id"],
            summary=delivery.model_dump(),
        )
        return PipelineCheckpointOutcome("paused", None, new_payload["checkpoint_id"], "delivery")

    result_obj, trace, _ = _run_single_pipeline_step(
        next_step,
        llm=llm,
        hydrated=hydrated,
        profile=profile,
        retrieval_context=retrieval_context,
        direction_hints=direction_hints,
        event_queue=event_queue,
    )
    trace_steps.append(trace)

    if next_step == "merge":
        session_cache.delete_checkpoint(checkpoint_id, session_id)
        merged_notes = str(result_obj)
        pipeline_result = _finish_spec(
            user_text=user_text,
            spec=hydrated["discovery"],
            outline=hydrated["outline"],
            sketch=hydrated["sketch"],
            delivery=hydrated["delivery"],
            test_bundle=hydrated["test_bundle"],
            merged_notes=merged_notes,
            profile=profile,
            steps=trace_steps,
        )
        return PipelineCheckpointOutcome("complete", pipeline_result, None, None)

    result_key = _result_key_for_step(next_step)
    hydrated[result_key] = result_obj

    old_checkpoint_id = checkpoint_id
    new_payload = _build_checkpoint_payload(
        session_id=session_id,
        user_text=user_text,
        profile=profile,
        retrieval_context=retrieval_context,
        waiting_after=next_step,
        choices=choices,
        hydrated=hydrated,
        trace_steps=trace_steps,
    )
    session_cache.delete_checkpoint(old_checkpoint_id, session_id)
    _save_checkpoint_safe(session_cache, session_id, new_payload)

    partial_md = _partial_md_for_step(next_step, hydrated)
    summary = result_obj.model_dump() if hasattr(result_obj, "model_dump") else {"merge_preview": str(result_obj)[:300]}
    _emit_pause(
        event_queue=event_queue,
        completed_step=next_step,
        partial_md=partial_md,
        checkpoint_id=new_payload["checkpoint_id"],
        summary=summary,
    )
    return PipelineCheckpointOutcome("paused", None, new_payload["checkpoint_id"], next_step)


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

    hydrated = {"user_text": clipped, "discovery": spec, "outline": outline}
    sketch, delivery, parallel_traces = _run_implementation_delivery_parallel(
        llm=llm,
        hydrated=hydrated,
        profile=profile,
        retrieval_context=retrieval_context,
        direction_hints=None,
        event_queue=event_queue,
    )
    steps.extend(parallel_traces)

    _emit_status(event_queue, "test_code")
    t0 = time.perf_counter()
    stream_cb = None
    if event_queue is not None:
        stream_cb = lambda token: _put(
            event_queue, {"type": "delta", "step": "test_code", "content": token}
        )
    test_bundle = run_test_code_step(
        llm=llm,
        discovery=spec,
        sprint=outline,
        sketch=sketch,
        delivery=delivery,
        profile_focus=profile_focus,
        stream_callback=stream_cb,
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
    merge_stream_cb = None
    if event_queue is not None:
        merge_stream_cb = lambda token: _put(
            event_queue, {"type": "delta", "step": "merge", "content": token}
        )
    merged_notes = run_merge_step(
        llm=llm,
        discovery=spec,
        sprint=outline,
        sketch=sketch,
        delivery=delivery,
        stream_callback=merge_stream_cb,
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


def run_dev_pipeline_interactive_stream(
    user_text: str,
    llm,
    *,
    retrieval_context: str = "",
    event_queue: asyncio.Queue | None = None,
    session_id: str,
    session_cache: Any,
    action: Literal["start", "continue"] = "start",
    checkpoint_id: str | None = None,
    choice: ChoiceId | None = None,
) -> PipelineCheckpointOutcome:
    """Interactive forward workflow: one step per invocation with pause/choice."""
    if action == "continue":
        if not checkpoint_id or not choice:
            raise ValueError("continue requires checkpoint_id and choice")
        return run_dev_pipeline_interactive_continue(
            checkpoint_id,
            choice,
            llm,
            event_queue=event_queue,
            session_id=session_id,
            session_cache=session_cache,
        )
    return run_dev_pipeline_interactive_start(
        user_text,
        llm,
        retrieval_context=retrieval_context,
        event_queue=event_queue,
        session_id=session_id,
        session_cache=session_cache,
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
