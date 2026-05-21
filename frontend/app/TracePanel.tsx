import type { TraceStepRow } from "./types";

export function TracePanel({ steps, traceId }: { steps: TraceStepRow[]; traceId?: string }) {
  if (!steps.length) return null;
  const totalDurationMs = steps.reduce((sum, s) => sum + (Number(s.duration_ms) || 0), 0);
  const estimatedTokens = steps.reduce(
    (sum, s) => sum + (Number(s.summary?._metrics?.estimated_tokens) || 0),
    0
  );
  const memoryMb = steps
    .map((s) => Number(s.summary?._metrics?.memory_mb) || 0)
    .filter((n) => n > 0)
    .at(-1);

  return (
    <details className="mt-2 rounded-lg border border-zinc-200 text-xs">
      <summary className="cursor-pointer select-none px-3 py-2 font-medium text-zinc-500 hover:text-zinc-700 transition-colors">
        链路追踪 ({steps.length} 步)
        {traceId && (
          <span className="ml-2 font-mono text-zinc-400">{traceId.slice(0, 8)}...</span>
        )}
      </summary>
      <div className="mx-3 mt-2 grid grid-cols-3 gap-2 rounded-md border border-zinc-100 bg-zinc-50 p-2 text-[11px] text-zinc-500">
        <div>
          <div className="font-medium text-zinc-800">{Math.round(totalDurationMs)} ms</div>
          <div>total</div>
        </div>
        <div>
          <div className="font-medium text-zinc-800">{estimatedTokens}</div>
          <div>est. tokens</div>
        </div>
        <div>
          <div className="font-medium text-zinc-800">{memoryMb ? `${memoryMb} MB` : "n/a"}</div>
          <div>memory</div>
        </div>
      </div>
      <ol className="px-4 pb-3 pt-2 space-y-2 list-decimal text-zinc-600">
        {steps.map((s) => {
          const summary = s.summary as Record<string, unknown> | undefined;
          const delivery = summary?.delivery as Record<string, unknown> | undefined;
          const testCount =
            delivery?.test_cases_count ??
            (Array.isArray(delivery?.test_cases) ? delivery.test_cases.length : undefined);
          const testFiles = summary?.test_files_count;
          const hint =
            testCount != null
              ? ` · ${testCount} 条用例`
              : testFiles != null
                ? ` · ${testFiles} 个测试文件`
                : "";
          return (
          <li key={`${s.index}-${s.node}`} className="break-words">
            <span className="font-mono text-zinc-800">{s.node}</span>
            <span className="text-zinc-400">
              {" "}
              &middot; {s.duration_ms} ms{hint}
            </span>
            <pre className="mt-1 whitespace-pre-wrap break-words text-[11px] bg-zinc-50 rounded p-2 border border-zinc-100 max-h-32 overflow-y-auto">
              {JSON.stringify(s.summary, null, 2)}
            </pre>
          </li>
          );
        })}
      </ol>
    </details>
  );
}
