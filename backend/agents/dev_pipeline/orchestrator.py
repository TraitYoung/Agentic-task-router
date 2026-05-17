"""A 方向 orchestrator：阶段1配置化 + 阶段2并行实现/测试并汇总。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from config.context_budget import WORKFLOW_USER_TEXT_MAX_CHARS, clip_text
from prompts.dev_pipeline_profiles import detect_dev_profile

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
from schemas.workflows import to_implementation_prompt, to_review_prompt, to_test_prompt


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


def run_dev_pipeline(user_text: str, llm, *, retrieval_context: str = ""):
    """返回 (final_markdown, trace_steps)."""
    t_total = time.perf_counter()
    clipped = clip_text(user_text.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    logger.info("dev_pipeline start: profile=%s text_len=%d retrieval=%s",
                profile["name"], len(clipped), "yes" if retrieval_context else "no")
    profile_injection = profile["prompt_injection"]
    profile_focus = "、".join(profile["output_focus"])
    steps: list[dict[str, Any]] = []

    # 1) discovery
    t0 = time.perf_counter()
    spec = run_discovery_step(
        llm=llm, raw_text=clipped, profile_injection=profile_injection, retrieval_context=retrieval_context
    )
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(1, DISCOVERY_CFG.node, t1, {"profile": profile["name"], "discovery": spec.model_dump()}))

    # 2) sprint design
    t0 = time.perf_counter()
    outline = run_sprint_step(llm=llm, discovery=spec, profile_focus=profile_focus)
    t2 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(2, SPRINT_CFG.node, t2, {"profile": profile["name"], "sprint_design": outline.model_dump()}))

    # 3) phase-2 parallel: implementation + delivery
    # delivery 依赖 sketch，因此这里先并行"实现草案 + 测试规划基线"不可行。
    # 折中实现：并行跑两个互补 agent，测试agent读取 discovery+sprint（不读 sketch），随后 merge 汇总。
    def _impl():
        return run_implementation_step(
            llm=llm,
            discovery=spec,
            sprint=outline,
            profile_injection=profile_injection,
        )

    def _delivery_seed():
        # 先给一个轻量草图，确保并行阶段有稳定输入，再由 merge 做一致性收敛。
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
        f_impl = ex.submit(_impl)
        f_deliver = ex.submit(_delivery_seed)
        sketch = f_impl.result()
        delivery = f_deliver.result()
    t3 = (time.perf_counter() - t0) * 1000
    # 拆成两条 trace，耗时都记录并行段总耗时，便于肉眼比对
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

    # 4) merge
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

    final = (
        "## AI 赋能软件工程流水线（敏捷取向 · 多步编排）\n\n"
        f"- 岗位画像：`{profile['name']}`\n"
        f"- 输出关注：{profile_focus}\n"
        "- 执行形态：阶段1（步骤配置化）+ 阶段2（实现/交付并行 + merge）\n\n"
        "### 1) 需求发现 · 用户故事与 Sprint 目标\n"
        f"{json.dumps(spec.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        "### 2) Sprint 待办与架构 / 数据流\n"
        f"{json.dumps(outline.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        "### 3) 实现草案（并行分支 A）\n"
        f"```{sketch.language}\n{sketch.code}\n```\n"
        f"{sketch.notes}\n\n"
        "### 4) 测试 · DoD · CHANGELOG · CI · 回顾（并行分支 B）\n"
        f"{json.dumps(delivery.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        "### 5) 并行汇总（Merge）\n"
        f"{merged_notes}\n"
    )
    logger.info("dev_pipeline done: profile=%s steps=%d total_ms=%d",
                profile["name"], len(steps), int((time.perf_counter() - t_total) * 1000))
    return final, steps


def run_reverse_engineer(code: str, llm, *, retrieval_context: str = ""):
    """逆向工程：代码 → 需求规格 + 改进计划。返回 (final_markdown, trace_steps)."""
    t_total = time.perf_counter()
    clipped = clip_text(code.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    logger.info("reverse_engineer start: profile=%s code_len=%d retrieval=%s",
                profile["name"], len(clipped), "yes" if retrieval_context else "no")
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

    review_prompt = to_review_prompt(spec)

    final = (
        "## SpecForge 代码审查报告\n\n"
        f"- 项目画像：`{profile['name']}`\n\n"
        "### 推测的业务目标\n"
        f"{spec.inferred_goal}\n\n"
        "### 反向推导的用户故事\n"
        + "\n".join(f"- {s}" for s in spec.inferred_user_stories)
        + "\n\n"
        "### 架构问题\n"
        + "\n".join(f"- {x}" for x in spec.architecture_issues)
        + "\n\n"
        "### 代码质量问题\n"
        + "\n".join(f"- {x}" for x in spec.code_quality_issues)
        + "\n\n"
        "### 缺失的测试\n"
        + "\n".join(f"- {t}" for t in spec.missing_tests)
        + "\n\n"
        "### 改进计划（按优先级）\n"
        + "\n".join(f"{i+1}. {x}" for i, x in enumerate(spec.improvement_plan))
        + "\n\n"
        "---\n"
        "### 可粘贴到 Cursor 的改进 Prompt\n\n"
        f"```\n{review_prompt}\n```\n"
    )
    logger.info("reverse_engineer done: profile=%s steps=%d total_ms=%d",
                profile["name"], len(steps), int((time.perf_counter() - t_total) * 1000))
    return final, steps


# ═══════════════════════════════════════════════════════════════
# Streaming variants: push status/delta events to asyncio.Queue
# ═══════════════════════════════════════════════════════════════


def _put(q: asyncio.Queue | None, event: dict[str, Any]) -> None:
    if q is not None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def run_dev_pipeline_stream(
    user_text: str, llm, *, retrieval_context: str = "", event_queue: asyncio.Queue | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """正向工程流式版：进度事件通过 event_queue 推送，merge 段逐 token 流式。"""
    clipped = clip_text(user_text.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    profile_injection = profile["prompt_injection"]
    profile_focus = "、".join(profile["output_focus"])
    steps: list[dict[str, Any]] = []

    _put(event_queue, {"type": "status", "step": "profile", "text": f"识别为 {profile['name']} 项目，开始分析…"})

    # 1) discovery
    _put(event_queue, {"type": "status", "step": "discovery", "text": "正在分析需求，拆解用户故事与验收标准…"})
    t0 = time.perf_counter()
    spec = run_discovery_step(
        llm=llm, raw_text=clipped, profile_injection=profile_injection, retrieval_context=retrieval_context
    )
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(1, DISCOVERY_CFG.node, t1, {"profile": profile["name"], "discovery": spec.model_dump()}))
    _put(event_queue, {"type": "status", "step": "discovery_done", "text": "需求分析完成"})

    # 2) sprint design
    _put(event_queue, {"type": "status", "step": "sprint", "text": "正在设计架构，拆分模块与 Sprint 待办…"})
    t0 = time.perf_counter()
    outline = run_sprint_step(llm=llm, discovery=spec, profile_focus=profile_focus)
    t2 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(2, SPRINT_CFG.node, t2, {"profile": profile["name"], "sprint_design": outline.model_dump()}))
    _put(event_queue, {"type": "status", "step": "sprint_done", "text": "架构设计完成"})

    # 3) phase-2 parallel: implementation + delivery
    _put(event_queue, {"type": "status", "step": "parallel", "text": "正在并行生成代码草案与测试方案…"})

    def _impl():
        return run_implementation_step(llm=llm, discovery=spec, sprint=outline, profile_injection=profile_injection)

    def _delivery_seed():
        from schemas.workflows import DevCodeSketch

        seed = DevCodeSketch(language="text", code="", notes="parallel-seed")
        return run_delivery_step(llm=llm, discovery=spec, sprint=outline, sketch=seed, profile_focus=profile_focus)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_impl = ex.submit(_impl)
        f_deliver = ex.submit(_delivery_seed)
        sketch = f_impl.result()
        delivery = f_deliver.result()
    t3 = (time.perf_counter() - t0) * 1000
    steps.append(
        _trace_step(3, IMPLEMENT_CFG.node, t3, {"profile": profile["name"], "parallel_group": "impl_delivery", "sketch": sketch.model_dump()})
    )
    steps.append(
        _trace_step(4, DELIVERY_CFG.node, t3, {"profile": profile["name"], "parallel_group": "impl_delivery", "delivery": delivery.model_dump()})
    )
    _put(event_queue, {"type": "status", "step": "parallel_done", "text": "代码草案与测试方案生成完成"})

    # 4) merge — true streaming
    _put(event_queue, {"type": "status", "step": "merge", "text": "正在汇总发布说明…"})

    def _on_token(token: str) -> None:
        _put(event_queue, {"type": "delta", "content": token})

    t2_start = time.perf_counter()
    merged_notes = run_merge_step(
        llm=llm, discovery=spec, sprint=outline, sketch=sketch, delivery=delivery, stream_callback=_on_token,
    )
    t4 = (time.perf_counter() - t2_start) * 1000
    steps.append(_trace_step(5, MERGE_CFG.node, t4, {"profile": profile["name"], "merge_preview": merged_notes[:300]}))

    final = (
        "## AI 赋能软件工程流水线（敏捷取向 · 多步编排）\n\n"
        f"- 岗位画像：`{profile['name']}`\n"
        f"- 输出关注：{profile_focus}\n"
        "- 执行形态：阶段1（步骤配置化）+ 阶段2（实现/交付并行 + merge）\n\n"
        "### 1) 需求发现 · 用户故事与 Sprint 目标\n"
        f"{json.dumps(spec.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        "### 2) Sprint 待办与架构 / 数据流\n"
        f"{json.dumps(outline.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        "### 3) 实现草案（并行分支 A）\n"
        f"```{sketch.language}\n{sketch.code}\n```\n"
        f"{sketch.notes}\n\n"
        "### 4) 测试 · DoD · CHANGELOG · CI · 回顾（并行分支 B）\n"
        f"{json.dumps(delivery.model_dump(), ensure_ascii=False, indent=2)}\n\n"
        "### 5) 并行汇总（Merge）\n"
        f"{merged_notes}\n"
    )
    return final, steps


def run_reverse_engineer_stream(
    code: str, llm, *, retrieval_context: str = "", event_queue: asyncio.Queue | None = None
) -> tuple[str, list[dict[str, Any]]]:
    """逆向审查流式版：进度事件通过 event_queue 推送。"""
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

    review_prompt = to_review_prompt(spec)

    final = (
        "## SpecForge 代码审查报告\n\n"
        f"- 项目画像：`{profile['name']}`\n\n"
        "### 推测的业务目标\n"
        f"{spec.inferred_goal}\n\n"
        "### 反向推导的用户故事\n"
        + "\n".join(f"- {s}" for s in spec.inferred_user_stories)
        + "\n\n"
        "### 架构问题\n"
        + "\n".join(f"- {x}" for x in spec.architecture_issues)
        + "\n\n"
        "### 代码质量问题\n"
        + "\n".join(f"- {x}" for x in spec.code_quality_issues)
        + "\n\n"
        "### 缺失的测试\n"
        + "\n".join(f"- {t}" for t in spec.missing_tests)
        + "\n\n"
        "### 改进计划（按优先级）\n"
        + "\n".join(f"{i+1}. {x}" for i, x in enumerate(spec.improvement_plan))
        + "\n\n"
        "---\n"
        "### 可粘贴到 Cursor 的改进 Prompt\n\n"
        f"```\n{review_prompt}\n```\n"
    )
    return final, steps

