"""SessionCache checkpoint 读写测试。"""

import json
from unittest.mock import MagicMock

from memory.session_cache import SessionCache


def _make_cache() -> SessionCache:
    cache = SessionCache(redis_url="redis://localhost:6379/0", ttl_seconds=60)
    cache.client = MagicMock()
    return cache


def test_save_and_get_checkpoint():
    cache = _make_cache()
    payload = {
        "checkpoint_id": "cp-1",
        "session_id": "sess-1",
        "waiting_after": "discovery",
        "results": {"discovery": {"goal": "g"}},
    }
    cache.client.pipeline.return_value.execute.return_value = None

    cp_id = cache.save_checkpoint("sess-1", payload)
    assert cp_id == "cp-1"

    cache.client.get.return_value = json.dumps(payload, ensure_ascii=False)
    loaded = cache.get_checkpoint("cp-1")
    assert loaded is not None
    assert loaded["waiting_after"] == "discovery"


def test_delete_checkpoint():
    cache = _make_cache()
    cache.client.pipeline.return_value.execute.return_value = None
    cache.delete_checkpoint("cp-1", "sess-1")
    cache.client.pipeline.assert_called()


def test_get_checkpoint_missing():
    cache = _make_cache()
    cache.client.get.return_value = None
    assert cache.get_checkpoint("missing") is None
