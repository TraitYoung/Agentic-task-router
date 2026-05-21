import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TracePanel } from "../TracePanel";
import type { TraceStepRow } from "../types";

const steps: TraceStepRow[] = [
  {
    index: 0,
    node: "discovery",
    ts: "2026-05-19T00:00:00Z",
    duration_ms: 1500,
    keys_written: ["goal"],
    summary: { goal: "test", _metrics: { estimated_tokens: 500, memory_mb: 12 } },
  },
  {
    index: 1,
    node: "sprint_design",
    ts: "2026-05-19T00:00:02Z",
    duration_ms: 2000,
    keys_written: ["modules"],
    summary: { modules: [], _metrics: { estimated_tokens: 800, memory_mb: 15 } },
  },
];

describe("TracePanel", () => {
  it("returns null when steps is empty", () => {
    const { container } = render(<TracePanel steps={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders step count", () => {
    render(<TracePanel steps={steps} />);
    expect(screen.getByText("链路追踪 (2 步)")).toBeInTheDocument();
  });

  it("shows truncated traceId", () => {
    render(<TracePanel steps={steps} traceId="abcdefgh-1234" />);
    expect(screen.getByText("abcdefgh...")).toBeInTheDocument();
  });

  it("calculates total duration", () => {
    render(<TracePanel steps={steps} />);
    expect(screen.getByText("3500 ms")).toBeInTheDocument();
  });

  it("shows estimated tokens", () => {
    render(<TracePanel steps={steps} />);
    expect(screen.getByText("1300")).toBeInTheDocument();
  });
});
