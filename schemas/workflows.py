"""开发流水线：结构化中间结果（敏捷 / 软件工程取向，下游只喂 JSON 摘要以省 Token）。"""

from typing import List

from pydantic import BaseModel, Field, field_validator


class DevTaskSpec(BaseModel):
    """步骤 1：需求发现 — 对齐用户价值与可验收标准（教材式需求 + 敏捷用户故事）"""

    goal: str = Field(..., max_length=2000)
    constraints: List[str] = Field(default_factory=list, max_length=8)
    stack_hint: str = Field(default="", max_length=500)
    acceptance_criteria: List[str] = Field(default_factory=list, max_length=6)
    user_stories: List[str] = Field(
        default_factory=list,
        max_length=6,
        description="简短用户故事，建议 As a / I want / so that 或一句话等价物",
    )
    mvp_sprint_goal: str = Field(
        default="",
        max_length=500,
        description="本迭代（Sprint）要交付的最小可用增量（MVP slice）",
    )
    measurable_outcomes: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="可观察的成功信号或度量（非空话）",
    )

    @field_validator("constraints")
    @classmethod
    def cap_constraints(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:8]]

    @field_validator("acceptance_criteria")
    @classmethod
    def cap_acceptance(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:6]]

    @field_validator("user_stories")
    @classmethod
    def cap_user_stories(cls, v: List[str]) -> List[str]:
        return [str(x)[:500] for x in v[:6]]

    @field_validator("measurable_outcomes")
    @classmethod
    def cap_metrics(cls, v: List[str]) -> List[str]:
        return [str(x)[:300] for x in v[:5]]


class DevOutline(BaseModel):
    """步骤 2：迭代规划与设计 — 架构要点 + 有序 Sprint 待办（MVP 优先）"""

    modules: List[str] = Field(default_factory=list, max_length=12)
    data_flow: str = Field(default="", max_length=2000)
    risks: List[str] = Field(default_factory=list, max_length=6)
    backlog_mvp_ordered: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="本 Sprint 内按实现顺序排列的待办项（颗粒度到可开发任务）",
    )
    backlog_parking_lot: List[str] = Field(
        default_factory=list,
        max_length=8,
        description="延后到后续迭代的条目（Parking lot）",
    )
    technical_spikes: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="需先验证未知点的技术探针（Spike）",
    )

    @field_validator("modules")
    @classmethod
    def cap_modules(cls, v: List[str]) -> List[str]:
        return [str(x)[:200] for x in v[:12]]

    @field_validator("risks")
    @classmethod
    def cap_risks(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:6]]

    @field_validator("backlog_parking_lot")
    @classmethod
    def cap_parking(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:8]]

    @field_validator("technical_spikes")
    @classmethod
    def cap_spikes(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:5]]

    @field_validator("backlog_mvp_ordered")
    @classmethod
    def cap_mvp_backlog(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:10]]


class DevCodeSketch(BaseModel):
    """步骤 3：实现草案（单文件或清晰模块草图）"""

    language: str = Field(default="python", max_length=32)
    code: str = Field(default="", max_length=6000)
    notes: str = Field(default="", max_length=1500)


class DevTestsChangelog(BaseModel):
    """步骤 4：测试、DoD、变更记录与短回顾 — 对齐「完成定义」与持续交付"""

    test_cases: List[str] = Field(default_factory=list, max_length=10)
    changelog_entry: str = Field(default="", max_length=2000)
    definition_of_done: List[str] = Field(
        default_factory=list,
        max_length=8,
        description="本增量满足哪些条件才算 Done（DoD checklist）",
    )
    ci_cd_notes: List[str] = Field(
        default_factory=list,
        max_length=6,
        description="CI/CD、自动化检查、发布注意点（可执行）",
    )
    sprint_retrospective_one_liner: str = Field(
        default="",
        max_length=500,
        description="Sprint 回顾：一条改进建议或风险预警",
    )

    @field_validator("test_cases")
    @classmethod
    def cap_tests(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:10]]

    @field_validator("definition_of_done", "ci_cd_notes")
    @classmethod
    def cap_dod_ci(cls, v: List[str]) -> List[str]:
        return [str(x)[:400] for x in v[:8]]

