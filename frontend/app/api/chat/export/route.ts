import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const sessionId = req.headers.get("x-session-id") || undefined;

  if (!sessionId) {
    return NextResponse.json({ detail: "missing x-session-id" }, { status: 400 });
  }

  const backendUrl = "http://127.0.0.1:8000/api/v1/chat/export";

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "x-session-id": sessionId,
  };

  const backendRes = await fetch(backendUrl + "?limit=20", {
    method: "POST",
    headers,
    body: JSON.stringify({}),
  });

  const text = await backendRes.text().catch(() => "");
  if (!backendRes.ok) {
    return NextResponse.json(
      { detail: "backend export failed", status: backendRes.status, text },
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

