"use client";

import { Fragment, useState } from "react";
import type { Message, UiMode } from "./types";
import { TracePanel } from "./TracePanel";
import { formatTs } from "./lib";
import {
  downloadMarkdown,
  extractImplementationPrompt,
  extractReviewPrompt,
} from "./lib/artifact";

function SummaryBody({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1" />;
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={i} className="text-base font-semibold text-zinc-900 pt-1">
              {trimmed.slice(3)}
            </h3>
          );
        }
        if (trimmed === "---") {
          return <hr key={i} className="my-2 border-zinc-200" />;
        }
        const parts = trimmed.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
        return (
          <p key={i} className="text-zinc-800 pl-0.5">
            {parts.map((part, j) => {
              if (part.startsWith("**") && part.endsWith("**")) {
                return (
                  <strong key={j} className="font-semibold text-zinc-900">
                    {part.slice(2, -2)}
                  </strong>
                );
              }
              if (part.startsWith("`") && part.endsWith("`")) {
                return (
                  <code
                    key={j}
                    className="text-[12px] bg-zinc-200/60 px-1 rounded font-mono"
                  >
                    {part.slice(1, -1)}
                  </code>
                );
              }
              return <Fragment key={j}>{part}</Fragment>;
            })}
          </p>
        );
      })}
    </div>
  );
}

export function AssistantBubble({
  msg,
  isStreaming,
  elapsed,
  stageLabel,
  mode = "spec",
}: {
  msg: Message;
  isStreaming: boolean;
  elapsed: number;
  stageLabel?: string;
  mode?: UiMode;
}) {
  const [copied, setCopied] = useState<"prompt" | "full" | null>(null);
  const isStatusOnly = msg.content.startsWith("> ") && isStreaming;
  const showThinkingHint = isStreaming && elapsed > 30;
  const hasArtifact = Boolean(msg.artifactMd?.trim());
  const isReview = mode === "review";

  async function copyText(label: "prompt" | "full", text: string) {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  }

  function onDownload() {
    if (!msg.artifactMd) return;
    downloadMarkdown(
      msg.artifactFilename ?? (isReview ? "REVIEW.md" : "SPEC.md"),
      msg.artifactMd
    );
  }

  const promptText = hasArtifact
    ? isReview
      ? extractReviewPrompt(msg.artifactMd!)
      : extractImplementationPrompt(msg.artifactMd!)
    : "";

  return (
    <div className="group flex flex-col gap-1 max-w-[80%]">
      <div className="relative rounded-2xl rounded-tl-sm bg-zinc-100 px-4 py-3 text-sm text-zinc-900 leading-relaxed">
        {isStreaming && !msg.content && !hasArtifact ? (
          <span className="flex flex-col gap-2 text-zinc-400">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce [animation-delay:300ms]" />
              <span className="ml-1 text-[11px]">
                {stageLabel || "准备中"}
                {elapsed > 2 ? ` · ${elapsed}s` : ""}
              </span>
            </span>
            {showThinkingHint && (
              <span className="text-[11px] text-amber-700/90">
                思考模式耗时较长，请耐心等待…
              </span>
            )}
          </span>
        ) : isStatusOnly ? (
          <p className="text-shimmer text-[13px] text-zinc-500">{msg.content}</p>
        ) : msg.content && !msg.content.startsWith("> ") ? (
          <SummaryBody text={msg.content} />
        ) : msg.content ? (
          <p className="text-[13px] text-zinc-500">{msg.content}</p>
        ) : null}

        {hasArtifact && !isStreaming && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-zinc-200/80 pt-3">
            <button
              type="button"
              onClick={() => copyText("prompt", promptText)}
              className="px-2.5 py-1.5 text-[11px] rounded-md bg-white border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
            >
              {copied === "prompt"
                ? "已复制"
                : isReview
                  ? "复制改进 Prompt"
                  : "复制实现 Prompt"}
            </button>
            <button
              type="button"
              onClick={() => copyText("full", msg.artifactMd!)}
              className="px-2.5 py-1.5 text-[11px] rounded-md bg-white border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
            >
              {copied === "full" ? "已复制" : "复制全文"}
            </button>
            <button
              type="button"
              onClick={onDownload}
              className="px-2.5 py-1.5 text-[11px] rounded-md bg-zinc-900 text-white hover:bg-zinc-800"
            >
              下载 {isReview ? "REVIEW.md" : "SPEC.md"}
            </button>
          </div>
        )}
      </div>
      {msg.artifactPath && !isStreaming && (
        <span className="text-[11px] text-zinc-400 pl-1">
          已保存: {msg.artifactPath}
        </span>
      )}
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
