"""将 test_code 流式 Markdown 解析为 DevTestBundle。"""

from __future__ import annotations

import re

from config.context_budget import clip_text
from config.structured_invoke import strip_thinking
from schemas.workflows import DevTestBundle, DevTestFile

_FILE_HEADING_RE = re.compile(r"^##\s*file:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"```(?:[\w+-]+)?\s*\n([\s\S]*?)```", re.MULTILINE)

_FALLBACK_PATH = "tests/smoke.test.ts"


def parse_test_bundle(text: str) -> DevTestBundle:
    raw = strip_thinking((text or "").strip())
    if not raw:
        return _fallback_bundle("")

    files: list[DevTestFile] = []
    chunks = re.split(r"(?=^##\s*file:\s*.+\s*$)", raw, flags=re.IGNORECASE | re.MULTILINE)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        heading = _FILE_HEADING_RE.match(chunk)
        if heading:
            path = heading.group(1).strip().strip("`").strip()
            body = chunk[heading.end() :].strip()
        elif files:
            continue
        else:
            path = _infer_path(raw)
            body = chunk

        code_blocks = _CODE_FENCE_RE.findall(body)
        code = code_blocks[0].strip() if code_blocks else body.strip()
        if not code and not path:
            continue
        files.append(DevTestFile(path=path or _FALLBACK_PATH, code=code))

    if not files:
        return _fallback_bundle(raw)

    return DevTestBundle.model_validate({"files": files[:2]})


def _infer_path(text: str) -> str:
    lower = text.lower()
    if "pytest" in lower or "def test_" in lower:
        return "tests/test_smoke.py"
    if "vitest" in lower or "jest" in lower:
        return "src/__tests__/smoke.test.ts"
    return _FALLBACK_PATH


def _fallback_bundle(raw: str) -> DevTestBundle:
    snippet = clip_text(raw, 3000) if raw else "// TODO: add smoke test"
    path = _infer_path(raw)
    return DevTestBundle(files=[DevTestFile(path=path, code=snippet)])
