"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Intent = {
  task_type?: string;
};

type SSEMsg =
  | { type: "meta"; session_id: string; intent: Intent }
  | { type: "delta"; content: string }
  | { type: "done" };

function safeParseJson(line: string): unknown | null {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

function agentName(taskType?: string) {
  switch (taskType) {
    case "emotion":
      return "情绪（bina）";
    case "taki":
      return "文档（taki）";
    case "bit":
      return "代码（bit）";
    case "juzheng":
      return "战略（juzheng）";
    default:
      return "未知";
  }
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string>("");
  const [text, setText] = useState<string>("");
  const [reply, setReply] = useState<string>("");
  const [activeAgent, setActiveAgent] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const cached = window.localStorage.getItem("x-session-id");
    if (cached) {
      setSessionId(cached);
      return;
    }
    const id = crypto.randomUUID();
    window.localStorage.setItem("x-session-id", id);
    setSessionId(id);
  }, []);

  const disableSend = useMemo(() => loading || !text.trim() || !sessionId, [loading, text, sessionId]);

  async function onSend() {
    setLoading(true);
    setError("");
    setReply("");
    setActiveAgent("");

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-session-id": sessionId,
        },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buf = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });

        // SSE 事件块以空行分隔：\n\n
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.slice(5).trim();
          const parsed = safeParseJson(jsonStr);
          if (!parsed || typeof parsed !== "object") continue;
          const msg = parsed as SSEMsg;
          if (!("type" in msg)) continue;

          if (msg.type === "meta") {
            setActiveAgent(agentName(msg.intent?.task_type));
          } else if (msg.type === "delta") {
            setReply((prev) => prev + msg.content);
          } else if (msg.type === "done") {
            // no-op
          }
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "请求失败";
      setError(msg);
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function onStop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  }

  return (
    <main className="min-h-screen p-6 flex flex-col items-center gap-4">
      <div className="w-full max-w-3xl bg-white dark:bg-black rounded-xl border border-zinc-200 dark:border-zinc-800 p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-lg font-semibold">Axiodrasil 演示（流式输出 + 路由分区）</div>
            <div className="text-sm text-zinc-500 dark:text-zinc-400">
              当前路由：<b>{activeAgent || "—"}</b>
            </div>
          </div>
          <button
            className="px-3 py-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-sm"
            onClick={() => {
              window.localStorage.removeItem("x-session-id");
              window.location.reload();
            }}
          >
            重置 session
          </button>
        </div>

        <div className="flex gap-2">
          <input
            className="flex-1 border border-zinc-200 dark:border-zinc-800 rounded-lg px-3 py-2 bg-transparent text-sm"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="输入：情绪/文档/代码/战略（例如：把 README 变成阅读路线）"
            maxLength={1000}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) onSend();
            }}
            disabled={loading}
          />
          {!loading ? (
            <button
              className="px-4 py-2 rounded-lg bg-black dark:bg-white text-white dark:text-black text-sm"
              onClick={onSend}
              disabled={disableSend}
            >
              发送
            </button>
          ) : (
            <button
              className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm"
              onClick={onStop}
            >
              停止
            </button>
          )}
        </div>

        {error ? (
          <div className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</div>
        ) : null}

        <div className="mt-4">
          <div className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">模型输出</div>
          <pre className="whitespace-pre-wrap bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg p-3 text-sm min-h-[120px]">
            {reply || (loading ? "正在生成..." : "等待输入")}
          </pre>
        </div>
      </div>
    </main>
  );
}
