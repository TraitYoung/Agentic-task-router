import type { UiMode } from "./types";

interface Props {
  mode: UiMode;
  stackOk: boolean | null;
  onPromptClick: (prompt: string) => void;
}

const specPrompts = [
  "帮我拆解一个新功能的需求、范围和验收标准",
  "把一个模糊想法整理成 Sprint 计划和交付清单",
];

const reviewPrompts = [
  "帮我审查这段代码的结构问题和潜在风险",
  "把现有实现反向整理成需求、测试点和重构路线",
];

export function WelcomeHero({ mode, stackOk, onPromptClick }: Props) {
  const prompts = mode === "spec" ? specPrompts : reviewPrompts;

  return (
    <div className="mx-auto flex w-full max-w-6xl items-start px-4 pt-6 pb-2">
      <div className="grid w-full gap-4 lg:grid-cols-[1.25fr_0.75fr]">
        <section className="rounded-[2rem] border border-white/60 bg-[color:var(--surface)] p-6 shadow-[0_24px_70px_rgba(98,65,39,0.12)] backdrop-blur-xl">
          <div className="inline-flex rounded-full border border-[rgba(201,111,59,0.18)] bg-[rgba(201,111,59,0.08)] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-[color:var(--accent-strong)]">
            {mode === "spec" ? "Product Spec Studio" : "Reverse Review Desk"}
          </div>
          <h1 className="mt-3 max-w-2xl text-2xl font-semibold tracking-tight text-zinc-900 sm:text-3xl">
            {mode === "spec" ? "把模糊需求整理成可执行规格" : "把现有代码还原成清晰决策"}
          </h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-600">
            {mode === "spec"
              ? "从目标、范围、验收标准到 Sprint 计划，一次把需求讲清楚。"
              : "从实现细节、结构风险到重构建议，快速看出问题和下一步。"}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {prompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => onPromptClick(prompt)}
                className="rounded-2xl border border-[color:var(--line)] bg-white/80 px-4 py-3 text-left text-sm text-zinc-600 shadow-sm transition-transform hover:-translate-y-0.5 hover:text-zinc-900"
              >
                {prompt}
              </button>
            ))}
          </div>
        </section>

        <aside className="rounded-[2rem] border border-white/60 bg-[color:var(--surface)] p-5 shadow-[0_24px_70px_rgba(98,65,39,0.1)] backdrop-blur-xl">
          <div className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">
            当前工作流
          </div>
          <div className="mt-3 space-y-3">
            <div className="rounded-2xl bg-white/80 p-4 shadow-sm">
              <div className="text-sm font-medium text-zinc-900">输入方式</div>
              <p className="mt-2 text-sm leading-6 text-zinc-600">
                {mode === "spec"
                  ? "自然语言描述目标、约束和你希望交付的结果。"
                  : "贴入代码片段或模块说明，系统会反向整理结构与风险。"}
              </p>
            </div>
            <div className="rounded-2xl bg-white/80 p-4 shadow-sm">
              <div className="text-sm font-medium text-zinc-900">发送规则</div>
              <p className="mt-2 text-sm leading-6 text-zinc-600">
                Enter 发送，Shift+Enter 换行。中文输入法确认候选词时不会误触发送。
              </p>
            </div>
            <div className="rounded-2xl bg-white/80 p-4 shadow-sm">
              <div className="text-sm font-medium text-zinc-900">当前状态</div>
              <p className="mt-2 text-sm leading-6 text-zinc-600">
                {stackOk === false
                  ? "后端未连接，当前无法发起请求。"
                  : "前端已准备好接收输入并开始新会话。"}
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
