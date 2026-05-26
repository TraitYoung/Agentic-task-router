"use client";

import type { ChoiceId, StageChoice } from "./types";

type Props = {
  choice: StageChoice;
  disabled?: boolean;
  loading?: boolean;
  onSelect: (choiceId: ChoiceId, checkpointId: string) => void;
  onRetry?: (checkpointId: string, choice: ChoiceId) => void;
};

export function StageChoicePanel({
  choice,
  disabled,
  loading,
  onSelect,
  onRetry,
}: Props) {
  const isSelected = Boolean(choice.selected);
  const selectedOpt = choice.options.find((o) => o.id === choice.selected);
  const showRetry = choice.retryable && choice.selected && choice.lastChoice;

  if (isSelected && !loading && !showRetry) {
    return (
      <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50/80 px-3 py-2 text-[12px] text-zinc-600">
        已选 <span className="font-semibold text-zinc-800">{choice.selected}</span>
        {selectedOpt ? ` · ${selectedOpt.label}` : ""}
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-xl border border-amber-200/80 bg-amber-50/60 p-3">
      <p className="mb-2 text-[12px] font-medium text-amber-900">
        {loading && isSelected ? (
          <span className="inline-flex items-center gap-2">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-amber-600 border-t-transparent" />
            已选 {choice.selected}，正在生成…
          </span>
        ) : showRetry ? (
          "上一步失败，可重试"
        ) : (
          "请选择下一步方向"
        )}
      </p>
      {showRetry && choice.lastChoice ? (
        <button
          type="button"
          onClick={() => onRetry?.(choice.checkpointId, choice.lastChoice!)}
          className="rounded-lg border border-amber-300 bg-white px-3 py-2 text-[12px] font-medium text-amber-900 hover:bg-amber-50"
        >
          重试（{choice.lastChoice}）
        </button>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {choice.options.map((opt) => {
            const active = choice.selected === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                disabled={disabled || isSelected || loading}
                onClick={() => onSelect(opt.id, choice.checkpointId)}
                className={`rounded-lg border px-3 py-2 text-left text-[12px] transition-colors ${
                  active
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-amber-200 bg-white text-zinc-800 hover:border-amber-400 hover:bg-amber-50"
                } disabled:cursor-not-allowed disabled:opacity-50`}
              >
                <span className="font-semibold">
                  {opt.id}
                  {opt.id === "D" ? " · 综合全部" : ""}
                </span>
                <span className="ml-1.5">{opt.label}</span>
                <p className={`mt-1 leading-snug ${active ? "text-zinc-200" : "text-zinc-500"}`}>
                  {opt.description}
                </p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
