import test from "node:test";
import assert from "node:assert/strict";

import { canSendMessage, shouldSendOnEnter } from "./chatComposer.ts";

test("canSendMessage requires non-empty text, session, and idle state", () => {
  assert.equal(canSendMessage("hello", "session-1", false), true);
  assert.equal(canSendMessage("   ", "session-1", false), false);
  assert.equal(canSendMessage("hello", "", false), false);
  assert.equal(canSendMessage("hello", "session-1", true), false);
});

test("shouldSendOnEnter sends only for plain Enter", () => {
  assert.equal(
    shouldSendOnEnter({
      key: "Enter",
      shiftKey: false,
      isComposing: false,
    }),
    true
  );
  assert.equal(
    shouldSendOnEnter({
      key: "Enter",
      shiftKey: true,
      isComposing: false,
    }),
    false
  );
});

test("shouldSendOnEnter ignores IME confirmation Enter", () => {
  assert.equal(
    shouldSendOnEnter({
      key: "Enter",
      shiftKey: false,
      isComposing: true,
    }),
    false
  );

  assert.equal(
    shouldSendOnEnter({
      key: "Enter",
      shiftKey: false,
      isComposing: false,
      keyCode: 229,
    }),
    false
  );
});
