import { promises as fs } from "fs";
import path from "path";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

function resolveDirInRepo(dirParam: string | null): string {
  const repoRoot = path.resolve(process.cwd(), "..");
  const rel = (dirParam || "input").trim();
  const target = path.resolve(repoRoot, rel);
  if (!target.startsWith(repoRoot)) {
    throw new Error("invalid path");
  }
  return target;
}

export async function GET(req: NextRequest) {
  try {
    const dir = resolveDirInRepo(req.nextUrl.searchParams.get("dir"));
    await fs.mkdir(dir, { recursive: true });

    const fileParam = req.nextUrl.searchParams.get("file");
    if (fileParam) {
      const filePath = path.resolve(dir, fileParam);
      if (!filePath.startsWith(dir)) {
        return NextResponse.json({ detail: "invalid file path" }, { status: 400 });
      }
      const content = await fs.readFile(filePath, "utf-8");
      return NextResponse.json({ dir, file: fileParam, content });
    }

    const entries = await fs.readdir(dir, { withFileTypes: true });
    const files = entries
      .filter((e) => e.isFile())
      .map((e) => e.name)
      .sort((a, b) => a.localeCompare(b));
    return NextResponse.json({ dir, files });
  } catch (e) {
    const detail = e instanceof Error ? e.message : "failed to list files";
    return NextResponse.json({ detail }, { status: 400 });
  }
}

