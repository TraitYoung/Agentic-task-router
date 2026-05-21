import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PipelineProgress } from "../PipelineProgress";

describe("PipelineProgress", () => {
  it("returns null when visible=false", () => {
    const { container } = render(<PipelineProgress activeStep={null} visible={false} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders pipeline step labels", () => {
    render(<PipelineProgress activeStep={null} visible={true} />);
    expect(screen.getByText("识别画像")).toBeInTheDocument();
    expect(screen.getByText("需求分析")).toBeInTheDocument();
    expect(screen.getByText("架构设计")).toBeInTheDocument();
    expect(screen.getByText("实现草案")).toBeInTheDocument();
    expect(screen.getByText("测试方案")).toBeInTheDocument();
    expect(screen.getByText("测试代码")).toBeInTheDocument();
    expect(screen.getByText("汇总发布")).toBeInTheDocument();
  });
});
