import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/lib/backend";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const sessionId = req.headers.get("x-session-id") || undefined;

  if (!sessionId) {
    return NextResponse.json({ detail: "missing x-session-id" }, { status: 400 });
  }

  const backendUrl = `${getBackendBaseUrl()}/api/v1/chat/history?limit=50`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "x-session-id": sessionId,
  };

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(30_000),
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { detail: `无法连接 FastAPI（${backendUrl}）：${msg}` },
      { status: 503 }
    );
  }

  const text = await backendRes.text().catch(() => "");
  if (!backendRes.ok) {
    return NextResponse.json(
      { detail: "backend history failed", status: backendRes.status, text },
      { status: 500 }
    );
  }

  try {
    const data = JSON.parse(text);
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ detail: "invalid json from backend", text }, { status: 500 });
  }
}

