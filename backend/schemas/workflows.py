"""开发流水线：结构化中间结果（敏捷 / 软件工程取向，下游只喂 JSON 摘要以省 Token）。"""

from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.coerce import cap_str, normalize_str_list

_WORKFLOW_MODEL_CONFIG = ConfigDict(extra="ignore")


class DevTaskSpec(BaseModel):
    """步骤 1：需求发现 — 对齐用户价值与可验收标准（教材式需求 + 敏捷用户故事）"""

    model_config = _WORKFLOW_MODEL_CONFIG

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

    @field_validator("goal", mode="before")
    @classmethod
    def cap_goal(cls, v: object) -> object:
        return cap_str(v, 2000, default="未指定目标")

    @field_validator("stack_hint", "mvp_sprint_goal", mode="before")
    @classmethod
    def cap_short_text(cls, v: object) -> object:
        return cap_str(v, 500)

    @field_validator("constraints", mode="before")
    @classmethod
    def cap_constraints(cls, v: object) -> object:
        return normalize_str_list(v, limit=8, item_max=400)

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def cap_acceptance(cls, v: object) -> object:
        return normalize_str_list(v, limit=6, item_max=400)

    @field_validator("user_stories", mode="before")
    @classmethod
    def cap_user_stories(cls, v: object) -> object:
        return normalize_str_list(v, limit=6, item_max=500)

    @field_validator("measurable_outcomes", mode="before")
    @classmethod
    def cap_metrics(cls, v: object) -> object:
        return normalize_str_list(v, limit=5, item_max=300)


class DevOutline(BaseModel):
    """步骤 2：迭代规划与设计 — 架构要点 + 有序 Sprint 待办（MVP 优先）"""

    model_config = _WORKFLOW_MODEL_CONFIG

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

    @field_validator("data_flow", mode="before")
    @classmethod
    def cap_data_flow(cls, v: object) -> object:
        return cap_str(v, 2000)

    @field_validator("modules", mode="before")
    @classmethod
    def cap_modules(cls, v: object) -> object:
        return normalize_str_list(v, limit=12, item_max=200)

    @field_validator("risks", mode="before")
    @classmethod
    def cap_risks(cls, v: object) -> object:
        return normalize_str_list(v, limit=6, item_max=400)

    @field_validator("backlog_parking_lot", mode="before")
    @classmethod
    def cap_parking(cls, v: object) -> object:
        return normalize_str_list(v, limit=8, item_max=400)

    @field_validator("technical_spikes", mode="before")
    @classmethod
    def cap_spikes(cls, v: object) -> object:
        return normalize_str_list(v, limit=5, item_max=400)

    @field_validator("backlog_mvp_ordered", mode="before")
    @classmethod
    def cap_mvp_backlog(cls, v: object) -> object:
        return normalize_str_list(v, limit=10, item_max=400)


class DevCodeSketch(BaseModel):
    """步骤 3：实现草案（单文件或清晰模块草图）"""

    model_config = _WORKFLOW_MODEL_CONFIG

    language: str = Field(default="python", max_length=128)
    code: str = Field(default="", max_length=6000)
    notes: str = Field(default="", max_length=1500)

    @field_validator("language", mode="before")
    @classmethod
    def cap_language(cls, v: object) -> object:
        return cap_str(v, 128, default="python")

    @field_validator("code", mode="before")
    @classmethod
    def cap_code(cls, v: object) -> object:
        return cap_str(v, 6000)

    @field_validator("notes", mode="before")
    @classmethod
    def cap_notes(cls, v: object) -> object:
        return cap_str(v, 1500)


class DevTestsChangelog(BaseModel):
    """步骤 4：测试、DoD、变更记录与短回顾 — 对齐「完成定义」与持续交付"""

    model_config = _WORKFLOW_MODEL_CONFIG

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

    @field_validator("changelog_entry", mode="before")
    @classmethod
    def cap_changelog(cls, v: object) -> object:
        return cap_str(v, 2000)

    @field_validator("sprint_retrospective_one_liner", mode="before")
    @classmethod
    def cap_retro(cls, v: object) -> object:
        return cap_str(v, 500)

    @field_validator("test_cases", mode="before")
    @classmethod
    def cap_tests(cls, v: object) -> object:
        return normalize_str_list(v, limit=10, item_max=400)

    @field_validator("definition_of_done", mode="before")
    @classmethod
    def cap_dod(cls, v: object) -> object:
        return normalize_str_list(v, limit=8, item_max=400)

    @field_validator("ci_cd_notes", mode="before")
    @classmethod
    def cap_ci(cls, v: object) -> object:
        return normalize_str_list(v, limit=6, item_max=400)


class DevTestFile(BaseModel):
    """单文件测试代码草稿（可粘贴到用户仓库）。"""

    model_config = _WORKFLOW_MODEL_CONFIG

    path: str = Field(default="", max_length=200)
    code: str = Field(default="", max_length=8000)

    @field_validator("path", mode="before")
    @classmethod
    def cap_path(cls, v: object) -> object:
        return cap_str(v, 200)

    @field_validator("code", mode="before")
    @classmethod
    def cap_code(cls, v: object) -> object:
        return cap_str(v, 8000)


class DevTestBundle(BaseModel):
    """步骤 5：可运行的测试代码草稿（2~3 个文件）。"""

    model_config = _WORKFLOW_MODEL_CONFIG

    files: List[DevTestFile] = Field(default_factory=list, max_length=5)

    @field_validator("files", mode="before")
    @classmethod
    def cap_files(cls, v: object) -> object:
        if not isinstance(v, list):
            return []
        out: list[DevTestFile] = []
        for item in v[:5]:
            if isinstance(item, DevTestFile):
                out.append(item)
            elif isinstance(item, dict):
                out.append(DevTestFile.model_validate(item))
        return out


class ReverseEngineerSpec(BaseModel):
    """逆向工程：从现有代码推导需求、测试与改进点"""

    model_config = _WORKFLOW_MODEL_CONFIG

    inferred_goal: str = Field(default="", max_length=2000, description="推测的业务目标")
    inferred_user_stories: List[str] = Field(default_factory=list, max_length=6, description="反向推导的用户故事")
    missing_tests: List[str] = Field(default_factory=list, max_length=10, description="缺失的测试用例")
    architecture_issues: List[str] = Field(default_factory=list, max_length=8, description="架构问题")
    code_quality_issues: List[str] = Field(default_factory=list, max_length=8, description="代码质量问题")
    improvement_plan: List[str] = Field(default_factory=list, max_length=6, description="改进计划（按优先级）")

    @field_validator("inferred_goal", mode="before")
    @classmethod
    def cap_inferred_goal(cls, v: object) -> object:
        return cap_str(v, 2000)

    @field_validator("inferred_user_stories", mode="before")
    @classmethod
    def cap_stories(cls, v: object) -> object:
        return normalize_str_list(v, limit=6, item_max=500)

    @field_validator("missing_tests", mode="before")
    @classmethod
    def cap_missing_tests(cls, v: object) -> object:
        return normalize_str_list(v, limit=10, item_max=400)

    @field_validator("architecture_issues", "code_quality_issues", mode="before")
    @classmethod
    def cap_issues(cls, v: object) -> object:
        return normalize_str_list(v, limit=8, item_max=400)

    @field_validator("improvement_plan", mode="before")
    @classmethod
    def cap_improvements(cls, v: object) -> object:
        return normalize_str_list(v, limit=6, item_max=500)


# ── Cursor / AI 编程工具 Prompt 生成 ──

def to_implementation_prompt(spec: DevTaskSpec, outline: DevOutline) -> str:
    """生成可直接粘贴到 Cursor/Copilot 的实现 prompt。"""
    stories = "\n".join(f"- {s}" for s in spec.user_stories)
    backlog = "\n".join(f"{i+1}. {t}" for i, t in enumerate(outline.backlog_mvp_ordered))
    acceptance = "\n".join(f"- [ ] {ac}" for ac in spec.acceptance_criteria)
    return (
        f"## 任务目标\n{spec.goal}\n\n"
        f"## 用户故事\n{stories}\n\n"
        f"## 实现任务（按顺序）\n{backlog}\n\n"
        f"## 验收标准\n{acceptance}\n\n"
        f"## 约束条件\n" + "\n".join(f"- {c}" for c in spec.constraints) + "\n\n"
        f"## 技术栈提示\n{spec.stack_hint or '请根据项目类型自行判断'}\n\n"
        "请逐条实现上述任务，每完成一条标记进度。优先 MVP，延后优化项。"
    )


def to_test_prompt(delivery: DevTestsChangelog) -> str:
    """生成测试编写 prompt。"""
    tests = "\n".join(f"- [ ] {t}" for t in delivery.test_cases)
    dod = "\n".join(f"- [ ] {d}" for d in delivery.definition_of_done)
    ci = "\n".join(f"- {c}" for c in delivery.ci_cd_notes)
    return (
        f"## 测试用例\n{tests}\n\n"
        f"## 完成定义 (DoD)\n{dod}\n\n"
        f"## CI/CD 注意事项\n{ci}\n\n"
        f"## CHANGELOG\n{delivery.changelog_entry}\n\n"
        "请为上述测试用例编写自动化测试代码，确保所有 DoD 条目可验证。"
    )


def to_review_prompt(spec: ReverseEngineerSpec) -> str:
    """生成代码审查改进 prompt。"""
    issues = "\n".join(f"{i+1}. {x}" for i, x in enumerate(spec.architecture_issues + spec.code_quality_issues))
    improvements = "\n".join(f"{i+1}. {x}" for i, x in enumerate(spec.improvement_plan))
    return (
        f"## 审查发现的问题\n{issues}\n\n"
        f"## 改进计划\n{improvements}\n\n"
        f"## 参考：推测的需求\n{spec.inferred_goal}\n\n"
        "请按改进计划逐条重构代码，每完成一条验证对应测试是否通过。"
    )
