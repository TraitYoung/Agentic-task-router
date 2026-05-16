export type TraceStepRow = {
  index: number;
  node: string;
  ts: string;
  duration_ms: number;
  keys_written: string[];
  summary: Record<string, unknown>;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: string;
  traceId?: string;
  traceSteps?: TraceStepRow[];
};

export type UiMode = "spec" | "review";
