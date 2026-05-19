export type PipelineStepId =
  | "profile"
  | "discovery"
  | "discovery_done"
  | "sprint"
  | "sprint_done"
  | "parallel"
  | "parallel_done"
  | "merge"
  | "reverse"
  | "reverse_done";

export const PIPELINE_STEPS: { id: PipelineStepId; label: string }[] = [
  { id: "profile", label: "识别画像" },
  { id: "discovery", label: "需求分析" },
  { id: "sprint", label: "架构设计" },
  { id: "parallel", label: "并行草案" },
  { id: "merge", label: "汇总发布" },
];

const ORDER: PipelineStepId[] = [
  "profile",
  "discovery",
  "discovery_done",
  "sprint",
  "sprint_done",
  "parallel",
  "parallel_done",
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
  const idx = ORDER.indexOf(step);
  if (idx < 0) return -1;
  if (step === "discovery_done") return 1;
  if (step === "sprint_done") return 2;
  if (step === "parallel_done") return 3;
  if (step === "merge") return 4;
  if (step === "discovery") return 1;
  if (step === "sprint") return 2;
  if (step === "parallel") return 3;
  if (step === "profile") return 0;
  return idx;
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
    parallel: "生成代码草案与测试方案…",
    parallel_done: "并行生成完成",
    merge: "汇总发布说明…",
  };
  return (step && map[step]) || "生成中…";
}
