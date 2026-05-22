import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  backendConnectionError,
  backendJsonResponse,
  buildBackendUrl,
  forwardedBackendHeaders,
} from "@/lib/backend";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const headers = forwardedBackendHeaders(req, { requireSession: true });
  if (headers instanceof NextResponse) return headers;

  const backendUrl = buildBackendUrl("/api/v1/chat/history?limit=50");

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl, {
      method: "GET",
      headers,
      signal: AbortSignal.timeout(30_000),
    });
  } catch (error) {
    return backendConnectionError(backendUrl, error);
  }

  return backendJsonResponse(backendRes, "backend history failed");
}
