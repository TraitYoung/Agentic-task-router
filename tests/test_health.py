from fastapi.testclient import TestClient

import main


class FailingRedisClient:
    def ping(self):
        raise RuntimeError("redis unavailable")


def test_health_reports_operational_fields_when_redis_is_down(monkeypatch):
    monkeypatch.setattr(main.session_cache, "client", FailingRedisClient())

    response = TestClient(main.app).get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["version"] == "3.0.0"
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["redis"]["ok"] is False
    assert "redis unavailable" in body["redis"]["error"]
    assert body["sqlite"]["ok"] is True
    assert body["memory_mb"] >= 0
    assert isinstance(body["env"]["has_llm_key"], bool)
    assert body["env"]["llm_model"] == "deepseek-v4-pro"
    assert body["env"]["llm_base_url"] == "https://api.deepseek.com/v1"
    assert body["env"]["llm_provider"] == "deepseek"
    assert body["env"]["llm_thinking"] == "enabled"
    assert body["env"]["llm_reasoning_effort"] == "max"
    assert "has_qwen_key" not in body["env"]
