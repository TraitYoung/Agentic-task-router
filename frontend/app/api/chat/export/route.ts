import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  backendConnectionError,
  backendJsonResponse,
  buildBackendUrl,
  forwardedBackendHeaders,
} from "@/lib/backend";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const headers = forwardedBackendHeaders(req, { requireSession: true });
  if (headers instanceof NextResponse) return headers;

  const backendUrl = buildBackendUrl("/api/v1/chat/export?limit=20");

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({}),
      signal: AbortSignal.timeout(60_000),
    });
  } catch (error) {
    return backendConnectionError(backendUrl, error);
  }

  return backendJsonResponse(backendRes, "backend export failed");
}
