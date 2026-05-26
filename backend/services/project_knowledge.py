"""Index project README, docs, API routes, and code entrypoints into RAG memory."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from repo_paths import REPO_ROOT

_INDEXED = False
_MAX_CHARS = 6000


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _chunks(text: str, size: int = _MAX_CHARS) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    return [clean[i : i + size] for i in range(0, len(clean), size)]


def _save_file(store: Any, path: Path, *, source_group: str) -> int:
    content = _read_text(path)
    count = 0
    rel = path.relative_to(REPO_ROOT).as_posix()
    for idx, chunk in enumerate(_chunks(content), start=1):
        suffix = f"#{idx}" if len(content) > _MAX_CHARS else ""
        store.save_knowledge(
            title=f"{rel}{suffix}",
            source=f"{source_group}:{rel}{suffix}",
            content=chunk,
        )
        count += 1
    return count


def ensure_project_knowledge_indexed(store: Any, *, root: Path = REPO_ROOT) -> int:
    """Idempotently index codebase, README, docs, and API files for retrieval."""
    global _INDEXED
    if _INDEXED:
        return 0

    paths: list[tuple[Path, str]] = []
    for name in ("README.md", "backend/main.py"):
        path = root / name
        if path.exists():
            paths.append((path, "project"))

    docs_dir = root / "docs"
    if docs_dir.exists():
        for path in docs_dir.glob("*.md"):
            paths.append((path, "docs"))

    api_dir = root / "frontend" / "app" / "api"
    if api_dir.exists():
        for path in api_dir.rglob("route.ts"):
            paths.append((path, "frontend-api"))

    code_roots = [
        root / "backend" / "agents" / "dev_pipeline",
        root / "backend" / "services",
        root / "backend" / "schemas",
        root / "backend" / "config",
    ]
    for code_root in code_roots:
        if code_root.exists():
            for path in code_root.glob("*.py"):
                paths.append((path, "codebase"))

    seen: set[str] = set()
    count = 0
    for path, source_group in paths:
        key = hashlib.sha1(str(path).encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        count += _save_file(store, path, source_group=source_group)

    _INDEXED = True
    return count
