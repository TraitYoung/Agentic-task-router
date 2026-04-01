import { NextResponse } from "next/server";
import { getBackendBaseUrl } from "@/lib/backend";

export const runtime = "nodejs";

export async function GET() {
  const base = getBackendBaseUrl();
  const url = `${base}/api/v1/health`;
  try {
    const r = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    const text = await r.text();
    if (!r.ok) {
      return NextResponse.json(
        {
          ok: false,
          backend: base,
          status: r.status,
          detail: text.slice(0, 500) || `HTTP ${r.status}`,
        },
        { status: 503 }
      );
    }
    let backendHealth: unknown = null;
    try {
      backendHealth = JSON.parse(text) as unknown;
    } catch {
      backendHealth = { raw: text };
    }
    return NextResponse.json({ ok: true, backend: base, backendHealth });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        ok: false,
        backend: base,
        detail: `无法连接后端 ${url}：${msg}`,
      },
      { status: 503 }
    );
  }
}
