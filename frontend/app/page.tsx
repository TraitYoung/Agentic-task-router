"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { canSendMessage, shouldSendOnEnter } from "./chatComposer";
import type { TraceStepRow, Message, UiMode } from "./types";
import { parseSseEvent } from "./lib";
import { AssistantBubble, UserBubble } from "./Bubble";
import { Composer } from "./Composer";
import { PipelineProgress } from "./PipelineProgress";
import {
  normalizePipelineStep,
  pipelineStepLabel,
  type PipelineStepId,
} from "./pipelineSteps";
import { WelcomeHero } from "./WelcomeHero";
import { ErrorBoundary } from "./ErrorBoundary";

export default function Home() {
  const [mode, setMode] = useState<UiMode>("spec");
  const [sessionId, setSessionId] = useState<string>(() => {
    try {
      const cached = window.localStorage.getItem("x-session-id");
      if (cached) return cached;
    } catch { /* ignore */ }
    const id = crypto.randomUUID();
    try { window.localStorage.setItem("x-session-id", id); } catch { /* ignore */ }
    return id;
  });
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const composingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const safeSetComposing = (v: boolean) => {
    setIsComposing(v);
    if (v) {
      if (composingTimer.current) clearTimeout(composingTimer.current);
      composingTimer.current = setTimeout(() => setIsComposing(false), 5000);
    } else {
      if (composingTimer.current) { clearTimeout(composingTimer.current); composingTimer.current = null; }
    }
  };
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [stackOk, setStackOk] = useState<boolean | null>(null);
  const [stackHint, setStackHint] = useState("");
  const [exporting, setExporting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [pipelineStep, setPipelineStep] = useState<PipelineStepId | null>(null);
  const [backendModel, setBackendModel] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function newSession() {
    const id = crypto.randomUUID();
    try { window.localStorage.setItem("x-session-id", id); } catch { /* ignore */ }
    setSessionId(id);
    setMessages([]);
    setError("");
    setText("");
    safeSetComposing(false);
  }

  useEffect(() => {
    if (!loading) { setElapsed(0); return; }
    const id = setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [loading]);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const data = (await res.json().catch(() => ({}))) as {
          ok?: boolean;
          detail?: string;
          backendHealth?: {
            redis?: boolean | { ok?: boolean };
            redis_ok?: boolean;
            env?: { llm_model?: string };
          };
        };
        if (res.ok && data.ok) {
          setStackOk(true);
          const model = data.backendHealth?.env?.llm_model;
          if (model) setBackendModel(model);
          const redisOk =
            typeof data.backendHealth?.redis === "object"
              ? data.backendHealth.redis.ok
              : data.backendHealth?.redis ?? data.backendHealth?.redis_ok;
          if (redisOk === false) {
            setStackHint("Redis 未连通：会话缓存不可用，但不影响核心功能。");
          }
        } else {
          setStackOk(false);
          setStackHint(
            data.detail ||
              "无法连接后端。若使用线上服务，Hugging Face Space 冷启动可能需要 20–30 秒，请稍后重试。"
          );
        }
      } catch (e) {
        setStackOk(false);
        setStackHint(e instanceof Error ? e.message : "健康检查失败");
      }
    })();
  }, []);

  const loadHistory = useCallback(async (sid: string) => {
    if (!sid) return;
    try {
      const res = await fetch("/api/chat/history", {
        method: "GET", headers: { "x-session-id": sid },
      });
      if (!res.ok) return;
      const data = (await res.json()) as { turns?: { user: string; assistant: string; ts: string }[] };
      const turns = data.turns ?? [];
      if (!turns.length) return;
      const mapped: Message[] = turns.flatMap((t, i) => [
        { id: `hist-u-${i}`, role: "user" as const, content: t.user, ts: t.ts },
        { id: `hist-a-${i}`, role: "assistant" as const, content: t.assistant, ts: t.ts },
      ]);
      setMessages(mapped);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (sessionId) void loadHistory(sessionId);
  }, [sessionId, loadHistory]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingId]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
  }, [text]);

  useEffect(() => {
    if (!loading) textareaRef.current?.focus();
  }, [loading, mode]);

  async function onSend() {
    const trimmed = text.trim();
    if (!trimmed || !sessionId || loading) return;

    setLoading(true);
    setError("");
    setText("");
    setPipelineStep(null);

    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();
    const now = new Date().toISOString();

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: trimmed, ts: now },
      { id: assistantMsgId, role: "assistant", content: "", ts: now },
    ]);
    setStreamingId(assistantMsgId);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const outboundTraceId = crypto.randomUUID?.() ?? "";
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-session-id": sessionId,
          ...(outboundTraceId ? { "x-trace-id": outboundTraceId } : {}),
        },
        body: JSON.stringify({ text: trimmed.slice(0, 12000), mode }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const ct = res.headers.get("content-type") ?? "";
        if (ct.includes("application/json")) {
          const j = (await res.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(j?.detail ?? `HTTP ${res.status}`);
        }
        throw new Error(`HTTP ${res.status}`);
      }
      if (!res.body) throw new Error("响应无正文");

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buf = "";
      let collectedTraceId = "";
      let collectedTrace: TraceStepRow[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const msg = parseSseEvent(part);
          if (!msg) continue;

          if (msg.type === "meta") {
            if (msg.trace_id) collectedTraceId = String(msg.trace_id);
            if (msg.trace && Array.isArray(msg.trace))
              collectedTrace = msg.trace as TraceStepRow[];
            continue;
          }
          if (msg.type === "done") {
            continue;
          }
          if (msg.type === "delta") {
            continue;
          }
          if (msg.type === "status") {
            const step = normalizePipelineStep(String(msg.step ?? ""));
            if (step) setPipelineStep(step);
            const statusLine = `> ${msg.text as string}`;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, content: statusLine } : m
              )
            );
          }
          if (msg.type === "artifact") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      artifactMd: String(msg.content ?? ""),
                      artifactPath: String(msg.file_path ?? ""),
                      artifactFilename: String(msg.filename ?? "SPEC.md"),
                    }
                  : m
              )
            );
          }
          if (msg.type === "reply") {
            const full = String(msg.content ?? "");
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId ? { ...m, content: full } : m
              )
            );
          }
          if (msg.type === "error") {
            const detail = typeof msg.detail === "string" ? msg.detail : "后端生成失败";
            const step = typeof msg.step === "string" && msg.step ? msg.step : "";
            const label = step ? `步骤「${step}」失败` : "后端生成失败";
            setError(detail);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: `${label}：${detail}` }
                  : m
              )
            );
          }
        }
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? { ...m, traceId: collectedTraceId || undefined, traceSteps: collectedTrace.length ? collectedTrace : undefined }
            : m
        )
      );
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId && !m.content
              ? { ...m, content: "（已停止生成）" }
              : m
          )
        );
      } else {
        const rawMsg = e instanceof Error ? e.message : "请求失败";
        const hint = rawMsg.includes("无法连接") || rawMsg.includes("fetch") || rawMsg.includes("503")
          ? `请求失败：后端服务不可用。请双击项目根目录的 start_dev.bat 启动全部服务。\n\n原始错误：${rawMsg}`
          : `请求失败：${rawMsg}`;
        setError(hint);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, content: `❌ ${hint}` } : m
          )
        );
      }
    } finally {
      setStreamingId(null);
      setLoading(false);
      setPipelineStep(null);
      abortRef.current = null;
    }
  }

  function onStop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (
      shouldSendOnEnter({
        key: e.key,
        shiftKey: e.shiftKey,
        isComposing: isComposing || e.nativeEvent.isComposing,
        keyCode: "keyCode" in e.nativeEvent ? e.nativeEvent.keyCode : undefined,
      })
    ) {
      e.preventDefault();
      void onSend();
    }
  }

  async function onExport() {
    if (!sessionId || exporting) return;
    setExporting(true);
    try {
      const res = await fetch("/api/chat/export", {
        method: "POST", headers: { "x-session-id": sessionId },
      });
      if (!res.ok) throw new Error(`导出失败 HTTP ${res.status}`);
      const data: unknown = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `specforge-export-${new Date().toISOString().slice(0, 16).replace(/[T:]/g, "-")}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  function onPromptClick(prompt: string) {
    setText(prompt);
    textareaRef.current?.focus();
  }

  const isEmpty = messages.length === 0 && !loading;
  const readyToSend = canSendMessage(text, sessionId, loading);
  const statusLabel = loading
    ? pipelineStepLabel(pipelineStep, mode)
    : stackOk === null
      ? "正在连接后端…"
      : stackOk === false
        ? "后端未连接"
        : backendModel
          ? `会话已就绪 · ${backendModel}`
          : "会话已就绪";

  return (
    <ErrorBoundary>
      <div className="flex min-h-screen flex-col text-zinc-900">
        {/* Top bar */}
        <header className="sticky top-0 z-20 flex-none border-b border-[color:var(--line)] bg-[color:var(--surface)]/95 px-5 py-4 backdrop-blur-xl">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#d9925a_0%,#8f3d1d_100%)] text-sm font-semibold text-white shadow-[0_10px_30px_rgba(143,61,29,0.22)]">
                SF
              </div>
              <div>
                <div className="font-semibold tracking-[0.18em] text-zinc-900 uppercase text-[11px]">
                  SpecForge
                </div>
                <div className="text-sm text-zinc-500">
                  把想法和代码整理成更可执行的工程规格
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-2 rounded-full border border-[color:var(--line)] bg-white/70 px-3 py-1.5 text-xs text-zinc-500 sm:flex">
                <span
                  className={`h-2 w-2 rounded-full ${
                    loading || stackOk === null
                      ? "bg-sky-500 animate-pulse"
                      : stackOk === false
                        ? "bg-red-500"
                        : "bg-emerald-500"
                  }`}
                />
                <span>{statusLabel}</span>
              </div>

              <div className="flex overflow-hidden rounded-xl border border-[color:var(--line)] bg-white/80 text-xs shadow-sm">
                <button
                  type="button"
                  onClick={() => setMode("spec")}
                  disabled={loading}
                  className={`px-3 py-2 transition-colors ${
                    mode === "spec"
                      ? "bg-zinc-900 text-white"
                      : "bg-white/40 text-zinc-500 hover:bg-zinc-50"
                  }`}
                >
                  Spec
                </button>
                <button
                  type="button"
                  onClick={() => setMode("review")}
                  disabled={loading}
                  className={`border-l border-[color:var(--line)] px-3 py-2 transition-colors ${
                    mode === "review"
                      ? "bg-zinc-900 text-white"
                      : "bg-white/40 text-zinc-500 hover:bg-zinc-50"
                  }`}
                >
                  Review
                </button>
              </div>

              <button
                type="button"
                onClick={() => void onExport()}
                disabled={exporting || messages.length === 0}
                className="rounded-full border border-[color:var(--line)] bg-white/80 px-3 py-2 text-xs text-zinc-500 shadow-sm transition-colors hover:text-zinc-800 disabled:opacity-30"
              >
                {exporting ? "导出中..." : "导出"}
              </button>

              <button
                type="button"
                onClick={newSession}
                disabled={loading}
                className="rounded-full border border-[color:var(--line)] bg-zinc-900 px-3 py-2 text-xs text-white shadow-sm transition-colors hover:bg-zinc-800 disabled:opacity-30"
              >
                新对话
              </button>
            </div>
          </div>
        </header>

        {/* Hint banner */}
        {(stackOk === false || stackHint) && (
          <div
            className={`mx-auto mt-4 w-[calc(100%-2rem)] max-w-6xl flex-none rounded-2xl px-4 py-3 text-xs shadow-sm ${
              stackOk === false
                ? "bg-red-50 border border-red-200 text-red-700"
                : "bg-amber-50 border border-amber-200 text-amber-700"
            }`}
          >
            {stackOk === false ? (
              <>
                <span className="font-medium">后端链路异常</span>
                {stackHint && <span className="ml-1.5 opacity-80">{stackHint}</span>}
              </>
            ) : (
              stackHint
            )}
          </div>
        )}

        {/* Messages area */}
        <main className="flex-1 overflow-y-auto">
          {isEmpty ? (
            <WelcomeHero mode={mode} stackOk={stackOk} onPromptClick={onPromptClick} />
          ) : (
            <div className="mx-auto flex max-w-4xl flex-col gap-5 px-4 py-8">
              <PipelineProgress activeStep={pipelineStep} visible={loading} />
              {messages.map((msg) =>
                msg.role === "user" ? (
                  <UserBubble key={msg.id} msg={msg} />
                ) : (
                  <AssistantBubble
                    key={msg.id}
                    msg={msg}
                    isStreaming={streamingId === msg.id}
                    elapsed={elapsed}
                    stageLabel={pipelineStepLabel(pipelineStep, mode)}
                    mode={mode}
                  />
                )
              )}
              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </main>

        <Composer
          mode={mode}
          text={text}
          loading={loading}
          readyToSend={readyToSend}
          isComposing={isComposing}
          stackOk={stackOk}
          textareaRef={textareaRef}
          onTextChange={setText}
          onSend={onSend}
          onStop={onStop}
          onKeyDown={onKeyDown}
          onCompositionStart={() => safeSetComposing(true)}
          onCompositionEnd={() => safeSetComposing(false)}
        />
      </div>
    </ErrorBoundary>
  );
}
