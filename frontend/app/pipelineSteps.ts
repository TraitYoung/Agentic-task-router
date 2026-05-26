export type PipelineStepId =
  | "profile"
  | "discovery"
  | "discovery_done"
  | "sprint"
  | "sprint_done"
  | "implementation"
  | "implementation_done"
  | "delivery"
  | "delivery_done"
  | "test_code"
  | "test_code_done"
  | "merge"
  | "awaiting_choice"
  | "reverse"
  | "reverse_done";

export const PIPELINE_STEPS: { id: PipelineStepId; label: string }[] = [
  { id: "profile", label: "识别画像" },
  { id: "discovery", label: "需求分析" },
  { id: "sprint", label: "架构设计" },
  { id: "implementation", label: "实现草案" },
  { id: "delivery", label: "测试方案" },
  { id: "test_code", label: "测试代码" },
  { id: "merge", label: "汇总发布" },
];

const ORDER: PipelineStepId[] = [
  "profile",
  "discovery",
  "discovery_done",
  "sprint",
  "sprint_done",
  "implementation",
  "implementation_done",
  "delivery",
  "delivery_done",
  "test_code",
  "test_code_done",
  "merge",
];

export function normalizePipelineStep(step: string | undefined): PipelineStepId | null {
  if (!step) return null;
  const s = step as PipelineStepId;
  if (ORDER.includes(s)) return s;
  return null;
}

export function pipelineStepIndex(step: PipelineStepId | null): number {
  if (!step) return -1;
  if (step === "profile") return 0;
  if (step === "discovery" || step === "discovery_done") return 1;
  if (step === "sprint" || step === "sprint_done") return 2;
  if (step === "implementation" || step === "implementation_done") return 3;
  if (step === "delivery" || step === "delivery_done") return 4;
  if (step === "test_code" || step === "test_code_done") return 5;
  if (step === "merge") return 6;
  return ORDER.indexOf(step);
}

export function pipelineStepLabel(step: PipelineStepId | null, mode: "spec" | "review"): string {
  if (mode === "review") {
    if (step === "reverse" || step === "profile") return "正在审查代码…";
    if (step === "reverse_done") return "正在整理报告…";
    return "审查中…";
  }
  const map: Partial<Record<PipelineStepId, string>> = {
    profile: "识别项目画像…",
    discovery: "分析需求与用户故事…",
    discovery_done: "需求分析完成",
    sprint: "设计架构与 Sprint 待办…",
    sprint_done: "架构设计完成",
    implementation: "生成实现草案…",
    implementation_done: "实现草案完成",
    delivery: "对照草案编写测试方案…",
    delivery_done: "测试方案完成",
    test_code: "生成测试代码草稿（约 1~2 分钟）…",
    test_code_done: "测试代码草稿完成",
    merge: "汇总发布说明…",
    awaiting_choice: "等待你的方向选择…",
  };
  return (step && map[step]) || "生成中…";
}

const PARTIAL_STEP_LABEL: Record<string, string> = {
  discovery: "需求分析",
  sprint: "架构设计",
  implementation: "实现草案",
  delivery: "测试方案",
  test_code: "测试代码",
};

const NEXT_AFTER: Record<string, PipelineStepId> = {
  discovery: "sprint",
  sprint: "implementation",
  implementation: "delivery",
  delivery: "test_code",
  test_code: "merge",
};

export function getNextStepAfter(completedStep: string): PipelineStepId | null {
  return NEXT_AFTER[completedStep] ?? null;
}

export function partialStepTitle(step: string): string {
  return PARTIAL_STEP_LABEL[step] ?? step;
}
