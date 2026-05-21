import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AssistantBubble, UserBubble } from "../Bubble";
import type { Message } from "../types";

const msg: Message = {
  id: "a1",
  role: "assistant",
  content: "Hello, this is a test reply.",
  ts: "2026-05-19T00:00:00Z",
};

describe("AssistantBubble", () => {
  it("renders message content when not streaming", () => {
    render(<AssistantBubble msg={msg} isStreaming={false} elapsed={0} />);
    expect(screen.getByText("Hello, this is a test reply.")).toBeInTheDocument();
  });

  it("renders streaming indicator when streaming with no content", () => {
    const emptyMsg = { ...msg, content: "" };
    render(
      <AssistantBubble msg={emptyMsg} isStreaming={true} elapsed={1} stageLabel="Discovery" />
    );
    expect(screen.getByText(/Discovery/)).toBeInTheDocument();
  });

  it("shows elapsed time when streaming > 2s", () => {
    const emptyMsg = { ...msg, content: "" };
    render(
      <AssistantBubble msg={emptyMsg} isStreaming={true} elapsed={10} />
    );
    expect(screen.getByText(/10s/)).toBeInTheDocument();
  });

  it("shows thinking hint when streaming > 30s", () => {
    const emptyMsg = { ...msg, content: "" };
    render(
      <AssistantBubble msg={emptyMsg} isStreaming={true} elapsed={35} />
    );
    expect(screen.getByText(/思考模式耗时较长/)).toBeInTheDocument();
  });

  it("renders artifact action buttons when artifact exists and not streaming", () => {
    const artifactMsg: Message = {
      ...msg,
      content: "## Implementation Prompt\nSome prompt here\n",
      artifactMd: "## Implementation Prompt\nSome prompt here\n## Test Prompt\nTest stuff\n",
      artifactPath: "output/chats/test_spec.md",
    };
    render(<AssistantBubble msg={artifactMsg} isStreaming={false} elapsed={0} />);
    expect(screen.getByText("复制实现 Prompt")).toBeInTheDocument();
    expect(screen.getByText("复制全文")).toBeInTheDocument();
  });

  it("shows review action buttons in review mode", () => {
    const reviewMsg: Message = {
      ...msg,
      content: "## Review Results\nSome review\n## Improvement Prompt\nFix this\n",
      artifactMd: "## Review Results\nSome review\n## Improvement Prompt\nFix this\n",
    };
    render(
      <AssistantBubble msg={reviewMsg} isStreaming={false} elapsed={0} mode="review" />
    );
    expect(screen.getByText("复制改进 Prompt")).toBeInTheDocument();
  });

  it("renders trace panel when trace steps exist", () => {
    const traceMsg: Message = {
      ...msg,
      traceId: "trace-123",
      traceSteps: [
        {
          index: 0,
          node: "discovery",
          ts: "2026-05-19T00:00:00Z",
          duration_ms: 1000,
          keys_written: ["goal"],
          summary: { goal: "test" },
        },
      ],
    };
    render(<AssistantBubble msg={traceMsg} isStreaming={false} elapsed={0} />);
    expect(screen.getByText(/链路追踪/)).toBeInTheDocument();
  });
});

describe("UserBubble", () => {
  it("renders user message text", () => {
    const userMsg: Message = { ...msg, role: "user", content: "Hello from user" };
    render(<UserBubble msg={userMsg} />);
    expect(screen.getByText("Hello from user")).toBeInTheDocument();
  });
});
