import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WelcomeHero } from "../WelcomeHero";

describe("WelcomeHero", () => {
  it("renders spec heading in spec mode", () => {
    render(<WelcomeHero mode="spec" stackOk={true} onPromptClick={() => {}} />);
    expect(screen.getByText("把模糊需求整理成可执行规格")).toBeInTheDocument();
  });

  it("renders review heading in review mode", () => {
    render(<WelcomeHero mode="review" stackOk={true} onPromptClick={() => {}} />);
    expect(screen.getByText("把现有代码还原成清晰决策")).toBeInTheDocument();
  });

  it("shows spec prompts in spec mode", () => {
    render(<WelcomeHero mode="spec" stackOk={true} onPromptClick={() => {}} />);
    expect(screen.getByText("帮我拆解一个新功能的需求、范围和验收标准")).toBeInTheDocument();
  });

  it("shows review prompts in review mode", () => {
    render(<WelcomeHero mode="review" stackOk={true} onPromptClick={() => {}} />);
    expect(screen.getByText("帮我审查这段代码的结构问题和潜在风险")).toBeInTheDocument();
  });

  it("calls onPromptClick when a prompt button is clicked", async () => {
    const onPromptClick = vi.fn();
    render(<WelcomeHero mode="spec" stackOk={true} onPromptClick={onPromptClick} />);
    await userEvent.click(screen.getByText("帮我拆解一个新功能的需求、范围和验收标准"));
    expect(onPromptClick).toHaveBeenCalledOnce();
  });

  it("shows disconnected state when stackOk is false", () => {
    render(<WelcomeHero mode="spec" stackOk={false} onPromptClick={() => {}} />);
    expect(screen.getByText("后端未连接，当前无法发起请求。")).toBeInTheDocument();
  });
});
