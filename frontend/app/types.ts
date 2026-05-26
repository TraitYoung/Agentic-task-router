export type TraceStepRow = {
  index: number;
  node: string;
  ts: string;
  duration_ms: number;
  keys_written: string[];
  summary: Record<string, unknown> & {
    _metrics?: {
      estimated_tokens?: number;
      memory_mb?: number;
    };
  };
};

export type ChoiceId = "A" | "B" | "C" | "D";

export type StageChoiceOption = {
  id: ChoiceId;
  label: string;
  description: string;
};

export type StageChoice = {
  checkpointId: string;
  step: string;
  options: StageChoiceOption[];
  selected?: ChoiceId;
  /** 失败后可重试 */
  retryable?: boolean;
  lastChoice?: ChoiceId;
};

export type StagePartial = {
  step: string;
  markdown: string;
};

export type StreamRetry = {
  checkpointId: string;
  choice: ChoiceId;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: string;
  traceId?: string;
  traceSteps?: TraceStepRow[];
  artifactMd?: string;
  artifactPath?: string;
  artifactFilename?: string;
  stagePartials?: StagePartial[];
  stageChoices?: StageChoice[];
  awaitingChoice?: boolean;
  /** 续跑 continue 请求需携带的原始用户输入 */
  sourceUserText?: string;
  /** SSE 等待/heartbeat 状态，与最终 reply 分离 */
  streamStatusText?: string;
  /** merge 步流式输出 */
  mergeStream?: string;
  /** test_code 步流式输出 */
  testCodeStream?: string;
  /** 当前进行中的步骤 id */
  activePartialStep?: string;
  streamRetry?: StreamRetry;
};

export type UiMode = "spec" | "review";
