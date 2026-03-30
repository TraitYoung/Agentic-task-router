import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const sessionId = req.headers.get("x-session-id") || undefined;

  let payload: { text?: string } = {};
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "invalid json body" }, { status: 400 });
  }

  if (!payload?.text || typeof payload.text !== "string") {
    return NextResponse.json({ detail: "missing field: text" }, { status: 400 });
  }

  const backendUrl = "http://127.0.0.1:8000/api/v1/chat/stream";

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (sessionId) headers["x-session-id"] = sessionId;

  const backendRes = await fetch(backendUrl, {
    method: "POST",
    headers,
    body: JSON.stringify({ text: payload.text }),
  });

  if (!backendRes.ok || !backendRes.body) {
    const text = await backendRes.text().catch(() => "");
    return NextResponse.json(
      { detail: "backend request failed", status: backendRes.status, text },
      { status: 500 }
    );
  }

  // 直接透传 SSE 流：让浏览器接收 data: ...\n\n 事件
  return new Response(backendRes.body, {
    status: backendRes.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}

