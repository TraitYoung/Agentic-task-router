import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import redis


class SessionCache:
    """基于 Redis 的会话热缓存，用于滑动窗口上下文注入。"""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 3600,
        window_size: int = 5,
    ) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.ttl_seconds = ttl_seconds
        self.window_size = window_size
        # 避免无 Redis / 半开连接时 LRANGE 等调用无限阻塞，拖死单 worker 的 FastAPI
        self.client = redis.Redis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}:chat_turns"

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        payload = {
            "user": user_text,
            "assistant": assistant_text,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        key = self._key(session_id)
        serialized = json.dumps(payload, ensure_ascii=False)

        # 使用 LPUSH + LTRIM 实现固定长度滑动窗口，并重置 TTL
        self.client.lpush(key, serialized)
        self.client.ltrim(key, 0, self.window_size - 1)
        self.client.expire(key, self.ttl_seconds)

    def get_recent_turns(self, session_id: str, limit: int = 5) -> List[Dict[str, str]]:
        key = self._key(session_id)
        raw_items = self.client.lrange(key, 0, max(limit, 1) - 1)
        turns: List[Dict[str, str]] = []

        # Redis 列表是新到旧，返回时反转为旧到新，便于 prompt 拼接
        for item in reversed(raw_items):
            try:
                parsed = json.loads(item)
                turns.append(
                    {
                        "user": str(parsed.get("user", "")),
                        "assistant": str(parsed.get("assistant", "")),
                        "ts": str(parsed.get("ts", "")),
                    }
                )
            except json.JSONDecodeError:
                continue
        return turns

    def format_recent_history(self, session_id: str, limit: int = 5) -> List[str]:
        turns = self.get_recent_turns(session_id=session_id, limit=limit)
        lines: List[str] = []
        for idx, turn in enumerate(turns, start=1):
            lines.append(
                f"Round {idx}\nUser: {turn['user']}\nAssistant: {turn['assistant']}"
            )
        return lines
