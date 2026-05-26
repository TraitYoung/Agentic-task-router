"use client";

import { Fragment, useState } from "react";
import type { Message, UiMode } from "./types";
import { TracePanel } from "./TracePanel";
import { StageChoicePanel } from "./StageChoicePanel";
import { StreamingStatusBar } from "./StreamingStatusBar";
import { StagePartialPanel } from "./StagePartialPanel";
import { formatTs } from "./lib";
import {
  downloadMarkdown,
  extractGeneratedTestFiles,
  extractImplementationPrompt,
  extractReviewPrompt,
  extractTestPrompt,
} from "./lib/artifact";

function SummaryBody({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1" />;
        if (trimmed.startsWith("## ") || trimmed.startsWith("### ")) {
          return (
            <h3 key={i} className="text-base font-semibold text-zinc-900 pt-1">
              {trimmed.replace(/^#+\s*/, "")}
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
  onStageChoice,
  onStageRetry,
  choiceDisabled,
  choiceLoadingId,
}: {
  msg: Message;
  isStreaming: boolean;
  elapsed: number;
  stageLabel?: string;
  mode?: UiMode;
  onStageChoice?: (choiceId: "A" | "B" | "C" | "D", checkpointId: string) => void;
  onStageRetry?: (checkpointId: string, choice: "A" | "B" | "C" | "D") => void;
  choiceDisabled?: boolean;
  choiceLoadingId?: string | null;
}) {
  const [copied, setCopied] = useState<"prompt" | "test" | "testcode" | "full" | null>(null);
  const hasArtifact = Boolean(msg.artifactMd?.trim());
  const isReview = mode === "review";
  const pendingChoice = msg.stageChoices?.find((c) => !c.selected && msg.awaitingChoice);
  const statusLine = msg.streamStatusText || (msg.content.startsWith("> ") ? msg.content : "");

  async function copyText(label: "prompt" | "test" | "testcode" | "full", text: string) {
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
  const testPromptText = hasArtifact && !isReview ? extractTestPrompt(msg.artifactMd!) : "";
  const testCodeText = hasArtifact && !isReview ? extractGeneratedTestFiles(msg.artifactMd!) : "";

  return (
    <div className="group flex flex-col gap-1 max-w-[80%]">
      <div className="relative rounded-2xl rounded-tl-sm bg-zinc-100 px-4 py-3 text-sm text-zinc-900 leading-relaxed">
        {msg.stagePartials?.map((partial) => (
          <StagePartialPanel
            key={partial.step}
            partial={partial}
            isActive={msg.activePartialStep === partial.step}
            defaultCollapsed={msg.activePartialStep !== partial.step}
          >
            <SummaryBody text={partial.markdown} />
          </StagePartialPanel>
        ))}

        {isStreaming ? (
          <StreamingStatusBar
            label={
              stageLabel ||
              (!msg.stagePartials?.length && !statusLine ? "准备中" : "生成中…")
            }
            statusText={statusLine}
            elapsed={elapsed}
          />
        ) : null}

        {msg.stageChoices?.map((choice) =>
          choice.selected || pendingChoice?.checkpointId === choice.checkpointId ? (
            <StageChoicePanel
              key={choice.checkpointId}
              choice={choice}
              disabled={choiceDisabled || Boolean(choice.selected && !choice.retryable)}
              loading={choiceLoadingId === choice.checkpointId}
              onSelect={(id, checkpointId) => onStageChoice?.(id, checkpointId)}
              onRetry={(cp, c) => onStageRetry?.(cp, c)}
            />
          ) : null
        )}

        {msg.testCodeStream ? (
          <div className="mt-3 border-t border-zinc-200/80 pt-3">
            <p className="mb-2 text-[12px] font-medium text-zinc-600">测试代码生成中…</p>
            <pre className="whitespace-pre-wrap text-[12px] leading-relaxed text-zinc-800 font-sans">
              {msg.testCodeStream}
            </pre>
          </div>
        ) : null}

        {msg.mergeStream ? (
          <div className="mt-3 border-t border-zinc-200/80 pt-3">
            <p className="mb-2 text-[12px] font-medium text-zinc-600">发布说明生成中…</p>
            <pre className="whitespace-pre-wrap text-[12px] leading-relaxed text-zinc-800 font-sans">
              {msg.mergeStream}
            </pre>
          </div>
        ) : null}

        {msg.content && !msg.content.startsWith("> ") && !msg.stagePartials?.length && !msg.mergeStream && !msg.testCodeStream ? (
          <SummaryBody text={msg.content} />
        ) : msg.content && !msg.content.startsWith("> ") && (hasArtifact || !isStreaming) ? (
          <div className="mt-3 border-t border-zinc-200/80 pt-3">
            <SummaryBody text={msg.content} />
          </div>
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
            {!isReview && testPromptText && (
              <button
                type="button"
                onClick={() => copyText("test", testPromptText)}
                className="px-2.5 py-1.5 text-[11px] rounded-md bg-white border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
              >
                {copied === "test" ? "已复制" : "复制测试 Prompt"}
              </button>
            )}
            {!isReview && testCodeText && (
              <button
                type="button"
                onClick={() => copyText("testcode", testCodeText)}
                className="px-2.5 py-1.5 text-[11px] rounded-md bg-white border border-zinc-200 text-zinc-700 hover:bg-zinc-50"
              >
                {copied === "testcode" ? "已复制" : "复制测试代码"}
              </button>
            )}
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
