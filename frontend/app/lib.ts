export function safeParseJson(line: string): unknown | null {
  try {
    return JSON.parse(line);
  } catch {
    return null;
  }
}

/** 从 SSE `data:` 行解析 JSON 事件；支持 `data: {...}` 与多行 data。 */
export function parseSseEvent(block: string): Record<string, unknown> | null {
  const lines = block.split("\n");
  const dataLines: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("data:")) {
      dataLines.push(trimmed.slice(5).trim());
    }
  }
  if (!dataLines.length) return null;
  const payload = dataLines.join("\n");
  const parsed = safeParseJson(payload);
  return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
}

export function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}
