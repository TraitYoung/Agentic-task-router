import type { TraceStepRow } from "./types";

export function TracePanel({ steps, traceId }: { steps: TraceStepRow[]; traceId?: string }) {
  if (!steps.length) return null;
  return (
    <details className="mt-2 rounded-lg border border-zinc-200 text-xs">
      <summary className="cursor-pointer select-none px-3 py-2 font-medium text-zinc-500 hover:text-zinc-700 transition-colors">
        链路追踪 ({steps.length} 步)
        {traceId && (
          <span className="ml-2 font-mono text-zinc-400">{traceId.slice(0, 8)}...</span>
        )}
      </summary>
      <ol className="px-4 pb-3 pt-2 space-y-2 list-decimal text-zinc-600">
        {steps.map((s) => (
          <li key={`${s.index}-${s.node}`} className="break-words">
            <span className="font-mono text-zinc-800">{s.node}</span>
            <span className="text-zinc-400"> &middot; {s.duration_ms} ms</span>
            <pre className="mt-1 whitespace-pre-wrap break-words text-[11px] bg-zinc-50 rounded p-2 border border-zinc-100 max-h-32 overflow-y-auto">
              {JSON.stringify(s.summary, null, 2)}
            </pre>
          </li>
        ))}
      </ol>
    </details>
  );
}
