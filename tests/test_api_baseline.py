"""API 生产基线测试（audit B1-B3 / §53-56）。

- X-Request-ID 中间件（透传/生成）。
- 统一错误 envelope（不泄漏 stack trace）。
- /health/live /health/ready /version。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture()
def client():
    return TestClient(create_app())


class TestRequestID:
    def test_response_has_request_id(self, client):
        r = client.get("/version")
        assert "X-Request-ID" in r.headers
        assert len(r.headers["X-Request-ID"]) >= 8

    def test_client_request_id_reused(self, client):
        r = client.get("/version", headers={"X-Request-ID": "trace-123"})
        assert r.headers["X-Request-ID"] == "trace-123"

    def test_invalid_request_id_replaced(self, client):
        r = client.get("/version", headers={"X-Request-ID": "x" * 100})
        assert len(r.headers["X-Request-ID"]) <= 64


class TestErrorEnvelope:
    def test_404_envelope(self, client):
        r = client.get("/nonexistent")
        assert r.status_code == 404
        body = r.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["request_id"]

    def test_validation_envelope(self, client):
        # question 类型错误 → 422 VALIDATION_ERROR（不走真实管线）
        r = client.post("/query", json={"question": 12345})
        assert r.status_code == 422
        body = r.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "traceback" not in r.text.lower()

    def test_no_stacktrace_leak(self, client):
        r = client.get("/nonexistent")
        assert "Traceback" not in r.text


class TestHealthVersion:
    def test_health_live(self, client):
        r = client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["version"]

    def test_version_semver(self, client):
        r = client.get("/version")
        assert r.status_code == 200
        body = r.json()
        # app_version 与 pipeline_version 分离（Final Pass §6）
        v = body["app_version"]
        parts = v.split(".")
        assert len(parts) >= 2  # semver，不是 "V9"
        assert body["pipeline_version"] == "rag-v9"
        assert "git_commit" in body  # None 或真实 SHA，禁止伪造

    def test_health_ready_shape(self, client):
        r = client.get("/health/ready")
        assert r.status_code in (200, 503)
        body = r.json()
        assert "checks" in body
        # vector_store（demo=内存 / 生产=Milvus 配置）
        assert "vector_store" in body["checks"]

    def test_health_legacy_still_works(self, client):
        r = client.get("/health")
        assert r.status_code == 200
