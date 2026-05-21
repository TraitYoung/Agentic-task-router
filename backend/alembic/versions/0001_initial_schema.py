"""Initial schema: specs, review_issues, and FTS5 virtual tables.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-19 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- specs table --
    op.execute(
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
        )
        """
    )

    # -- specs FTS5 virtual table --
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS specs_fts
            USING fts5(mode, profile, user_text, goal, user_stories, modules,
                       content='specs', content_rowid='id')
        """
    )

    # -- specs FTS trigger: after insert --
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS specs_ai AFTER INSERT ON specs BEGIN
            INSERT INTO specs_fts(rowid, mode, profile, user_text, goal, user_stories, modules)
            VALUES (new.id, new.mode, new.profile, new.user_text, new.goal, new.user_stories, new.modules);
        END
        """
    )

    # -- review_issues table --
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS review_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile TEXT NOT NULL DEFAULT '',
            issue_type TEXT NOT NULL,
            issue_text TEXT NOT NULL,
            suggestion TEXT NOT NULL DEFAULT '',
            frequency INTEGER NOT NULL DEFAULT 1,
            last_seen TEXT NOT NULL
        )
        """
    )

    # -- review_issues FTS5 virtual table --
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS review_issues_fts
            USING fts5(profile, issue_type, issue_text, suggestion,
                       content='review_issues', content_rowid='id')
        """
    )

    # -- review_issues FTS trigger: after insert --
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS review_issues_ai AFTER INSERT ON review_issues BEGIN
            INSERT INTO review_issues_fts(rowid, profile, issue_type, issue_text, suggestion)
            VALUES (new.id, new.profile, new.issue_type, new.issue_text, new.suggestion);
        END
        """
    )


def downgrade() -> None:
    # Drop triggers first, then FTS tables, then base tables
    op.execute("DROP TRIGGER IF EXISTS specs_ai")
    op.execute("DROP TRIGGER IF EXISTS review_issues_ai")
    op.execute("DROP TABLE IF EXISTS specs_fts")
    op.execute("DROP TABLE IF EXISTS review_issues_fts")
    op.execute("DROP TABLE IF EXISTS specs")
    op.execute("DROP TABLE IF EXISTS review_issues")
