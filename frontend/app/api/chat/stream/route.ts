import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  backendConnectionError,
  buildBackendUrl,
  forwardedBackendHeaders,
} from "@/lib/backend";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(req: NextRequest) {
  let payload: { text?: string; mode?: string } = {};
  try {
    payload = await req.json();
  } catch {
    return NextResponse.json({ detail: "invalid json body" }, { status: 400 });
  }

  if (!payload?.text || typeof payload.text !== "string") {
    return NextResponse.json({ detail: "missing field: text" }, { status: 400 });
  }

  const backendBody: Record<string, string> = { text: payload.text };
  if (payload.mode) backendBody.mode = payload.mode;

  const headers = forwardedBackendHeaders(req, { includeTrace: true });
  if (headers instanceof NextResponse) return headers;

  const backendUrl = buildBackendUrl("/api/v1/chat/stream");

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify(backendBody),
      signal: AbortSignal.timeout(600_000),
    });
  } catch (error) {
    return backendConnectionError(backendUrl, error);
  }

  if (!backendRes.ok || !backendRes.body) {
    const text = await backendRes.text().catch(() => "");
    return NextResponse.json(
      { detail: "backend request failed", status: backendRes.status, text },
      { status: 500 },
    );
  }

  const outHeaders: Record<string, string> = {
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    Connection: "keep-alive",
  };
  const backendTrace = backendRes.headers.get("x-trace-id");
  if (backendTrace) outHeaders["x-trace-id"] = backendTrace;

  return new Response(backendRes.body, {
    status: backendRes.status,
    headers: outHeaders,
  });
}
