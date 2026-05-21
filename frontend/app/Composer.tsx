"use client";

import { useState, type RefObject, type KeyboardEvent, type FormEvent } from "react";
import { shouldSendOnEnter } from "./chatComposer";
import type { UiMode } from "./types";

interface Props {
  mode: UiMode;
  text: string;
  loading: boolean;
  readyToSend: boolean;
  isComposing: boolean;
  stackOk: boolean | null;
  apiKey: string;
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  onTextChange: (text: string) => void;
  onApiKeyChange: (key: string) => void;
  onSend: () => void;
  onStop: () => void;
  onKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void;
  onCompositionStart: () => void;
  onCompositionEnd: () => void;
}

export function Composer({
  mode,
  text,
  loading,
  readyToSend,
  isComposing,
  stackOk,
  apiKey,
  textareaRef,
  onTextChange,
  onApiKeyChange,
  onSend,
  onStop,
  onKeyDown,
  onCompositionStart,
  onCompositionEnd,
}: Props) {
  const [keyVisible, setKeyVisible] = useState(false);

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    onSend();
  }

  return (
    <footer className="sticky bottom-0 flex-none border-t border-[color:var(--line)] bg-[color:var(--surface)]/95 px-4 py-4 backdrop-blur-xl">
      <form className="mx-auto w-full max-w-4xl" onSubmit={handleSubmit}>
        <div className="rounded-[2rem] border border-white/70 bg-[color:var(--surface-strong)] px-4 py-4 shadow-[0_18px_50px_rgba(91,63,42,0.12)]">
          <div className="flex items-center justify-between gap-3 px-1 pb-3">
            <div className="text-xs text-zinc-500">
              {mode === "spec" ? "需求规格输入区" : "代码审查输入区"}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-zinc-400">
              <button
                type="button"
                onClick={() => setKeyVisible(!keyVisible)}
                className="hover:text-zinc-600 transition-colors"
                aria-label="API Key 设置"
              >
                {apiKey ? "已设置 Key" : "设置 Key"}
              </button>
              <span>{isComposing ? "输入法确认中..." : "Enter 发送"}</span>
              <span>{text.length > 0 ? `${text.length}/12k` : "最多 12k"}</span>
            </div>
          </div>

          {keyVisible && (
            <div className="px-1 pb-3">
              <input
                type="password"
                value={apiKey}
                onChange={(e) => onApiKeyChange(e.target.value)}
                placeholder="输入 API Key（x-api-key）"
                className="w-full rounded-xl border border-[color:var(--line)] bg-white px-3 py-2 text-xs text-zinc-700 placeholder-zinc-400 focus:outline-none focus:border-[rgba(201,111,59,0.45)] transition-colors"
                autoComplete="off"
              />
            </div>
          )}

          <div
            className={`flex items-end gap-3 rounded-[1.5rem] border border-[color:var(--line)] bg-white px-4 py-3 transition-colors focus-within:border-[rgba(201,111,59,0.45)] ${
              loading ? "animate-pulse border-zinc-300/80" : ""
            }`}
          >
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => onTextChange(e.target.value)}
              onKeyDown={onKeyDown}
              onCompositionStart={onCompositionStart}
              onCompositionEnd={onCompositionEnd}
              disabled={loading}
              rows={1}
              placeholder={
                mode === "spec"
                  ? "描述你的想法、范围、约束或期望交付物..."
                  : "粘贴待审查代码、模块说明或你想聚焦的问题..."
              }
              maxLength={12000}
              className="min-h-[56px] flex-1 resize-none bg-transparent py-1 text-sm leading-7 text-zinc-900 placeholder-zinc-400 focus:outline-none max-h-48"
              style={{ overflowY: "auto" }}
            />
            <div className="relative flex items-center gap-2 pb-1">
              {loading ? (
                <button
                  type="button"
                  onClick={onStop}
                  className="relative flex h-11 w-11 items-center justify-center rounded-2xl bg-zinc-900 text-white transition-colors hover:bg-zinc-700"
                  aria-label="停止生成"
                >
                  <span
                    className="pointer-events-none absolute inset-0 rounded-2xl border-2 border-transparent border-t-white/80 animate-spin"
                    aria-hidden
                  />
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 12 12"
                    fill="currentColor"
                    className="relative z-10"
                  >
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
  );
}
