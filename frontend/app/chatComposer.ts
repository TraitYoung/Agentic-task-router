export type EnterIntent = {
  isComposing: boolean;
  key: string;
  keyCode?: number;
  shiftKey: boolean;
};

export function canSendMessage(text: string, sessionId: string, loading: boolean): boolean {
  return Boolean(text.trim() && sessionId && !loading);
}

export function shouldSendOnEnter(intent: EnterIntent): boolean {
  return (
    intent.key === "Enter" &&
    !intent.shiftKey &&
    !intent.isComposing &&
    intent.keyCode !== 229
  );
}
