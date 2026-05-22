import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

/** Base URL used by Next.js API routes to proxy requests to FastAPI. */
export function getBackendBaseUrl(): string {
  const u = process.env.BACKEND_URL?.trim();
  if (u) return u.replace(/\/$/, "");
  return "http://127.0.0.1:8000";
}

export function buildBackendUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${getBackendBaseUrl()}${normalized}`;
}

export function forwardedBackendHeaders(
  req: NextRequest,
  options: { requireSession?: boolean; includeTrace?: boolean } = {},
): Record<string, string> | NextResponse {
  const sessionId = req.headers.get("x-session-id") || undefined;
  if (options.requireSession && !sessionId) {
    return NextResponse.json({ detail: "missing x-session-id" }, { status: 400 });
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = req.headers.get("x-api-key") || undefined;
  const traceId = options.includeTrace ? req.headers.get("x-trace-id") || undefined : undefined;

  if (sessionId) headers["x-session-id"] = sessionId;
  if (apiKey) headers["x-api-key"] = apiKey;
  if (traceId) headers["x-trace-id"] = traceId;
  return headers;
}

export function backendConnectionError(url: string, error: unknown): NextResponse {
  const msg = error instanceof Error ? error.message : String(error);
  return NextResponse.json(
    { detail: `Unable to connect to FastAPI (${url}): ${msg}` },
    { status: 503 },
  );
}

export async function backendJsonResponse(
  backendRes: Response,
  failureDetail: string,
): Promise<NextResponse> {
  const text = await backendRes.text().catch(() => "");
  if (!backendRes.ok) {
    return NextResponse.json(
      { detail: failureDetail, status: backendRes.status, text },
      { status: 500 },
    );
  }

  try {
    return NextResponse.json(JSON.parse(text));
  } catch {
    return NextResponse.json({ detail: "invalid json from backend", text }, { status: 500 });
  }
}
