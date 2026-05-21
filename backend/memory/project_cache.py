"""轻量项目记忆：按 project_id 存储项目摘要与上下文，复用 Redis。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis

from config.settings import get_settings

REDIS_URL = get_settings().redis_url


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectCache:
    def __init__(self, ttl_seconds: int = 86400 * 7):
        self.ttl = ttl_seconds
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        return self._client

    def _key(self, project_id: str) -> str:
        return f"specforge:project:{project_id}"

    def _index_key(self) -> str:
        return "specforge:projects"

    def save_snapshot(self, project_id: str, snapshot: dict[str, Any]) -> None:
        snapshot["updated_at"] = _now_iso()
        try:
            self.client.set(self._key(project_id), json.dumps(snapshot, ensure_ascii=False), ex=self.ttl)
            self.client.sadd(self._index_key(), project_id)
            self.client.expire(self._index_key(), self.ttl)
        except Exception:
            pass

    def get_context(self, project_id: str) -> dict[str, Any] | None:
        try:
            raw = self.client.get(self._key(project_id))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def list_projects(self) -> list[str]:
        try:
            return sorted(self.client.smembers(self._index_key()))
        except Exception:
            return []

    def delete_project(self, project_id: str) -> None:
        try:
            self.client.delete(self._key(project_id))
            self.client.srem(self._index_key(), project_id)
        except Exception:
            pass
