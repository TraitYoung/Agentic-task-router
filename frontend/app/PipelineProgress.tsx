"use client";

import { PIPELINE_STEPS, pipelineStepIndex, type PipelineStepId } from "./pipelineSteps";

export function PipelineProgress({
  activeStep,
  visible,
  elapsedSec = 0,
  statusText,
}: {
  activeStep: PipelineStepId | null;
  visible: boolean;
  elapsedSec?: number;
  statusText?: string;
}) {
  if (!visible) return null;

  const activeIdx = pipelineStepIndex(activeStep);
  const sublabel =
    statusText?.replace(/^>\s*/, "") ||
    (activeStep ? undefined : "等待模型响应…");

  return (
    <div className="mb-3 rounded-xl border border-[color:var(--line)] bg-white/60 px-3 py-3">
      <ol className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-500">
        {PIPELINE_STEPS.map((step, i) => {
          const done = activeIdx > i;
          const active =
            activeIdx === i ||
            (activeStep === "discovery_done" && i === 1) ||
            (activeStep === "sprint_done" && i === 2) ||
            (activeStep === "implementation_done" && i === 3) ||
            (activeStep === "delivery_done" && i === 4) ||
            (activeStep === "test_code_done" && i === 5);
          return (
            <li key={step.id} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-zinc-300">›</span>}
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 transition-colors ${
                  active
                    ? "bg-[color:var(--accent)]/15 text-[color:var(--accent-strong)] animate-pulse font-medium"
                    : done
                      ? "text-emerald-700"
                      : "text-zinc-400"
                }`}
              >
                {done && !active ? (
                  <span aria-hidden className="text-[10px]">
                    ✓
                  </span>
                ) : active ? (
                  <span
                    aria-hidden
                    className="h-1.5 w-1.5 rounded-full bg-[color:var(--accent)] animate-pulse"
                  />
                ) : (
                  <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-zinc-300" />
                )}
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
      {(sublabel || elapsedSec > 0) && (
        <p className="mt-2 text-[11px] text-zinc-500">
          {sublabel}
          {elapsedSec > 2 ? ` · ${elapsedSec}s` : ""}
        </p>
      )}
      <div
        className={`progress-shimmer mt-2 h-1 w-full overflow-hidden rounded-full ${
          activeIdx >= 0 ? "bg-zinc-200/80" : "bg-zinc-100"
        }`}
        role="progressbar"
        aria-label="生成进度"
      />
    </div>
  );
}
