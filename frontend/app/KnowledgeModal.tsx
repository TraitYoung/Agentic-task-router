"use client";

import { useState } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function KnowledgeModal({ open, onClose }: Props) {
  const [content, setContent] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  if (!open) return null;

  async function handleUpload() {
    if (!content.trim() || sending) return;
    setSending(true);
    setDone(false);
    try {
      const res = await fetch("/api/knowledge/upload", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (res.ok) {
        setContent("");
        setDone(true);
        setTimeout(() => setDone(false), 2000);
      }
    } catch {
      // ignore
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-lg rounded-2xl border border-[color:var(--line)] bg-white p-6 shadow-2xl">
        <h3 className="mb-4 text-base font-semibold text-zinc-800">上传知识文档</h3>
        <p className="mb-3 text-xs text-zinc-500">
          粘贴 Markdown 或纯文本文档内容，将存入知识库供 RAG 检索增强。
        </p>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={10}
          maxLength={50000}
          placeholder="粘贴技术文档、API 说明、需求文档等内容..."
          className="w-full resize-none rounded-xl border border-[color:var(--line)] bg-zinc-50 px-4 py-3 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:border-[rgba(201,111,59,0.45)] transition-colors"
        />
        <div className="mt-1 mb-4 text-right text-[11px] text-zinc-400">
          {content.length}/50k
        </div>
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-[color:var(--line)] px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-50 transition-colors"
          >
            关闭
          </button>
          {done && (
            <span className="text-xs text-emerald-600">已上传，下次对话时将自动检索。</span>
          )}
          <button
            type="button"
            onClick={handleUpload}
            disabled={!content.trim() || sending}
            className="rounded-xl bg-[linear-gradient(135deg,#d9925a_0%,#8f3d1d_100%)] px-5 py-2 text-sm text-white shadow-[0_8px_20px_rgba(143,61,29,0.22)] transition-all hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-40"
          >
            {sending ? "上传中..." : "上传"}
          </button>
        </div>
      </div>
    </div>
  );
}
