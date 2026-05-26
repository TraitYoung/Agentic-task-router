import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StreamingStatusBar } from "../StreamingStatusBar";

describe("StreamingStatusBar", () => {
  it("shows label and elapsed seconds", () => {
    render(<StreamingStatusBar label="架构设计" elapsed={12} />);
    expect(screen.getByText(/架构设计/)).toBeInTheDocument();
    expect(screen.getByText(/12s/)).toBeInTheDocument();
  });

  it("shows long wait hint after 30s", () => {
    render(<StreamingStatusBar label="生成中" statusText="> 模型思考中" elapsed={35} />);
    expect(screen.getByText(/模型单步约 1~3 分钟/)).toBeInTheDocument();
  });
});
