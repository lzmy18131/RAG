"""可观测性测试（audit O2 / §63）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.metrics import (
    inc_cache_hit,
    inc_grounding_rejection,
    inc_provider_failure,
    metrics,
)
from src.api.middleware import _normalize_path


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_metrics_endpoint_prometheus_format(client):
    client.get("/health/live")  # 产生一次请求计数
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "# TYPE http_requests_total counter" in r.text
    assert "http_requests_total{" in r.text


def test_request_counted(client):
    client.get("/version")
    text = client.get("/metrics").text
    assert 'http_requests_total{method="GET",path="/version",status="200"}' in text


def test_dynamic_path_normalized():
    assert _normalize_path("/documents/0123456789abcdef0123456789abcdef") == "/documents/{id}"
    assert _normalize_path("/query") == "/query"


def test_grounding_rejection_counter():
    before = metrics.snapshot_count("grounding_rejections_total")
    inc_grounding_rejection()
    assert metrics.snapshot_count("grounding_rejections_total") == before + 1


def test_provider_failure_counter_with_label():
    before = metrics.snapshot_count("provider_failures_total", {"provider": "deepseek"})
    inc_provider_failure(provider="deepseek")
    assert metrics.snapshot_count("provider_failures_total", {"provider": "deepseek"}) == before + 1


def test_cache_counter():
    before = metrics.snapshot_count("cache_hits_total", {"kind": "exact"})
    inc_cache_hit(kind="exact")
    assert metrics.snapshot_count("cache_hits_total", {"kind": "exact"}) == before + 1
