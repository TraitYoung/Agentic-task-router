"""A 方向 step-agents：每步独立配置与执行，便于后续按步骤微调模型。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger("specforge.step_agents")

from config.context_budget import WORKFLOW_STEP_JSON_MAX_CHARS, clip_text
from config.step_model_routing import resolve_step_llm
from config.structured_invoke import invoke_structured, prepare_system_content, strip_thinking
from .test_code_parser import parse_test_bundle
from schemas.workflows import (
    DevCodeSketch,
    DevOutline,
    DevTaskSpec,
    DevTestBundle,
    DevTestsChangelog,
    ReverseEngineerSpec,
)

_LIST_RULE = "列表字段元素必须是字符串，禁止 {name, responsibility} 等嵌套对象。"


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

TEST_CODE_CFG = StepConfig(
    step_id="test_code",
    node="workflow.se.test_code",
    role="测试工程师",
)

MERGE_CFG = StepConfig(
    step_id="merge",
    node="workflow.se.merge",
    role="Release Integrator",
)

REVERSE_ENGINEER_CFG = StepConfig(
    step_id="reverse_engineer",
    node="workflow.se.reverse_engineer",
    role="代码审查专家",
)


def _system(content: str) -> SystemMessage:
    return SystemMessage(content=prepare_system_content(content))


def _message_content(chunk: Any, *, strip_think: bool = False) -> str:
    """LangChain AIMessageChunk.content 可能是 str 或 list。"""
    raw = getattr(chunk, "content", chunk)
    if isinstance(raw, list):
        parts: list[str] = []
        for block in raw:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        text = "".join(parts)
    else:
        text = str(raw) if raw is not None else ""
    return strip_thinking(text) if strip_think else text


def _json_clip(obj: Any, max_chars: int) -> str:
    s = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    return clip_text(s, max_chars)


def _structured_llm(cfg: StepConfig, fallback_llm):
    return resolve_step_llm(cfg.step_id, fallback_llm, structured=True)


def _direction_block(direction_hints: list[str] | None) -> str:
    if not direction_hints:
        return ""
    lines = "\n".join(f"- {hint}" for hint in direction_hints if hint.strip())
    if not lines:
        return ""
    return f"\n用户方向偏好（请在本次输出中体现）：\n{lines}"


def run_discovery_step(
    *, llm, raw_text: str, profile_injection: str, retrieval_context: str = ""
) -> DevTaskSpec:
    step_llm = _structured_llm(DISCOVERY_CFG, llm)
    system_parts = [
        f"你是{DISCOVERY_CFG.role}。{profile_injection}",
        "只根据用户原文抽取结构化结果，填满 DevTaskSpec 各字段。",
        _LIST_RULE,
        "- goal：业务目标一句话 + 必要背景。",
        "- 先补齐功能版图：用户角色、核心对象、主流程、异常/空状态、权限、数据留存/导出/设置等常见产品能力；不要只写工程结构。",
        "- acceptance_criteria：6~8 条，验收标准必须可测试；覆盖成功路径、失败路径、边界输入、权限/状态变化与关键体验。",
        "- user_stories：5~8 条，尽量 As a / I want / so that；覆盖不同用户角色与核心对象生命周期。",
        "- mvp_sprint_goal：本迭代最小可用增量。",
        "- measurable_outcomes：可观察结果或指标。",
    ]
    if retrieval_context:
        system_parts.append(f"\n参考历史类似方案（可借鉴思路但勿照搬）：\n{retrieval_context}")
    return invoke_structured(
        step_llm,
        DevTaskSpec,
        [
            _system("\n".join(system_parts)),
            HumanMessage(content=f"产品负责人原始描述：\n{raw_text}"),
        ],
        step_id=DISCOVERY_CFG.step_id,
    )


def run_sprint_step(
    *, llm, discovery: DevTaskSpec, profile_focus: str, direction_hints: list[str] | None = None
) -> DevOutline:
    step_llm = _structured_llm(SPRINT_CFG, llm)
    discovery_json = _json_clip(discovery.model_dump(), SPRINT_CFG.max_context_chars)
    return invoke_structured(
        step_llm,
        DevOutline,
        [
            _system(
                f"你是{SPRINT_CFG.role}。只依据上一份 JSON 产出 DevOutline。\n"
                f"请额外强调：{profile_focus}。\n"
                f"{_LIST_RULE}\n"
                "- modules（≤8，字符串数组）：每项一句，如「db: IndexedDB 封装」，单条≤60字。\n"
                "- data_flow：写清页面/API/数据之间如何流转，包含状态流转、权限校验和错误处理路径。\n"
                "- risks（≤6）：架构拆分与风险。\n"
                "- backlog_mvp_ordered（≤12）：按功能切片组织，每条 backlog 必须能独立开发和验收；覆盖页面/API/数据、CRUD、状态流转、错误处理、空状态和最小权限控制。\n"
                "- backlog_parking_lot（≤8）：明确延后条目。\n"
                "- technical_spikes（≤5）：需先验证的技术探针。"
                f"{_direction_block(direction_hints)}"
            ),
            HumanMessage(content=f"需求与故事 JSON：\n{discovery_json}"),
        ],
        step_id=SPRINT_CFG.step_id,
    )


def run_implementation_step(
    *,
    llm,
    discovery: DevTaskSpec,
    sprint: DevOutline,
    profile_injection: str,
    direction_hints: list[str] | None = None,
) -> DevCodeSketch:
    step_llm = _structured_llm(IMPLEMENT_CFG, llm)
    bundle = _json_clip(
        {"discovery": discovery.model_dump(), "sprint_design": sprint.model_dump()},
        IMPLEMENT_CFG.max_context_chars,
    )
    return invoke_structured(
        step_llm,
        DevCodeSketch,
        [
            _system(
                f"你是{IMPLEMENT_CFG.role}。只收到 discovery+sprint_design 的 JSON。\n"
                f"岗位注入：{profile_injection}\n"
                f"{_LIST_RULE}\n"
                "请给出单文件或清晰分区的代码草稿，体现 MVP 前两条 backlog 的核心路径；"
                "language 用简短技术栈名（如 TypeScript）；notes 写依赖、环境、后续重构点；"
                "code 控制篇幅，避免超长导致 JSON 截断。"
                f"{_direction_block(direction_hints)}"
            ),
            HumanMessage(content=f"上下文 JSON：\n{bundle}"),
        ],
        step_id=IMPLEMENT_CFG.step_id,
    )


def run_delivery_step(
    *,
    llm,
    discovery: DevTaskSpec,
    sprint: DevOutline,
    profile_focus: str,
    direction_hints: list[str] | None = None,
) -> DevTestsChangelog:
    step_llm = _structured_llm(DELIVERY_CFG, llm)
    bundle = _json_clip(
        {
            "discovery": discovery.model_dump(),
            "sprint_design": sprint.model_dump(),
        },
        DELIVERY_CFG.max_context_chars,
    )
    return invoke_structured(
        step_llm,
        DevTestsChangelog,
        [
            _system(
                f"你是{DELIVERY_CFG.role}。基于 JSON 填写 DevTestsChangelog。\n"
                f"岗位关注：{profile_focus}。\n"
                f"{_LIST_RULE}\n"
                "- test_cases：自动化或手测用例标题。\n"
                "- definition_of_done：合入主干 DoD 条目。\n"
                "- ci_cd_notes：流水线、lint、构建、环境变量提示。\n"
                "- changelog_entry：面向同事的变更条目。\n"
                "- sprint_retrospective_one_liner：一句回顾。"
                f"{_direction_block(direction_hints)}"
            ),
            HumanMessage(content=f"上下文 JSON：\n{bundle}"),
        ],
        step_id=DELIVERY_CFG.step_id,
    )


def _test_code_context(
    *,
    sprint: DevOutline,
    sketch: DevCodeSketch,
    delivery: DevTestsChangelog,
) -> str:
    payload = {
        "language": sketch.language,
        "sketch_preview": clip_text(sketch.code, 800),
        "test_cases": delivery.test_cases[:3],
        "backlog_top": sprint.backlog_mvp_ordered[:2],
    }
    return _json_clip(payload, TEST_CODE_CFG.max_context_chars)


def run_test_code_step(
    *,
    llm,
    discovery: DevTaskSpec,
    sprint: DevOutline,
    sketch: DevCodeSketch,
    delivery: DevTestsChangelog,
    profile_focus: str,
    direction_hints: list[str] | None = None,
    stream_callback: Callable[[str], None] | None = None,
) -> DevTestBundle:
    del discovery  # 精简上下文，不再传入完整 discovery JSON
    step_llm = resolve_step_llm(TEST_CODE_CFG.step_id, llm, structured=False)
    context = _test_code_context(sprint=sprint, sketch=sketch, delivery=delivery)
    messages = [
        SystemMessage(
            content=(
                f"你是{TEST_CODE_CFG.role}。根据上下文生成可粘贴的测试代码草稿。\n"
                f"岗位关注：{profile_focus}。\n"
                "请用 Markdown 输出，禁止 JSON。\n"
                "每个测试文件一块，格式严格如下：\n"
                "## file: src/__tests__/example.test.ts\n"
                "```typescript\n"
                "// 骨架测试代码\n"
                "```\n"
                "要求：\n"
                "- 只输出 1~2 个文件，骨架测试即可（主路径 + 1 个断言），不要完整生产级测试矩阵。\n"
                "- 覆盖 test_cases 前 2 条与 backlog_top 前 2 条的核心路径。\n"
                "- 语言与 language 字段一致；使用常见框架（vitest/jest/pytest 等）。\n"
                "- 每个 code 块控制在 80 行以内。"
                f"{_direction_block(direction_hints)}"
            )
        ),
        HumanMessage(content=f"上下文 JSON：\n{context}"),
    ]

    if stream_callback is not None:
        full: list[str] = []
        for chunk in step_llm.stream(messages):
            token = _message_content(chunk, strip_think=True)
            if token:
                stream_callback(token)
                full.append(token)
        raw = strip_thinking("".join(full)).strip()
        logger.info("test_code step streamed: chars=%d", len(raw))
        return parse_test_bundle(raw)

    rsp = step_llm.invoke(messages)
    raw = strip_thinking(_message_content(rsp)).strip()
    logger.info("test_code step done: chars=%d", len(raw))
    return parse_test_bundle(raw)


def run_merge_step(
    *,
    llm,
    discovery: DevTaskSpec,
    sprint: DevOutline,
    sketch: DevCodeSketch,
    delivery: DevTestsChangelog,
    stream_callback: Callable[[str], None] | None = None,
    direction_hints: list[str] | None = None,
) -> str:
    """阶段 2: 并行后汇总。有 stream_callback 时逐个 token 推送。"""
    payload = _json_clip(
        {
            "discovery": discovery.model_dump(),
            "sprint_design": sprint.model_dump(),
            "sketch": sketch.model_dump(),
            "delivery": delivery.model_dump(),
        },
        MERGE_CFG.max_context_chars,
    )
    step_llm = resolve_step_llm(MERGE_CFG.step_id, llm, structured=False)
    merge_direction = _direction_block(direction_hints)
    messages = [
        SystemMessage(
            content=(
                f"你是{MERGE_CFG.role}。请把四份结构化结果整合为可提交给团队的发布说明，"
                "包含: MVP范围、已覆盖测试、未完成风险、下迭代建议。保持简洁，4-8条要点。"
                f"{merge_direction}"
            )
        ),
        HumanMessage(content=f"上游 JSON:\n{payload}"),
    ]

    if stream_callback is not None:
        full: list[str] = []
        for chunk in step_llm.stream(messages):
            token = _message_content(chunk, strip_think=True)
            if token:
                stream_callback(token)
                full.append(token)
        result = strip_thinking("".join(full)).strip()
        logger.info("merge step streamed: chars=%d", len(result))
        return result

    rsp = step_llm.invoke(messages)
    result = strip_thinking(_message_content(rsp)).strip()
    logger.info("merge step done: chars=%d", len(result))
    return result


def run_reverse_engineer_step(
    *, llm, code: str, profile_injection: str, retrieval_context: str = ""
) -> ReverseEngineerSpec:
    """逆向工程：从现有代码反推需求、测试缺失与改进计划。"""
    step_llm = _structured_llm(REVERSE_ENGINEER_CFG, llm)
    clipped_code = clip_text(code, WORKFLOW_STEP_JSON_MAX_CHARS * 2)
    system_parts = [
        f"你是{REVERSE_ENGINEER_CFG.role}。请审查以下代码，反向推导：",
        _LIST_RULE,
        "1. inferred_goal：这段代码在解决什么业务问题？",
        "2. inferred_user_stories：可以反推出哪些用户故事？",
        "3. missing_tests：缺少哪些测试用例？",
        "4. architecture_issues：架构层面的问题（耦合、职责不清、缺少抽象等）",
        "5. code_quality_issues：代码质量问题（命名、错误处理、硬编码等）",
        "6. improvement_plan：按优先级排列的改进计划",
        profile_injection,
    ]
    if retrieval_context:
        system_parts.append(
            f"\n已知高频问题模式（请特别关注是否匹配以下问题，如匹配请引用）：\n{retrieval_context}"
        )
    return invoke_structured(
        step_llm,
        ReverseEngineerSpec,
        [
            _system("\n".join(system_parts)),
            HumanMessage(content=f"待审查代码：\n```\n{clipped_code}\n```"),
        ],
        step_id=REVERSE_ENGINEER_CFG.step_id,
    )
