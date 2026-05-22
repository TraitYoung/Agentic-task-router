import { NextRequest } from "next/server";
import { buildBackendUrl } from "@/../lib/backend";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body || typeof body.content !== "string" || !body.content.trim()) {
    return Response.json({ detail: "missing field: content" }, { status: 400 });
  }

  const backendUrl = buildBackendUrl("/api/v1/knowledge/upload");
  try {
    const backendRes = await fetch(backendUrl, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content: body.content, title: body.title || "" }),
    });
    const data = await backendRes.json().catch(() => null);
    return Response.json(data, { status: backendRes.status });
  } catch (error) {
    return Response.json(
      { detail: `backend unreachable: ${error instanceof Error ? error.message : error}` },
      { status: 503 },
    );
  }
}
