"""SpecStore: SQLite FTS5 持久化检索 — 正向规格复用 + 逆向高频问题积累。

检索策略：
  - 主路径：FTS5 全文索引（BM25 相关性排序），覆盖 goal/user_stories/modules 字段
  - 降级路径：中文 LIKE 通配符模糊匹配（SQLite FTS5 内置 tokenizer 对中文分词有限）
  - 去重逻辑：review issues 按 (issue_text, type) 判定重复，重复则递增 frequency 计数

每插入一条 spec 或 issue 后，AFTER INSERT 触发器自动同步到 FTS5 虚拟表，
保证全文索引与原始表一致。

数据库文件：data/spec_store.db（由 .gitignore 忽略）
"""

from __future__ import annotations

import atexit
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from repo_paths import REPO_ROOT

logger = logging.getLogger("specforge.spec_store")

DB_PATH = REPO_ROOT / "data" / "spec_store.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _like_query(query: str) -> str:
    return query.strip().strip(' \t\r\n?？!！,，.。;；:："“”\'‘’`()（）[]【】{}<>《》')


class SpecStore:
    """封装 SQLite FTS5：存储和检索软件工程规格与审查问题。"""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                profile TEXT NOT NULL DEFAULT '',
                user_text TEXT NOT NULL,
                goal TEXT NOT NULL DEFAULT '',
                user_stories TEXT NOT NULL DEFAULT '',
                modules TEXT NOT NULL DEFAULT '',
                full_summary TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS specs_fts
                USING fts5(mode, profile, user_text, goal, user_stories, modules,
                           content='specs', content_rowid='id');

            CREATE TRIGGER IF NOT EXISTS specs_ai AFTER INSERT ON specs BEGIN
                INSERT INTO specs_fts(rowid, mode, profile, user_text, goal, user_stories, modules)
                VALUES (new.id, new.mode, new.profile, new.user_text, new.goal, new.user_stories, new.modules);
            END;

            CREATE TABLE IF NOT EXISTS review_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile TEXT NOT NULL DEFAULT '',
                issue_type TEXT NOT NULL,
                issue_text TEXT NOT NULL,
                suggestion TEXT NOT NULL DEFAULT '',
                frequency INTEGER NOT NULL DEFAULT 1,
                last_seen TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS review_issues_fts
                USING fts5(profile, issue_type, issue_text, suggestion,
                           content='review_issues', content_rowid='id');

            CREATE TRIGGER IF NOT EXISTS review_issues_ai AFTER INSERT ON review_issues BEGIN
                INSERT INTO review_issues_fts(rowid, profile, issue_type, issue_text, suggestion)
                VALUES (new.id, new.profile, new.issue_type, new.issue_text, new.suggestion);
            END;

            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
                USING fts5(title, content, content='knowledge', content_rowid='id');

            CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                INSERT INTO knowledge_fts(rowid, title, content)
                VALUES (new.id, new.title, new.content);
            END;
            """
        )
        self._conn.commit()
        self._stamp_alembic_if_needed()

    @staticmethod
    def _alembic_stamp_revision() -> str:
        """Return the revision that represents the current inline schema."""
        return "0001_initial_schema"

    def _stamp_alembic_if_needed(self) -> None:
        """Stamp the alembic_version table if this is a pre-Alembic database.

        Existing databases created by inline _migrate() won't have an
        alembic_version table.  This method creates one and stamps it
        with the initial revision so that future ``alembic upgrade head``
        commands know the schema is already up to date.
        """
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        )
        if cursor.fetchone() is not None:
            return  # Already stamped.

        rev = self._alembic_stamp_revision()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        self._conn.execute(
            "INSERT INTO alembic_version (version_num) VALUES (?)", (rev,)
        )
        self._conn.commit()
        logger.info("alembic stamped with revision %s (pre-existing database)", rev)

    # ── 正向规格存取 ──────────────────────────────────────

    def save_spec(
        self,
        *,
        mode: str,
        profile: str,
        user_text: str,
        goal: str,
        user_stories: list[str],
        modules: list[str],
        full_summary: str,
    ) -> int:
        """保存一条规格，返回 row id。"""
        cur = self._conn.execute(
            """INSERT INTO specs (mode, profile, user_text, goal, user_stories, modules, full_summary, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mode,
                profile,
                user_text,
                goal,
                json.dumps(user_stories, ensure_ascii=False),
                json.dumps(modules, ensure_ascii=False),
                full_summary,
                _now_iso(),
            ),
        )
        self._conn.commit()
        logger.info("spec saved: mode=%s profile=%s goal=%s", mode, profile, goal[:80])
        return cur.lastrowid

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def search_specs(self, query: str, mode: str = "", limit: int = 5) -> list[dict[str, Any]]:
        """FTS5 全文检索相似历史规格，中文回退 LIKE。返回 goal + user_stories + modules。"""
        if not query.strip():
            return []
        q = query.strip().replace('"', '')
        where_clauses: list[str] = []
        params: list[Any] = []

        if mode:
            where_clauses.append("s.mode = ?")
            params.append(mode)

        # 先尝试 FTS5 MATCH
        fts_where = " AND ".join(["specs_fts MATCH ?"] + where_clauses)
        try:
            rows = self._conn.execute(
                f"""SELECT s.goal, s.user_stories, s.modules, s.full_summary, s.created_at
                    FROM specs_fts f
                    JOIN specs s ON s.id = f.rowid
                    WHERE {fts_where}
                    ORDER BY rank
                    LIMIT ?""",
                (q, *params, limit),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("spec FTS search failed, falling back to LIKE: %s", exc)
            rows = []

        # 中文分词 FTS5 无结果时回退 LIKE
        if not rows:
            like_where = " AND ".join(["s.goal LIKE ? OR s.user_text LIKE ?"] + where_clauses)
            like_q = f"%{_like_query(q) or q}%"
            like_params: list[Any] = [like_q, like_q]
            if mode:
                like_params.append(mode)
            rows = self._conn.execute(
                f"""SELECT s.goal, s.user_stories, s.modules, s.full_summary, s.created_at
                    FROM specs s
                    WHERE {like_where}
                    ORDER BY s.created_at DESC
                    LIMIT ?""",
                (*like_params, limit),
            ).fetchall()

        return [dict(r) for r in rows]

    # ── 逆向问题存取 ──────────────────────────────────────

    def save_issues(self, *, profile: str, issues: list[dict[str, str]]) -> int:
        """保存审查发现的问题。若已存在相似文本则累加 frequency，否则新增。返回新增/更新数。"""
        count = 0
        for issue in issues:
            issue_text = issue.get("text", "").strip()
            if not issue_text:
                continue
            issue_type = issue.get("type", "code_quality")
            suggestion = issue.get("suggestion", "")

            # 简单去重：检查完全相同文本是否已存在
            existing = self._conn.execute(
                "SELECT id, frequency FROM review_issues WHERE issue_text = ?",
                (issue_text,),
            ).fetchone()

            if existing:
                self._conn.execute(
                    "UPDATE review_issues SET frequency = frequency + 1, last_seen = ? WHERE id = ?",
                    (_now_iso(), existing["id"]),
                )
            else:
                self._conn.execute(
                    """INSERT INTO review_issues (profile, issue_type, issue_text, suggestion, last_seen)
                       VALUES (?, ?, ?, ?, ?)""",
                    (profile, issue_type, issue_text, suggestion, _now_iso()),
                )
            count += 1
        self._conn.commit()
        logger.info("issues saved: profile=%s count=%d", profile, count)
        return count

    def search_issues(
        self, query: str, profile: str = "", limit: int = 5
    ) -> list[dict[str, Any]]:
        """FTS5 检索高频代码问题，中文回退 LIKE，按频率降序。"""
        if not query.strip():
            return []
        q = query.strip().replace('"', '')
        where_clauses: list[str] = []
        params: list[Any] = []

        if profile:
            where_clauses.append("i.profile = ?")
            params.append(profile)

        # 先尝试 FTS5 MATCH
        fts_where = " AND ".join(["review_issues_fts MATCH ?"] + where_clauses)
        try:
            rows = self._conn.execute(
                f"""SELECT i.issue_type, i.issue_text, i.suggestion, i.frequency, i.last_seen
                    FROM review_issues_fts f
                    JOIN review_issues i ON i.id = f.rowid
                    WHERE {fts_where}
                    ORDER BY i.frequency DESC, rank
                    LIMIT ?""",
                (q, *params, limit),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("issue FTS search failed, falling back to LIKE: %s", exc)
            rows = []

        # 中文分词回退 LIKE
        if not rows:
            like_where = " AND ".join(["i.issue_text LIKE ? OR i.issue_type LIKE ?"] + where_clauses)
            like_q = f"%{_like_query(q) or q}%"
            like_params: list[Any] = [like_q, like_q]
            if profile:
                like_params.append(profile)
            rows = self._conn.execute(
                f"""SELECT i.issue_type, i.issue_text, i.suggestion, i.frequency, i.last_seen
                    FROM review_issues i
                    WHERE {like_where}
                    ORDER BY i.frequency DESC
                    LIMIT ?""",
                (*like_params, limit),
            ).fetchall()

        return [dict(r) for r in rows]

    def get_top_issues(self, profile: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """获取频率最高的问题（不依赖查询关键词）。"""
        where = "WHERE profile = ?" if profile else ""
        params: list[Any] = [profile] if profile else []
        rows = self._conn.execute(
            f"""SELECT issue_type, issue_text, suggestion, frequency, last_seen
                FROM review_issues
                {where}
                ORDER BY frequency DESC
                LIMIT ?""",
            (*params, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── 知识库存取 ──────────────────────────────────────

    def save_knowledge(self, *, title: str, content: str) -> int:
        """保存一条知识文档，返回 row id。"""
        cur = self._conn.execute(
            "INSERT INTO knowledge (title, content, created_at) VALUES (?, ?, ?)",
            (title, content, _now_iso()),
        )
        self._conn.commit()
        logger.info("knowledge saved: title=%s len=%d", title[:80], len(content))
        return cur.lastrowid

    def search_knowledge(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """FTS5 检索知识库，中文回退 LIKE。返回 title + content 摘要。"""
        if not query.strip():
            return []
        q = query.strip().replace('"', '')
        try:
            rows = self._conn.execute(
                """SELECT k.title, k.content, k.created_at
                   FROM knowledge_fts f
                   JOIN knowledge k ON k.id = f.rowid
                   WHERE knowledge_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (q, limit),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            logger.warning("knowledge FTS search failed, falling back to LIKE: %s", exc)
            rows = []

        if not rows:
            like_q = f"%{_like_query(q) or q}%"
            rows = self._conn.execute(
                """SELECT title, content, created_at
                   FROM knowledge
                   WHERE title LIKE ? OR content LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (like_q, like_q, limit),
            ).fetchall()

        return [dict(r) for r in rows]

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# 模块级单例
_store: SpecStore | None = None


def get_spec_store() -> SpecStore:
    global _store
    if _store is None:
        _store = SpecStore()
        atexit.register(_shutdown_store)
    return _store

def _shutdown_store() -> None:
    global _store
    if _store is not None:
        _store.close()
        _store = None
