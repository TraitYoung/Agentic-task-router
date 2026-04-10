"""A 方向 orchestrator：阶段1配置化 + 阶段2并行实现/测试并汇总。"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from config.context_budget import WORKFLOW_USER_TEXT_MAX_CHARS, clip_text
from prompts.dev_pipeline_profiles import detect_dev_profile

from .step_agents import (
    DELIVERY_CFG,
    DISCOVERY_CFG,
    IMPLEMENT_CFG,
    MERGE_CFG,
    SPRINT_CFG,
    run_delivery_step,
    run_discovery_step,
    run_implementation_step,
    run_merge_step,
    run_sprint_step,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace_step(idx: int, node: str, t_ms: float, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": idx,
        "node": node,
        "ts": _now_iso(),
        "duration_ms": round(t_ms, 2),
        "keys_written": [],
        "summary": summary,
    }


def run_dev_pipeline(user_text: str, llm):
    """返回 (final_markdown, trace_steps)."""
    clipped = clip_text(user_text.strip(), WORKFLOW_USER_TEXT_MAX_CHARS)
    profile = detect_dev_profile(clipped)
    profile_injection = profile["prompt_injection"]
    profile_focus = "、".join(profile["output_focus"])
    steps: list[dict[str, Any]] = []

    # 1) discovery
    t0 = time.perf_counter()
    spec = run_discovery_step(llm=llm, raw_text=clipped, profile_injection=profile_injection)
    t1 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(1, DISCOVERY_CFG.node, t1, {"profile": profile["name"], "discovery": spec.model_dump()}))

    # 2) sprint design
    t0 = time.perf_counter()
    outline = run_sprint_step(llm=llm, discovery=spec, profile_focus=profile_focus)
    t2 = (time.perf_counter() - t0) * 1000
    steps.append(_trace_step(2, SPRINT_CFG.node, t2, {"profile": profile["name"], "sprint_design": outline.model_dump()}))

    # 3) phase-2 parallel: implementation + delivery
    # delivery 依赖 sketch，因此这里先并行“实现草案 + 测试规划基线”不可行。
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
    return final, steps

