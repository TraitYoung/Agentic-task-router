"use client";

import { useState } from "react";
import type { Message } from "./types";
import { TracePanel } from "./TracePanel";
import { formatTs } from "./lib";

export function AssistantBubble({
  msg,
  isStreaming,
  elapsed,
}: {
  msg: Message;
  isStreaming: boolean;
  elapsed: number;
}) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    if (!msg.content) return;
    await navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="group flex flex-col gap-1 max-w-[80%]">
      <div className="relative rounded-2xl rounded-tl-sm bg-zinc-100 px-4 py-3 text-sm text-zinc-900 leading-relaxed">
        {isStreaming && !msg.content ? (
          <span className="flex items-center gap-1.5 text-zinc-400">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:300ms]" />
            {elapsed > 2 && (
              <span className="ml-1 text-[11px]">等待中 {elapsed}s...</span>
            )}
          </span>
        ) : (
          <pre className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed">
            {msg.content}
          </pre>
        )}
        {msg.content && !isStreaming && (
          <button
            type="button"
            onClick={onCopy}
            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity px-2 py-1 text-[11px] rounded bg-white border border-zinc-200 text-zinc-500 hover:text-zinc-800"
          >
            {copied ? "已复制" : "复制"}
          </button>
        )}
      </div>
      {msg.ts && (
        <span className="text-[11px] text-zinc-400 pl-1">{formatTs(msg.ts)}</span>
      )}
      {msg.traceSteps && msg.traceSteps.length > 0 && (
        <TracePanel steps={msg.traceSteps} traceId={msg.traceId} />
      )}
    </div>
  );
}

export function UserBubble({ msg }: { msg: Message }) {
  return (
    <div className="flex flex-col items-end gap-1 max-w-[80%] self-end">
      <div className="rounded-2xl rounded-tr-sm bg-zinc-900 px-4 py-3 text-sm text-white leading-relaxed">
        <pre className="whitespace-pre-wrap break-words font-sans">{msg.content}</pre>
      </div>
      {msg.ts && (
        <span className="text-[11px] text-zinc-400 pr-1">{formatTs(msg.ts)}</span>
      )}
    </div>
  );
}
