"""A 方向 step-agents：每步独立配置与执行，便于后续按步骤微调模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config.context_budget import WORKFLOW_STEP_JSON_MAX_CHARS, clip_text
from config.step_model_routing import resolve_step_llm
from schemas.workflows import DevCodeSketch, DevOutline, DevTaskSpec, DevTestsChangelog


@dataclass(frozen=True)
class StepConfig:
    step_id: str
    node: str
    role: str
    model_hint: str = "default"
    max_context_chars: int = WORKFLOW_STEP_JSON_MAX_CHARS


DISCOVERY_CFG = StepConfig(
    step_id="discovery",
    node="workflow.se.discovery",
    role="需求教练",
)

SPRINT_CFG = StepConfig(
    step_id="sprint_design",
    node="workflow.se.sprint_design",
    role="Tech Lead + Scrum Master",
)

IMPLEMENT_CFG = StepConfig(
    step_id="implementation_sketch",
    node="workflow.se.implementation_sketch",
    role="实现工程师",
)

DELIVERY_CFG = StepConfig(
    step_id="delivery_review",
    node="workflow.se.delivery_review",
    role="QA + 发布协调",
)

MERGE_CFG = StepConfig(
    step_id="merge",
    node="workflow.se.merge",
    role="Release Integrator",
)


def _json_clip(obj: Any, max_chars: int) -> str:
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return clip_text(s, max_chars)


def run_discovery_step(*, llm, raw_text: str, profile_injection: str) -> DevTaskSpec:
    step_llm = resolve_step_llm(DISCOVERY_CFG.step_id, llm)
    model = step_llm.with_structured_output(DevTaskSpec)
    return model.invoke(
        [
            SystemMessage(
                content=(
                    f"你是{DISCOVERY_CFG.role}。{profile_injection}\n"
                    "只根据用户原文抽取结构化结果，填满 DevTaskSpec 各字段。\n"
                    "- goal：业务目标一句话 + 必要背景。\n"
                    "- acceptance_criteria：可测试、可验收。\n"
                    "- user_stories：3~6 条，尽量 As a / I want / so that。\n"
                    "- mvp_sprint_goal：本迭代最小可用增量。\n"
                    "- measurable_outcomes：可观察结果或指标。"
                )
            ),
            HumanMessage(content=f"产品负责人原始描述：\n{raw_text}"),
        ]
    )


def run_sprint_step(*, llm, discovery: DevTaskSpec, profile_focus: str) -> DevOutline:
    step_llm = resolve_step_llm(SPRINT_CFG.step_id, llm)
    model = step_llm.with_structured_output(DevOutline)
    discovery_json = _json_clip(discovery.model_dump(), SPRINT_CFG.max_context_chars)
    return model.invoke(
        [
            SystemMessage(
                content=(
                    f"你是{SPRINT_CFG.role}。只依据上一份 JSON 产出 DevOutline。\n"
                    f"请额外强调：{profile_focus}。\n"
                    "- modules / data_flow / risks：架构拆分与风险。\n"
                    "- backlog_mvp_ordered：本 Sprint 内按实现顺序排列任务。\n"
                    "- backlog_parking_lot：明确延后条目。\n"
                    "- technical_spikes：需先验证的技术探针。"
                )
            ),
            HumanMessage(content=f"需求与故事 JSON：\n{discovery_json}"),
        ]
    )


def run_implementation_step(
    *,
    llm,
    discovery: DevTaskSpec,
    sprint: DevOutline,
    profile_injection: str,
) -> DevCodeSketch:
    step_llm = resolve_step_llm(IMPLEMENT_CFG.step_id, llm)
    model = step_llm.with_structured_output(DevCodeSketch)
    bundle = _json_clip(
        {"discovery": discovery.model_dump(), "sprint_design": sprint.model_dump()},
        IMPLEMENT_CFG.max_context_chars,
    )
    return model.invoke(
        [
            SystemMessage(
                content=(
                    f"你是{IMPLEMENT_CFG.role}。只收到 discovery+sprint_design 的 JSON。\n"
                    f"岗位注入：{profile_injection}\n"
                    "请给出单文件或清晰分区的代码草稿，体现 MVP 前两条 backlog 的核心路径；"
                    "language 标明语言；notes 写依赖、环境、后续重构点。"
                )
            ),
            HumanMessage(content=f"上下文 JSON：\n{bundle}"),
        ]
    )


def run_delivery_step(
    *,
    llm,
    discovery: DevTaskSpec,
    sprint: DevOutline,
    sketch: DevCodeSketch,
    profile_focus: str,
) -> DevTestsChangelog:
    step_llm = resolve_step_llm(DELIVERY_CFG.step_id, llm)
    model = step_llm.with_structured_output(DevTestsChangelog)
    bundle = _json_clip(
        {
            "discovery": discovery.model_dump(),
            "sprint_design": sprint.model_dump(),
            "sketch": sketch.model_dump(),
        },
        DELIVERY_CFG.max_context_chars,
    )
    return model.invoke(
        [
            SystemMessage(
                content=(
                    f"你是{DELIVERY_CFG.role}。基于 JSON 填写 DevTestsChangelog。\n"
                    f"岗位关注：{profile_focus}。\n"
                    "- test_cases：自动化或手测用例标题。\n"
                    "- definition_of_done：合入主干 DoD 条目。\n"
                    "- ci_cd_notes：流水线、lint、构建、环境变量提示。\n"
                    "- changelog_entry：面向同事的变更条目。\n"
                    "- sprint_retrospective_one_liner：一句回顾。"
                )
            ),
            HumanMessage(content=f"上下文 JSON：\n{bundle}"),
        ]
    )


def run_merge_step(
    *,
    llm,
    discovery: DevTaskSpec,
    sprint: DevOutline,
    sketch: DevCodeSketch,
    delivery: DevTestsChangelog,
) -> str:
    """阶段 2：并行后汇总。返回 markdown 片段（面向最终交付展示）。"""
    payload = _json_clip(
        {
            "discovery": discovery.model_dump(),
            "sprint_design": sprint.model_dump(),
            "sketch": sketch.model_dump(),
            "delivery": delivery.model_dump(),
        },
        MERGE_CFG.max_context_chars,
    )
    step_llm = resolve_step_llm(MERGE_CFG.step_id, llm)
    rsp = step_llm.invoke(
        [
            SystemMessage(
                content=(
                    f"你是{MERGE_CFG.role}。请把四份结构化结果整合为“可提交给团队”的发布说明，"
                    "包含：MVP范围、已覆盖测试、未完成风险、下迭代建议。保持简洁，4-8条要点。"
                )
            ),
            HumanMessage(content=f"上游 JSON：\n{payload}"),
        ]
    )
    return str(rsp.content).strip()

