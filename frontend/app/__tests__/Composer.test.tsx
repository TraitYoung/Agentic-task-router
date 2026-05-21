import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Composer } from "../Composer";

const noop = () => {};
const ref = { current: null };

function renderComposer(overrides: Partial<Parameters<typeof Composer>[0]> = {}) {
  return render(
    <Composer
      mode="spec"
      text=""
      loading={false}
      readyToSend={false}
      isComposing={false}
      stackOk={true}
      apiKey=""
      textareaRef={ref}
      onTextChange={noop}
      onApiKeyChange={noop}
      onSend={noop}
      onStop={noop}
      onKeyDown={noop}
      onCompositionStart={noop}
      onCompositionEnd={noop}
      {...overrides}
    />
  );
}

describe("Composer", () => {
  it("renders textarea with spec placeholder", () => {
    renderComposer();
    const ta = screen.getByPlaceholderText(/描述你的想法/);
    expect(ta).toBeInTheDocument();
  });

  it("renders review placeholder when mode is review", () => {
    renderComposer({ mode: "review" });
    const ta = screen.getByPlaceholderText(/粘贴待审查代码/);
    expect(ta).toBeInTheDocument();
  });

  it("shows send button when not loading", () => {
    renderComposer();
    expect(screen.getByLabelText("发送")).toBeInTheDocument();
  });

  it("shows stop button when loading", () => {
    renderComposer({ loading: true });
    expect(screen.getByLabelText("停止生成")).toBeInTheDocument();
  });

  it("disables textarea when loading", () => {
    renderComposer({ loading: true });
    expect(screen.getByPlaceholderText(/描述你的想法/)).toBeDisabled();
  });

  it("shows API key toggle button", () => {
    renderComposer();
    expect(screen.getByText("设置 Key")).toBeInTheDocument();
  });

  it("shows '已设置 Key' when apiKey is provided", () => {
    renderComposer({ apiKey: "sk-test" });
    expect(screen.getByText("已设置 Key")).toBeInTheDocument();
  });

  it("calls onSend when form submitted with readyToSend=true", async () => {
    const onSend = vi.fn();
    renderComposer({ readyToSend: true, text: "hello", onSend });
    await userEvent.click(screen.getByLabelText("发送"));
    expect(onSend).toHaveBeenCalledOnce();
  });

  it("shows character count when text has content", () => {
    renderComposer({ text: "hello" });
    expect(screen.getByText("5/12k")).toBeInTheDocument();
  });
});
