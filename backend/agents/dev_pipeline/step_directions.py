"""各流水线暂停点的 A/B/C/D 方向选项与 prompt 注入。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ChoiceId = Literal["A", "B", "C", "D"]

PAUSE_AFTER_STEPS: tuple[str, ...] = (
    "discovery",
    "sprint",
    "implementation",
    "delivery",
    "test_code",
)

NEXT_STEP: dict[str, str] = {
    "discovery": "sprint",
    "sprint": "implementation",
    "implementation": "delivery",
    "delivery": "test_code",
    "test_code": "merge",
}


@dataclass(frozen=True)
class DirectionOption:
    id: ChoiceId
    label: str
    description: str
    prompt_injection: str


_STEP_OPTIONS: dict[str, tuple[DirectionOption, DirectionOption, DirectionOption]] = {
    "discovery": (
        DirectionOption(
            "A",
            "MVP 极简验证",
            "下一步架构与实现优先最小可用路径，砍掉非必要功能。",
            "下一步请优先 MVP 极简验证：只保留核心用户路径，架构与实现从最小集开始。",
        ),
        DirectionOption(
            "B",
            "平衡迭代",
            "下一步在核心功能与可维护性之间取平衡。",
            "下一步请采用平衡迭代：核心功能完整，同时保留合理的模块划分与基本非功能需求。",
        ),
        DirectionOption(
            "C",
            "完整需求覆盖",
            "下一步尽量覆盖全部需求与扩展点。",
            "下一步请尽量完整覆盖需求：包含扩展点、边界场景与后续迭代预留。",
        ),
    ),
    "sprint": (
        DirectionOption(
            "A",
            "轻量架构",
            "下一步实现草案采用最少模块、最快落地。",
            "下一步实现请采用轻量架构：模块尽量少、依赖简单、优先可运行。",
        ),
        DirectionOption(
            "B",
            "标准分层",
            "下一步按常见分层（UI / 逻辑 / 数据）组织代码。",
            "下一步实现请采用标准分层：职责清晰、目录结构符合团队惯例。",
        ),
        DirectionOption(
            "C",
            "可扩展架构",
            "下一步预留接口与抽象，便于后续演进。",
            "下一步实现请采用可扩展架构：关键边界有抽象，便于替换与测试。",
        ),
    ),
    "implementation": (
        DirectionOption(
            "A",
            "最小代码骨架",
            "下一步测试方案以冒烟与主路径为主。",
            "下一步测试方案以冒烟与主路径为主，DoD 条目精简。",
        ),
        DirectionOption(
            "B",
            "标准实现",
            "下一步覆盖核心路径与常见异常。",
            "下一步测试方案覆盖核心路径与常见异常，DoD 符合常规合入标准。",
        ),
        DirectionOption(
            "C",
            "生产级完整",
            "下一步测试矩阵较全，含边界与回归。",
            "下一步测试方案尽量全面：含边界、回归与 CI 相关检查。",
        ),
    ),
    "delivery": (
        DirectionOption(
            "A",
            "冒烟测试为主",
            "下一步只生成 1~2 个关键测试文件。",
            "下一步测试代码以冒烟为主：少量高价值测试文件，覆盖主路径。",
        ),
        DirectionOption(
            "B",
            "核心路径覆盖",
            "下一步生成 2~3 个测试文件，覆盖 backlog 前几条。",
            "下一步测试代码覆盖核心路径：2~3 个文件，对齐 backlog 与 test_cases 前几条。",
        ),
        DirectionOption(
            "C",
            "全面测试矩阵",
            "下一步尽量多场景、多文件测试草案。",
            "下一步测试代码尽量全面：多场景覆盖，含边界与集成向用例。",
        ),
    ),
    "test_code": (
        DirectionOption(
            "A",
            "精简汇总",
            "最终 SPEC 发布说明简洁，4 条要点以内。",
            "最终汇总请精简：4 条以内要点，突出 MVP 与已覆盖测试。",
        ),
        DirectionOption(
            "B",
            "标准 SPEC",
            "最终 SPEC 结构完整、篇幅适中。",
            "最终汇总请标准篇幅：MVP、测试、风险、下迭代建议各 1~2 条。",
        ),
        DirectionOption(
            "C",
            "详尽文档",
            "最终 SPEC 尽量详尽，便于团队 onboarding。",
            "最终汇总请详尽：覆盖范围、测试、风险、后续建议均写清楚，便于新人接手。",
        ),
    ),
}


def get_choice_options(completed_step: str) -> list[dict[str, str]]:
    """返回含 A/B/C/D 四选项的 UI 列表（D 为综合 ABC）。"""
    if completed_step not in _STEP_OPTIONS:
        return []
    a, b, c = _STEP_OPTIONS[completed_step]
    return [
        {"id": a.id, "label": a.label, "description": a.description},
        {"id": b.id, "label": b.label, "description": b.description},
        {"id": c.id, "label": c.label, "description": c.description},
        {
            "id": "D",
            "label": "综合全部",
            "description": f"同时考虑 {a.label}、{b.label}、{c.label} 三方面。",
        },
    ]


def resolve_direction_hints(completed_step: str, choice: ChoiceId) -> list[str]:
    """根据刚完成步骤与用户选择，解析注入下一步的 prompt hints。"""
    if completed_step not in _STEP_OPTIONS:
        return []
    a, b, c = _STEP_OPTIONS[completed_step]
    if choice == "A":
        return [a.prompt_injection]
    if choice == "B":
        return [b.prompt_injection]
    if choice == "C":
        return [c.prompt_injection]
    if choice == "D":
        return [a.prompt_injection, b.prompt_injection, c.prompt_injection]
    return []
