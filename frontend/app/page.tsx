"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Intent = {
  task_type?: string;
};

type SSEMsg =
  | { type: "meta"; session_id: string; intent: Intent }
  | { session_id: string; intent: Intent }
  | { type: "delta"; content: string }
  | { type: "done" };

type ChatTurn = {
  user: string;
  assistant: string;
  ts: string;
};

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
  const TURN_LIMIT = 50;
  const [mode, setMode] = useState<"chat" | "clean">("chat");
  const [sessionId, setSessionId] = useState<string>("");
  const [text, setText] = useState<string>("");
  const [reply, setReply] = useState<string>("");
  const [activeAgent, setActiveAgent] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [exporting, setExporting] = useState<boolean>(false);
  const [exportMessage, setExportMessage] = useState<string>("");
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [activeTurnIdx, setActiveTurnIdx] = useState<number>(-1);
  const [inputDir, setInputDir] = useState<string>("input");
  const [defaultFiles, setDefaultFiles] = useState<string[]>([]);
  const [selectedDefaultFile, setSelectedDefaultFile] = useState<string>("");
  const [selectedDefaultFileContent, setSelectedDefaultFileContent] = useState<string>("");
  const [customFileName, setCustomFileName] = useState<string>("");
  const [customFileContent, setCustomFileContent] = useState<string>("");
  const [systemMode, setSystemMode] = useState<"manual" | "file">("manual");
  const [manualSystemInstruction, setManualSystemInstruction] = useState<string>("");
  const [systemFileName, setSystemFileName] = useState<string>("");
  const [systemFileContent, setSystemFileContent] = useState<string>("");
  const [stackOk, setStackOk] = useState<boolean | null>(null);
  const [stackHint, setStackHint] = useState<string>("");

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    try {
      const cached = window.localStorage.getItem("x-session-id");
      if (cached) {
        setSessionId(cached);
        return;
      }
      const id = crypto.randomUUID();
      window.localStorage.setItem("x-session-id", id);
      setSessionId(id);
    } catch {
      setSessionId(crypto.randomUUID());
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const data = (await res.json().catch(() => ({}))) as {
          ok?: boolean;
          detail?: string;
          backend?: string;
          backendHealth?: { redis?: boolean };
        };
        if (res.ok && data.ok) {
          setStackOk(true);
          if (data.backendHealth && data.backendHealth.redis === false) {
            setStackHint("Redis 未连通：历史/导出可能异常，请检查 6379 或停掉系统 Redis 后重开 dev_stack。");
          } else {
            setStackHint("");
          }
        } else {
          setStackOk(false);
          setStackHint(
            data.detail ||
              `Next 无法访问后端 ${data.backend || "127.0.0.1:8000"}，请确认 uvicorn 已在本机 8000 监听。`
          );
        }
      } catch (e) {
        setStackOk(false);
        setStackHint(e instanceof Error ? e.message : "健康检查失败");
      }
    })();
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    void (async () => {
      try {
        const res = await fetch("/api/chat/history", {
          method: "GET",
          headers: {
            "x-session-id": sessionId,
          },
        });
        if (!res.ok) {
          const data = (await res.json().catch(() => ({}))) as { detail?: string };
          setError(
            data.detail ||
              `加载历史失败 (HTTP ${res.status})。若页面卡住过久，多半是 Redis 阻塞或后端未启动。`
          );
          return;
        }
        setError("");
        const data = (await res.json()) as { turns?: ChatTurn[] };
        const turns = data.turns || [];
        setHistory(turns);
        setActiveTurnIdx(turns.length > 0 ? turns.length - 1 : -1);
      } catch {
        setError("加载历史时网络错误，请确认前端 dev 与后端均已启动。");
      }
    })();
  }, [sessionId]);

  async function loadDefaultFiles(dir: string) {
    try {
      const res = await fetch(`/api/cleaning/files?dir=${encodeURIComponent(dir)}`);
      const data = (await res.json()) as { files?: string[]; detail?: string };
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      const files = data.files || [];
      setDefaultFiles(files);
      if (files.length > 0 && !files.includes(selectedDefaultFile)) {
        setSelectedDefaultFile(files[0]);
      }
      if (files.length === 0) {
        setSelectedDefaultFile("");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "加载文件列表失败";
      setError(msg);
    }
  }

  useEffect(() => {
    if (mode === "clean") {
      void loadDefaultFiles(inputDir);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  useEffect(() => {
    if (mode !== "clean" || !selectedDefaultFile) {
      setSelectedDefaultFileContent("");
      return;
    }
    void (async () => {
      try {
        const res = await fetch(
          `/api/cleaning/files?dir=${encodeURIComponent(inputDir)}&file=${encodeURIComponent(selectedDefaultFile)}`
        );
        if (!res.ok) {
          setSelectedDefaultFileContent("");
          return;
        }
        const data = (await res.json()) as { content?: string };
        setSelectedDefaultFileContent(data.content || "");
      } catch {
        setSelectedDefaultFileContent("");
      }
    })();
  }, [mode, inputDir, selectedDefaultFile]);

  const disableSend = useMemo(() => {
    if (!sessionId || loading) return true;
    if (history.length >= TURN_LIMIT) return true;
    if (mode === "clean") return false;
    return !text.trim();
  }, [loading, mode, sessionId, text, history.length]);

  function composePayloadText(): string {
    if (mode !== "clean") return text.trim();

    const baseTask = text.trim() || "请执行日志清洗任务";
    const lines: string[] = [
      "[清洗模式请求]",
      "请优先执行日志清洗与归档流水线（关键词：sft/jsonl/logs/archive/system instruction）。",
      `任务描述：${baseTask}`,
      `默认 input 目录：${inputDir}`,
    ];

    if (selectedDefaultFile) {
      lines.push(`默认目录选中文件：${selectedDefaultFile}`);
      if (selectedDefaultFileContent) {
        lines.push(`默认目录文件内容（节选）：\n${selectedDefaultFileContent.slice(0, 3000)}`);
      }
    }
    if (customFileName) {
      lines.push(`自定义文件：${customFileName}`);
      if (customFileContent) {
        lines.push(`自定义文件内容（节选）：\n${customFileContent.slice(0, 3000)}`);
      }
    }

    if (systemMode === "manual" && manualSystemInstruction.trim()) {
      lines.push(`system instruction（手动输入）：\n${manualSystemInstruction.trim().slice(0, 1500)}`);
    }
    if (systemMode === "file" && systemFileName) {
      lines.push(`system instruction 文件：${systemFileName}`);
      if (systemFileContent.trim()) {
        lines.push(`system instruction 文件内容：\n${systemFileContent.trim().slice(0, 1500)}`);
      }
    }

    lines.push("请给出执行结果与下一步建议。");
    return lines.join("\n");
  }

  async function onSend() {
    if (history.length >= TURN_LIMIT) {
      return;
    }
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
        body: JSON.stringify({ text: composePayloadText().slice(0, 12000) }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          const j = (await res.json().catch(() => null)) as { detail?: string } | null;
          throw new Error(j?.detail || `HTTP ${res.status}`);
        }
        throw new Error(`HTTP ${res.status}`);
      }
      if (!res.body) {
        throw new Error("响应无正文（后端可能未返回流）");
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
          if ("session_id" in msg && "intent" in msg) {
            setActiveAgent(agentName(msg.intent?.task_type));
            continue;
          }
          if ("type" in msg && msg.type === "delta") {
            setReply((prev) => prev + msg.content);
            continue;
          }
          if ("type" in msg && msg.type === "done") {
            continue;
          }
        }
      }
      // 简单刷新一次历史记录（不追求强一致，够演示即可）
      try {
        const res = await fetch("/api/chat/history", {
          method: "GET",
          headers: {
            "x-session-id": sessionId,
          },
        });
        if (res.ok) {
          const data = (await res.json()) as { turns?: ChatTurn[] };
          const turns = data.turns || [];
          setHistory(turns);
          setActiveTurnIdx(turns.length > 0 ? turns.length - 1 : -1);
        }
      } catch {
        // ignore
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

  async function onExport() {
    if (!sessionId || exporting) return;
    setExporting(true);
    setExportMessage("");
    setError("");
    try {
      const res = await fetch("/api/chat/export", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-session-id": sessionId,
        },
        body: JSON.stringify({}),
      });
      const data = (await res.json()) as { file_path?: string; detail?: string };
      if (!res.ok) {
        throw new Error(data?.detail || `导出失败: HTTP ${res.status}`);
      }
      if (data.file_path) {
        setExportMessage(`已导出到 ${data.file_path}`);
      } else {
        setExportMessage("导出成功。");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "导出失败";
      setError(msg);
    } finally {
      setExporting(false);
    }
  }

  return (
    <main className="min-h-screen flex items-start justify-center bg-zinc-50 dark:bg-black px-4 pt-[6vh] pb-6">
      <div className="w-[min(94vw,1360px)] min-h-[70vh] grid grid-cols-1 lg:grid-cols-[1.618fr,1fr] gap-4">
        <section className="bg-white dark:bg-black rounded-2xl border border-zinc-200 dark:border-zinc-800 p-6 shadow-sm flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-lg font-semibold">Axiodrasil 演示（流式输出 + 路由分区）</div>
              <div className="text-sm text-zinc-500 dark:text-zinc-400">
                当前路由：<b>{activeAgent || "—"}</b>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="px-3 py-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => {
                  const id = crypto.randomUUID();
                  try {
                    window.localStorage.setItem("x-session-id", id);
                  } catch {
                    /* 隐私模式等无法写 localStorage 时仍允许新会话 */
                  }
                  setSessionId(id);
                  setText("");
                  setReply("");
                  setHistory([]);
                  setActiveTurnIdx(-1);
                  setError("");
                  setExportMessage("");
                }}
              >
                新建对话
              </button>
              <button
                type="button"
                className="px-3 py-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={onExport}
                disabled={exporting || !sessionId}
              >
                {exporting ? "导出中..." : "导出会话"}
              </button>
            </div>
          </div>

          {history.length >= TURN_LIMIT ? (
            <div className="mb-2 text-xs text-amber-700 dark:text-amber-400">
              本对话已达到 {TURN_LIMIT} 轮上限，请点击「新建对话」开始新的会话。
            </div>
          ) : null}

          {stackOk === false ? (
            <div className="mb-3 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-3 py-2 text-sm text-red-800 dark:text-red-200">
              <div className="font-medium">后端链路异常（Next → FastAPI）</div>
              <div className="mt-1 text-xs opacity-90">{stackHint}</div>
              <div className="mt-2 text-xs text-red-700 dark:text-red-300">
                建议：以管理员打开 CMD/PowerShell，对仍占用 6379 的进程执行{" "}
                <code className="rounded bg-red-100 dark:bg-red-900/50 px-1">taskkill /F /PID {"<PID>"}</code>，或在{" "}
                <code className="rounded bg-red-100 dark:bg-red-900/50 px-1">services.msc</code>{" "}
                中停止 Redis 服务；然后{" "}
                <code className="rounded bg-red-100 dark:bg-red-900/50 px-1">
                  .\scripts\dev_stack.ps1 -Action restart -All -ForceKillPort
                </code>
                。修改过后端 Python 后需重启 backend。
              </div>
            </div>
          ) : null}
          {stackOk === true && stackHint ? (
            <div className="mb-3 rounded-lg border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
              {stackHint}
            </div>
          ) : null}

          <div className="mb-3 flex gap-2">
            <button
              type="button"
              className={`px-3 py-1.5 rounded-lg text-sm border disabled:opacity-50 disabled:cursor-not-allowed ${
                mode === "chat"
                  ? "bg-black text-white border-black dark:bg-white dark:text-black dark:border-white"
                  : "bg-transparent border-zinc-300 dark:border-zinc-700"
              }`}
              onClick={() => setMode("chat")}
              disabled={loading}
            >
              聊天模式
            </button>
            <button
              type="button"
              className={`px-3 py-1.5 rounded-lg text-sm border disabled:opacity-50 disabled:cursor-not-allowed ${
                mode === "clean"
                  ? "bg-black text-white border-black dark:bg-white dark:text-black dark:border-white"
                  : "bg-transparent border-zinc-300 dark:border-zinc-700"
              }`}
              onClick={() => setMode("clean")}
              disabled={loading}
            >
              清洗模式
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
                type="button"
                className="px-4 py-2 rounded-lg bg-black dark:bg-white text-white dark:text-black text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={onSend}
                disabled={disableSend}
                title={
                  !sessionId
                    ? "正在初始化会话…"
                    : history.length >= TURN_LIMIT
                      ? "已达轮次上限，请新建对话"
                      : mode === "chat" && !text.trim()
                        ? "请先输入内容"
                        : undefined
                }
              >
                发送
              </button>
            ) : (
              <button
                type="button"
                className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm"
                onClick={onStop}
              >
                停止
              </button>
            )}
          </div>

          {mode === "clean" ? (
            <div className="mt-3 grid grid-cols-1 xl:grid-cols-2 gap-3">
              <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg p-3">
                <div className="text-sm font-medium mb-2">输入文件选择</div>
                <div className="text-xs text-zinc-500 mb-2">默认目录（input）文件下拉 + 自定义文件入口</div>
                <label className="text-xs text-zinc-500">默认目录</label>
                <div className="flex gap-2 mt-1 mb-2">
                  <input
                    className="flex-1 border border-zinc-200 dark:border-zinc-800 rounded-lg px-2 py-1.5 bg-transparent text-sm"
                    value={inputDir}
                    onChange={(e) => setInputDir(e.target.value)}
                    disabled={loading}
                  />
                  <button
                    type="button"
                    className="px-2 py-1.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => void loadDefaultFiles(inputDir)}
                    disabled={loading}
                  >
                    刷新
                  </button>
                </div>
                <select
                  className="w-full border border-zinc-200 dark:border-zinc-800 rounded-lg px-2 py-1.5 bg-transparent text-sm mb-2"
                  value={selectedDefaultFile}
                  onChange={(e) => setSelectedDefaultFile(e.target.value)}
                  disabled={loading || defaultFiles.length === 0}
                >
                  {defaultFiles.length === 0 ? (
                    <option value="">暂无可选文件</option>
                  ) : (
                    defaultFiles.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))
                  )}
                </select>
                <label className="text-xs text-zinc-500">自定义文件（本地）</label>
                <input
                  className="mt-1 block w-full text-sm"
                  type="file"
                  disabled={loading}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setCustomFileName(file.name);
                    const content = await file.text();
                    setCustomFileContent(content);
                  }}
                />
              </div>

              <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg p-3">
                <div className="text-sm font-medium mb-2">System Instruction 注入</div>
                <div className="text-xs text-zinc-500 mb-2">二选一，避免手写与文件提示冲突</div>
                <div className="flex gap-3 mb-2 text-sm">
                  <label className="flex items-center gap-1">
                    <input
                      type="radio"
                      checked={systemMode === "manual"}
                      onChange={() => setSystemMode("manual")}
                      disabled={loading}
                    />
                    手动输入
                  </label>
                  <label className="flex items-center gap-1">
                    <input
                      type="radio"
                      checked={systemMode === "file"}
                      onChange={() => setSystemMode("file")}
                      disabled={loading}
                    />
                    文件挂载
                  </label>
                </div>
                {systemMode === "manual" ? (
                  <textarea
                    className="w-full border border-zinc-200 dark:border-zinc-800 rounded-lg px-2 py-2 bg-transparent text-sm min-h-[100px]"
                    value={manualSystemInstruction}
                    onChange={(e) => setManualSystemInstruction(e.target.value)}
                    placeholder="输入 system instruction（例如：清洗规则、格式要求）"
                    disabled={loading}
                  />
                ) : (
                  <div>
                    <input
                      className="block w-full text-sm mb-2"
                      type="file"
                      disabled={loading}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        setSystemFileName(file.name);
                        const content = await file.text();
                        setSystemFileContent(content);
                      }}
                    />
                    <div className="text-xs text-zinc-500 truncate">
                      {systemFileName ? `已加载：${systemFileName}` : "尚未加载提示词文件"}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {error ? <div className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</div> : null}
          {exportMessage && !error ? (
            <div className="mt-2 text-xs text-emerald-700 dark:text-emerald-400">{exportMessage}</div>
          ) : null}

          <div className="mt-4">
            <div className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">模型输出</div>
            <pre className="whitespace-pre-wrap bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-lg p-3 text-sm min-h-[120px]">
              {reply || (loading ? "正在生成..." : "等待输入")}
            </pre>
          </div>

          <div className="mt-6 flex-1 min-h-[32vh]">
            <div className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">对话记录（最近）</div>
            {history.length === 0 ? (
              <div className="text-xs text-zinc-400">暂无历史记录。</div>
            ) : (
              <div className="space-y-4 max-h-[40vh] overflow-y-auto overflow-x-hidden pr-1">
                {history.map((turn, idx) => (
                  <div key={idx} id={`turn-${idx}`} className="space-y-1 scroll-mt-16">
                    <div className="flex justify-end">
                      <div className="max-w-[90%] bg-blue-500 text-white text-sm rounded-2xl px-4 py-2.5 whitespace-pre-wrap break-words">
                        {turn.user || "（空用户输入）"}
                      </div>
                    </div>
                    <div className="flex justify-start">
                      <div className="max-w-[90%] bg-zinc-100 dark:bg-zinc-900 text-sm rounded-2xl px-4 py-2.5 whitespace-pre-wrap break-words">
                        {turn.assistant || "（空回复）"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <aside className="bg-white dark:bg-black rounded-2xl border border-zinc-200 dark:border-zinc-800 p-4 shadow-sm h-fit sticky top-6">
          <div className="text-sm font-medium mb-1">会话导航</div>
          <div className="text-xs text-zinc-500 mb-3">轮次：{history.length} / {TURN_LIMIT}</div>
          <button
            type="button"
            className="w-full mb-3 px-3 py-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-sm"
            onClick={() => {
              try {
                window.localStorage.removeItem("x-session-id");
              } catch {
                /* ignore */
              }
              window.location.reload();
            }}
          >
            重置 session
          </button>
          <div className="text-xs text-zinc-500 mb-2">Prompt 定位</div>
          {history.length === 0 ? (
            <div className="text-xs text-zinc-400">暂无可导航的 prompt。</div>
          ) : (
            <div className="space-y-1 max-h-[56vh] overflow-y-auto pr-1 text-xs">
              {history.map((turn, idx) => (
                <button
                  key={idx}
                  type="button"
                  className={`w-full text-left px-2 py-1 rounded-md border transition-colors ${
                    activeTurnIdx === idx
                      ? "bg-blue-50 dark:bg-zinc-800 border-blue-200 dark:border-zinc-600"
                      : "border-transparent hover:bg-zinc-100 dark:hover:bg-zinc-900 hover:border-zinc-200 dark:hover:border-zinc-700"
                  }`}
                  onClick={() => {
                    setActiveTurnIdx(idx);
                    const el = document.getElementById(`turn-${idx}`);
                    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                >
                  <div className="font-medium text-zinc-700 dark:text-zinc-200 truncate">{turn.user || "（空用户输入）"}</div>
                  <div className="text-zinc-400 dark:text-zinc-500 truncate">{turn.assistant || "（空回复）"}</div>
                </button>
              ))}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}
