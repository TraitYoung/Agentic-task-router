"use client";

import { useState } from "react";
import type { StagePartial } from "./types";
import { partialStepTitle } from "./pipelineSteps";

type Props = {
  partial: StagePartial;
  isActive: boolean;
  defaultCollapsed?: boolean;
  children: React.ReactNode;
};

export function StagePartialPanel({
  partial,
  isActive,
  defaultCollapsed = true,
  children,
}: Props) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed && !isActive);
  const title = partialStepTitle(partial.step);

  return (
    <div
      className={`mt-3 border-t border-zinc-200/80 pt-3 first:mt-0 first:border-t-0 first:pt-0 ${
        isActive ? "rounded-lg bg-white/50 -mx-1 px-1" : ""
      }`}
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className="mb-2 flex w-full items-center gap-2 text-left text-[12px] font-medium text-zinc-700 hover:text-zinc-900"
      >
        <span className="text-zinc-400">{collapsed ? "▸" : "▾"}</span>
        <span>{title}</span>
        {isActive ? (
          <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-normal text-sky-800">
            进行中
          </span>
        ) : (
          <span className="text-[10px] font-normal text-emerald-700">已完成</span>
        )}
      </button>
      {!collapsed ? children : null}
    </div>
  );
}
