"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { canSendMessage, shouldSendOnEnter } from "./chatComposer";

type TraceStepRow = {
  index: number;
  node: string;
  ts: string;
  duration_ms: number;
  keys_written: string[];
  summary: Record<string, unknown>;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: string;
  traceId?: string;
  traceSteps?: TraceStepRow[];
};

type UiMode = "spec" | "review";

function safeParseJson(line: string): unknown | null {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function TracePanel({ steps, traceId }: { steps: TraceStepRow[]; traceId?: string }) {
  if (!steps.length) return null;
  return (
    <details className="mt-2 rounded-lg border border-zinc-200 text-xs">
      <summary className="cursor-pointer select-none px-3 py-2 font-medium text-zinc-500 hover:text-zinc-700 transition-colors">
        链路追踪 ({steps.length} 步)
        {traceId && (
          <span className="ml-2 font-mono text-zinc-400">{traceId.slice(0, 8)}…</span>
        )}
      </summary>
      <ol className="px-4 pb-3 pt-2 space-y-2 list-decimal text-zinc-600">
        {steps.map((s) => (
          <li key={`${s.index}-${s.node}`} className="break-words">
            <span className="font-mono text-zinc-800">{s.node}</span>
            <span className="text-zinc-400"> · {s.duration_ms} ms</span>
            <pre className="mt-1 whitespace-pre-wrap break-words text-[11px] bg-zinc-50 rounded p-2 border border-zinc-100 max-h-32 overflow-y-auto">
              {JSON.stringify(s.summary, null, 2)}
            </pre>
          </li>
        ))}
      </ol>
    </details>
  );
}

function AssistantBubble({ msg, isStreaming, elapsed }: { msg: Message; isStreaming: boolean; elapsed: number }) {
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
              <span className="ml-1 text-[11px]">等待中 {elapsed}s…</span>
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

function UserBubble({ msg }: { msg: Message }) {
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
      // 安全兜底：5 秒后强制清零，防止 onCompositionEnd 未触发导致按钮永久禁用
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

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function newSession() {
    const id = crypto.randomUUID();
    try {
      window.localStorage.setItem("x-session-id", id);
    } catch { /* ignore */ }
    setSessionId(id);
    setMessages([]);
    setError("");
    setText("");
    safeSetComposing(false);
  }

  useEffect(() => {
    if (!loading) {
      setElapsed(0);
      return;
    }
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
          backendHealth?: { redis?: boolean };
        };
        if (res.ok && data.ok) {
          setStackOk(true);
          if (data.backendHealth?.redis === false) {
            setStackHint("Redis 未连通：会话缓存不可用，但不影响核心功能。");
          }
        } else {
          setStackOk(false);
          setStackHint(data.detail || "无法连接后端，请确认 uvicorn 已在本机 8000 监听。");
        }
      } catch (e) {
        setStackOk(false);
        setStackHint(e instanceof Error ? e.message : "健康检查失败");
      }
    })();
  }, []);

  const loadHistory = useCallback(
    async (sid: string) => {
      if (!sid) return;
      try {
        const res = await fetch("/api/chat/history", {
          method: "GET",
          headers: { "x-session-id": sid },
        });
        if (!res.ok) return;
        const data = (await res.json()) as {
          turns?: { user: string; assistant: string; ts: string }[];
        };
        const turns = data.turns ?? [];
        if (!turns.length) return;
        const mapped: Message[] = turns.flatMap((t, i) => [
          {
            id: `hist-u-${i}`,
            role: "user" as const,
            content: t.user,
            ts: t.ts,
          },
          {
            id: `hist-a-${i}`,
            role: "assistant" as const,
            content: t.assistant,
            ts: t.ts,
          },
        ]);
        setMessages(mapped);
      } catch { /* ignore */ }
    },
    []
  );

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
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const parsed = safeParseJson(line.slice(5).trim());
          if (!parsed || typeof parsed !== "object") continue;
          const msg = parsed as Record<string, unknown>;

          if ("session_id" in msg && "intent" in msg) {
            if (msg.trace_id) collectedTraceId = String(msg.trace_id);
            if (msg.trace && Array.isArray(msg.trace))
              collectedTrace = msg.trace as TraceStepRow[];
            continue;
          }
          if (msg.type === "delta") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + (msg.content as string) }
                  : m
              )
            );
          }
          if (msg.type === "status") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId && !m.content
                  ? { ...m, content: `> ${msg.text as string}` }
                  : m
              )
            );
          }
        }
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsgId
            ? {
                ...m,
                traceId: collectedTraceId || undefined,
                traceSteps: collectedTrace.length ? collectedTrace : undefined,
              }
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
            m.id === assistantMsgId
              ? { ...m, content: `❌ ${hint}` }
              : m
          )
        );
      }
    } finally {
      setStreamingId(null);
      setLoading(false);
      abortRef.current = null;
    }
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    void onSend();
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
        method: "POST",
        headers: { "x-session-id": sessionId },
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

  const isEmpty = messages.length === 0 && !loading;
  const readyToSend = canSendMessage(text, sessionId, loading);
  const statusLabel = loading
    ? "生成中"
    : stackOk === false
    ? "后端未连接"
    : "会话已就绪";
  const promptSuggestions =
    mode === "spec"
      ? [
          "帮我拆解一个新功能的需求、范围和验收标准",
          "把一个模糊想法整理成 Sprint 计划和交付清单",
        ]
      : [
          "帮我审查这段代码的结构问题和潜在风险",
          "把现有实现反向整理成需求、测试点和重构路线",
        ];

  return (
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
                  loading
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
              {exporting ? "导出中…" : "导出"}
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
                  {promptSuggestions.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => {
                        setText(prompt);
                        textareaRef.current?.focus();
                      }}
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
                      `Enter` 发送，`Shift+Enter` 换行。中文输入法确认候选词时不会误触发送。
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
        ) : (
          <div className="mx-auto flex max-w-4xl flex-col gap-5 px-4 py-8">
            {messages.map((msg) =>
              msg.role === "user" ? (
                <UserBubble key={msg.id} msg={msg} />
              ) : (
                <AssistantBubble
                  key={msg.id}
                  msg={msg}
                  isStreaming={streamingId === msg.id}
                  elapsed={elapsed}
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

      {/* Composer */}
      <footer className="sticky bottom-0 flex-none border-t border-[color:var(--line)] bg-[color:var(--surface)]/95 px-4 py-4 backdrop-blur-xl">
        <form className="mx-auto w-full max-w-4xl" onSubmit={onSubmit}>
          <div className="rounded-[2rem] border border-white/70 bg-[color:var(--surface-strong)] px-4 py-4 shadow-[0_18px_50px_rgba(91,63,42,0.12)]">
            <div className="flex items-center justify-between gap-3 px-1 pb-3">
              <div className="text-xs text-zinc-500">
                {mode === "spec" ? "需求规格输入区" : "代码审查输入区"}
              </div>
              <div className="flex items-center gap-3 text-[11px] text-zinc-400">
                <span>{isComposing ? "输入法确认中…" : "Enter 发送"}</span>
                <span>{text.length > 0 ? `${text.length}/12k` : "最多 12k"}</span>
              </div>
            </div>

            <div className="flex items-end gap-3 rounded-[1.5rem] border border-[color:var(--line)] bg-white px-4 py-3 transition-colors focus-within:border-[rgba(201,111,59,0.45)]">
              <textarea
                ref={textareaRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                onCompositionStart={() => safeSetComposing(true)}
                onCompositionEnd={() => safeSetComposing(false)}
                disabled={loading}
                rows={1}
                placeholder={
                  mode === "spec"
                    ? "描述你的想法、范围、约束或期望交付物…"
                    : "粘贴待审查代码、模块说明或你想聚焦的问题…"
                }
                maxLength={12000}
                className="min-h-[56px] flex-1 resize-none bg-transparent py-1 text-sm leading-7 text-zinc-900 placeholder-zinc-400 focus:outline-none max-h-48"
                style={{ overflowY: "auto" }}
              />
              <div className="flex items-center gap-2 pb-1">
                {loading ? (
                  <button
                    type="button"
                    onClick={onStop}
                    className="flex h-11 w-11 items-center justify-center rounded-2xl bg-zinc-900 text-white transition-colors hover:bg-zinc-700"
                    aria-label="停止生成"
                  >
                    <svg width="13" height="13" viewBox="0 0 12 12" fill="currentColor">
                      <rect x="2" y="2" width="8" height="8" rx="1.2" />
                    </svg>
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!readyToSend}
                    className="flex h-11 min-w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#d9925a_0%,#8f3d1d_100%)] px-3 text-white shadow-[0_14px_30px_rgba(143,61,29,0.28)] transition-all hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-30"
                    aria-label="发送"
                  >
                    <svg
                      width="15"
                      height="15"
                      viewBox="0 0 14 14"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <line x1="7" y1="12" x2="7" y2="2" />
                      <polyline points="3,6 7,2 11,6" />
                    </svg>
                  </button>
                )}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 px-1 pt-3 text-[11px] text-zinc-400">
              <span>Shift+Enter 换行，支持多段输入和长文本粘贴。</span>
              {!stackOk && stackOk !== null && <span>后端未连接，请确认已启动全部服务。</span>}
            </div>
          </div>
        </form>
      </footer>
    </div>
  );
}
