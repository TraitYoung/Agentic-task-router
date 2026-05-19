import assert from "node:assert/strict";
import test from "node:test";
import { parseSseEvent } from "./lib.ts";

test("parseSseEvent reads single data line", () => {
  const evt = parseSseEvent('data: {"type":"status","text":"ok"}');
  assert.equal(evt?.type, "status");
  assert.equal(evt?.text, "ok");
});

test("parseSseEvent reads meta event", () => {
  const evt = parseSseEvent(
    'data: {"type":"meta","session_id":"s1","intent":{"task_type":"spec"},"trace":[]}'
  );
  assert.equal(evt?.type, "meta");
  assert.equal(evt?.session_id, "s1");
});
