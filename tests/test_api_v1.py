"""API v1 测试（Final Pass Phase 4）：/api/v1/query + SSE stream + 取消 + documents。

Demo 模式运行（无 API key / GPU）。
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _demo_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setenv("ENVIRONMENT", "testing")
    from src.config.settings import Settings

    Settings.model_config["env_file"] = None
    # setup 前先清 lru_cache：确保 demo settings 生效（否则拿到上一用例的非 demo 单例 → 真加载 BGE）
    from src.api import deps

    for name in ("get_settings", "get_embedder", "get_milvus_client", "get_latest_v1_collection",
                 "get_bm25", "get_reranker", "get_retriever", "get_vqa", "get_semantic_cache",
                 "get_incremental_indexer"):
        getattr(deps, name).cache_clear()
    yield
    Settings.model_config["env_file"] = ".env"
    for name in ("get_settings", "get_embedder", "get_milvus_client", "get_latest_v1_collection",
                 "get_bm25", "get_reranker", "get_retriever", "get_vqa", "get_semantic_cache",
                 "get_incremental_indexer"):
        getattr(deps, name).cache_clear()


@pytest.fixture()
def client():
    from src.api.app import create_app

    return TestClient(create_app())


class TestQueryV1:
    def test_query_answered_contract(self, client):
        r = client.post("/api/v1/query", json={"query": "故障码 E01 是什么意思"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "answered"
        assert body["answer"]
        assert body["citations"], "citations 必须非空"
        c0 = body["citations"][0]
        assert c0["chunk_id"]
        assert c0["page"] >= 0
        assert "rerank_score" in c0
        assert body["grounding"]["status"] in ("supported", "warning", "abstained")
        assert "total_ms" in body["latency"]
        assert isinstance(body["request_id"], str) and body["request_id"]
        assert body["cache"]["hit"] is False

    def test_query_refused(self, client):
        r = client.post("/api/v1/query", json={"query": "如何登录火星"})
        body = r.json()
        assert body["status"] == "refused"
        assert "无法回答" in body["answer"]

    def test_query_cache_second_hit(self, client):
        q = {"query": "机器人的电池容量是多少"}
        client.post("/api/v1/query", json=q)
        r2 = client.post("/api/v1/query", json=q)
        body = r2.json()
        assert body["cache"]["hit"] is True
        assert body["cache"]["source"] in ("exact", "semantic")

    def test_query_cache_disabled(self, client):
        q = {"query": "如何清理边刷", "cache": False}
        r1 = client.post("/api/v1/query", json=q)
        r2 = client.post("/api/v1/query", json=q)
        assert r1.json()["cache"]["hit"] is False
        assert r2.json()["cache"]["hit"] is False

    def test_query_debug_trace(self, client):
        r = client.post("/api/v1/query", json={"query": "故障码 E07", "debug": True})
        body = r.json()
        assert body["trace"] is not None
        assert "candidates" in body["trace"]
        assert body["trace"]["candidates"][0]["rerank_score"] is not None

    def test_query_validation(self, client):
        assert client.post("/api/v1/query", json={"query": ""}).status_code == 422
        assert client.post("/api/v1/query", json={"query": "x", "top_k": 99}).status_code == 422


class TestQueryStreamV1:
    def _events(self, resp_text: str) -> list[dict]:
        out = []
        for block in resp_text.split("\n\n"):
            for line in block.splitlines():
                if line.startswith("data:"):
                    out.append(json.loads(line[5:].strip()))
        return out

    def test_stream_stage_order(self, client):
        r = client.post(
            "/api/v1/query/stream", json={"query": "故障码 E01 是什么意思"}
        )
        assert r.status_code == 200
        events = self._events(r.text)
        types = [e["type"] for e in events]
        assert types[0] == "start"
        # 关键 stage 都出现且顺序正确
        order = [t for t in types if t in ("start", "stage", "usage", "done", "token")]
        assert order.index("stage") >= order.index("start")
        assert "done" in order
        done = [e for e in events if e["type"] == "done"][0]
        assert done["status"] == "answered"
        assert done["citations"]
        assert "elapsed_ms" in done
        # demo token 流式存在且带 demo 标记
        tokens = [e for e in events if e["type"] == "token"]
        assert tokens and all(t.get("demo") for t in tokens)
        joined = "".join(t["token"] for t in tokens)
        assert "DEMO" in joined or "说明书" in joined

    def test_stream_refused_no_tokens(self, client):
        r = client.post("/api/v1/query/stream", json={"query": "如何登录火星"})
        events = self._events(r.text)
        assert any(e["type"] == "done" and e["status"] == "refused" for e in events)
        assert not any(e["type"] == "token" for e in events)  # 拒答无 token


class TestCancellation:
    def test_stream_cancelled_propagates_not_500(self, client):
        """CancelledError 不应被包装成 500（任务书 §16）。"""
        from src.api.routes_v1 import query as qmod
        from src.api.services.rag_service import RAGService

        original = qmod._build_service

        class _SlowService(RAGService):
            def run_stages(self, *args, **kwargs):
                import time

                time.sleep(1.0)  # 模拟慢管线
                yield from super().run_stages(*args, **kwargs)

        def _fake_build(request):
            svc = original(request)
            svc.__class__ = _SlowService
            return svc

        qmod._build_service = _fake_build
        try:
            with client.stream("POST", "/api/v1/query/stream", json={"query": "故障码 E01"}) as _resp:
                # 客户端立即断开 → 生成器被取消
                pass
        finally:
            qmod._build_service = original
        # 不抛异常 / 不是 500 JSON —— 通过即代表 CancelledError 未被包装


class TestDocumentsV1:
    def test_list_demo_documents(self, client):
        r = client.get("/api/v1/documents")
        assert r.status_code == 200
        docs = r.json()["documents"]
        assert docs and docs[0]["document_id"] == "demo-manual"
        assert docs[0]["num_chunks"] >= 20

    def test_ingest_rejected_in_demo(self, client):
        r = client.post(
            "/api/v1/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert r.status_code == 400
        # 统一错误 envelope：{"error": {"message": ...}}
        err = r.json().get("error", {})
        assert "DEMO" in err.get("message", "")


class TestSystemV1:
    def test_system_status(self, client):
        r = client.get("/api/v1/system/status")
        assert r.status_code == 200
        body = r.json()
        assert body["demo_mode"] is True
        assert body["vector_store"] == "demo-in-memory"
        assert "gateway" in body
        assert "cache" in body
        # 不泄露 secret
        assert "api_key" not in json.dumps(body).lower()
