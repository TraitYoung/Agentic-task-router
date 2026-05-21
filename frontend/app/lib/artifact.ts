/** 从 artifact markdown 提取可复制段落（与后端 schemas/artifact_pack 标题一致） */

const IMPL_HEADING = "## Cursor / Copilot — Implementation Prompt";
const TEST_HEADING = "## Cursor / Copilot — Test Prompt";
const GENERATED_TESTS_HEADING = "## Generated Test Files";
const REVIEW_HEADING = "## Cursor / Copilot — Improvement Prompt";

export function extractSection(md: string, heading: string): string {
  const lines = md.split("\n");
  const start = lines.findIndex((l) => l.trim() === heading);
  if (start < 0) return "";
  const body: string[] = [];
  for (let i = start + 1; i < lines.length; i++) {
    if (lines[i].startsWith("## ")) break;
    body.push(lines[i]);
  }
  return body.join("\n").trim();
}

export function extractImplementationPrompt(artifactMd: string): string {
  return extractSection(artifactMd, IMPL_HEADING);
}

export function extractTestPrompt(artifactMd: string): string {
  return extractSection(artifactMd, TEST_HEADING);
}

export function extractGeneratedTestFiles(artifactMd: string): string {
  return extractSection(artifactMd, GENERATED_TESTS_HEADING);
}

export function extractReviewPrompt(artifactMd: string): string {
  return extractSection(artifactMd, REVIEW_HEADING);
}

export function downloadMarkdown(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "SPEC.md";
  a.click();
  URL.revokeObjectURL(url);
}
