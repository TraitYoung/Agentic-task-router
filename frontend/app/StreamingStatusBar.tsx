"use client";

type Props = {
  label: string;
  statusText?: string;
  elapsed: number;
};

export function StreamingStatusBar({ label, statusText, elapsed }: Props) {
  const showLongHint = elapsed > 30;
  const display = statusText?.replace(/^>\s*/, "") || label;

  return (
    <div
      className="mt-3 rounded-lg border border-sky-200/80 bg-sky-50/70 px-3 py-2.5"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2 text-[13px] text-sky-900">
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:0ms]" />
          <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:150ms]" />
          <span className="h-1.5 w-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:300ms]" />
        </span>
        <span className="text-shimmer font-medium">{display}</span>
        {elapsed > 2 ? (
          <span className="text-[11px] text-sky-700/80 tabular-nums">{elapsed}s</span>
        ) : null}
      </div>
      {showLongHint ? (
        <p className="mt-1.5 text-[11px] text-amber-800/90">
          模型单步约 1~3 分钟，连接保持中，请勿刷新页面…
        </p>
      ) : null}
    </div>
  );
}
