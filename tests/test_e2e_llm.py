"""End-to-end tests with real LLM calls. Gated by RUN_LLM_TESTS env var.

To run:  RUN_LLM_TESTS=true pytest tests/test_e2e_llm.py -v
In CI these are skipped by default.
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

import main

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LLM_TESTS"),
    reason="Set RUN_LLM_TESTS=true to run LLM-dependent tests",
)


class TestSpecGeneration:
    def test_spec_sync(self):
        client = TestClient(main.app)
        payload = {"text": "Build a simple React todo app with add and delete", "mode": "spec"}

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"]
        assert body["reply"]
        assert body["intent"]
        assert body["trace_id"]
        assert isinstance(body["trace"], list)
        assert len(body["trace"]) >= 1

    def test_spec_stream(self):
        client = TestClient(main.app)
        payload = {"text": "Build a simple React todo app", "mode": "spec"}

        with client.stream("POST", "/api/v1/chat/stream", json=payload) as response:
            assert response.status_code == 200
            body = response.text
            assert "data:" in body


class TestReview:
    def test_review_sync(self):
        client = TestClient(main.app)
        code = "def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b"
        payload = {"text": code, "mode": "review"}

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["session_id"]
        assert body["reply"]
        assert isinstance(body["trace"], list)
        assert len(body["trace"]) >= 1


class TestValidation:
    def test_invalid_mode_returns_422(self):
        client = TestClient(main.app)
        payload = {"text": "hello", "mode": "invalid"}

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 422
        body = response.json()
        assert "error_code" in body

    def test_empty_text_returns_422(self):
        client = TestClient(main.app)
        payload = {"text": "", "mode": "spec"}

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 422
        body = response.json()
        assert "error_code" in body


class TestAuth:
    def test_missing_api_key_returns_401(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "sk-test-key")
        # Force reload of main module's settings — auth middleware reads on each request
        client = TestClient(main.app)
        payload = {"text": "hello", "mode": "spec"}

        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 401
        body = response.json()
        assert body["error_code"] == "AUTH_INVALID"

    def test_valid_api_key_passes(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "sk-test-key")
        client = TestClient(main.app)
        payload = {"text": "hello", "mode": "spec"}
        headers = {"x-api-key": "sk-test-key"}

        response = client.post("/api/v1/chat", json=payload, headers=headers)
        # Should get 422 (validation passes but empty input fails) or 200
        assert response.status_code in (200, 422)


class TestMetrics:
    def test_metrics_endpoint(self):
        client = TestClient(main.app)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "fastapi_request_duration" in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
