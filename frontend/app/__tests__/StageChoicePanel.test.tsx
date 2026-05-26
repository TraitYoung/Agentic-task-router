/** StageChoicePanel 组件测试 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StageChoicePanel } from "../StageChoicePanel";

const sampleChoice = {
  checkpointId: "cp-1",
  step: "discovery",
  options: [
    { id: "A" as const, label: "MVP", description: "极简" },
    { id: "B" as const, label: "平衡", description: "标准" },
    { id: "C" as const, label: "完整", description: "全量" },
    { id: "D" as const, label: "综合全部", description: "ABC" },
  ],
};

describe("StageChoicePanel", () => {
  it("renders A/B/C/D options", () => {
    render(<StageChoicePanel choice={sampleChoice} onSelect={vi.fn()} />);
    expect(screen.getByText(/MVP/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /D · 综合全部/ })).toBeInTheDocument();
  });

  it("calls onSelect with choice id and checkpoint", () => {
    const onSelect = vi.fn();
    render(<StageChoicePanel choice={sampleChoice} onSelect={onSelect} />);
    fireEvent.click(screen.getByText(/平衡/));
    expect(onSelect).toHaveBeenCalledWith("B", "cp-1");
  });

  it("collapses when selected and not loading", () => {
    render(
      <StageChoicePanel
        choice={{ ...sampleChoice, selected: "A" }}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText(/已选/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /MVP/ })).not.toBeInTheDocument();
  });

  it("shows loading spinner when generating after selection", () => {
    render(
      <StageChoicePanel
        choice={{ ...sampleChoice, selected: "B" }}
        loading
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText(/正在生成/)).toBeInTheDocument();
  });

  it("shows retry button when retryable", () => {
    const onRetry = vi.fn();
    render(
      <StageChoicePanel
        choice={{ ...sampleChoice, selected: "B", retryable: true, lastChoice: "B" }}
        onSelect={vi.fn()}
        onRetry={onRetry}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /重试（B）/ }));
    expect(onRetry).toHaveBeenCalledWith("cp-1", "B");
  });
});
