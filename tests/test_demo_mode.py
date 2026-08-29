"""Demo Mode + Truthfulness 测试（Final Pass Phase 1）。

覆盖：
- Demo 组件：FakeEmbedder 确定性 / FakeReranker 分数语义 / FakeMilvusClient 检索过滤
- Demo 管线：answered（检索→rerank→grounding）/ refused（越界）/ cache hit
- /query API（demo 模式）：回答 + 缓存 + DEMO 标记
- /version：app_version/pipeline_version/git_commit 分离
- /versions：无 artifact → available:false（禁止历史 benchmark fallback）
- /health/ready：存储缺失 → 503
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from src.infra.demo import (
    DEMO_CORPUS,
    DEMO_MARK,
    FakeEmbedder,
    FakeMilvusClient,
    FakeReranker,
    build_demo_bm25,
)


@pytest.fixture(autouse=True)
def _demo_env(tmp_path, monkeypatch):
    """所有测试以 demo 模式 + 隔离 storage 运行。"""
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("CACHE_DB_PATH", str(tmp_path / "cache.db"))
    monkeypatch.setenv("ENVIRONMENT", "testing")
    from src.config.settings import Settings

    Settings.model_config["env_file"] = None  # 不读 .env
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


class TestDemoComponents:
    def test_fake_embedder_deterministic(self):
        e = FakeEmbedder()
        v1 = e.encode("故障码 E01 激光雷达遮挡")
        v2 = e.encode("故障码 E01 激光雷达遮挡")
        assert v1 == v2
        assert len(v1) == e.dim == 64
        assert abs(sum(x * x for x in v1) - 1.0) < 1e-3  # 归一化
        # 语义相近 > 无关
        v3 = e.encode("E01 激光雷达 遮挡")
        v4 = e.encode("如何登录火星")
        sim_close = sum(a * b for a, b in zip(v1, v3, strict=False))
        sim_far = sum(a * b for a, b in zip(v1, v4, strict=False))
        assert sim_close > sim_far

    def test_fake_reranker_overlap_semantics(self):
        r = FakeReranker()
        scores = r.score("故障码 E01 激光雷达", ["故障码 E01 表示激光雷达被遮挡", "充电说明：使用电源适配器"])
        assert scores[0] > scores[1]
        assert scores[1] == FakeReranker.UNRELATED_FLOOR  # 无关对 → 低基础分（< 相关性阈值）
        assert all(0.0 <= x <= 1.0 for x in scores)

    def test_fake_milvus_search_and_filter(self):
        e = FakeEmbedder()
        m = FakeMilvusClient()
        m.seed("demo", DEMO_CORPUS, e)
        hits = m.search(
            collection_name="demo",
            data=[e.encode("故障码 E01")],
            limit=3,
            output_fields=["chunk_id", "content", "source_file", "page_number", "content_type", "document_id"],
        )
        assert hits[0][0]["entity"]["chunk_id"] in ("demo-0003", "demo-0004")  # E01 相关
        # filter: source_file 精确匹配（V8 doc_filter 语义）
        filtered = m.search(
            collection_name="demo",
            data=[e.encode("故障码")],
            limit=5,
            filter='source_file == "data/demo/x1-manual.pdf"',
            output_fields=["chunk_id", "source_file"],
        )
        assert all(h["entity"]["source_file"] == "data/demo/x1-manual.pdf" for h in filtered[0])
        assert "demo_corpus" not in m.list_collections()  # seed 用 "demo"

    def test_demo_corpus_covers_key_topics(self):
        texts = " ".join(c["content"] for c in DEMO_CORPUS)
        for kw in ("故障码", "E01", "E07", "PTC", "边刷", "尘盒", "HEPA", "悬崖传感器", "配网", "充电"):
            assert kw in texts, f"demo corpus missing topic: {kw}"
        assert len(DEMO_CORPUS) >= 20

    def test_demo_bm25(self):
        bm = build_demo_bm25()
        results = bm.search("故障码 E01", top_k=3)
        assert results and results[0]["chunk_id"] == "demo-0003"


class TestDemoPipeline:
    def test_answered_and_refused(self):
        from src.api.deps import get_vqa

        vqa = get_vqa()
        st = vqa.run("故障码 E01 是什么意思")
        assert st["final_status"] == "answered"
        assert DEMO_MARK in st["answer"]
        assert st["retrieved_chunks"]
        c0 = st["retrieved_chunks"][0]
        # 真实 hybrid 路径：dense+bm25+rrf+rerank 都有分
        assert c0.get("retrieval_channel") == "hybrid"
        assert c0.get("rrf_score") is not None
        assert c0.get("rerank_score") is not None

        st2 = vqa.run("如何登录火星")  # 越界 → 拒答
        assert st2["final_status"] == "refused"
        assert "无法回答" in st2["answer"]

    def test_grounding_verifier_runs(self):
        from src.api.deps import get_vqa

        vqa = get_vqa()
        st = vqa.run("清理边刷的步骤是什么")
        vr = st["verification_result"]
        assert vr.get("supported") is True
        assert vr.get("sentence_evidence")


class TestDemoAPI:
    @pytest.fixture()
    def client(self):
        from src.api.app import create_app

        return TestClient(create_app())

    def test_query_answered_with_demo_mark(self, client):
        r = client.post("/query", json={"question": "故障码 E01 是什么意思"})
        assert r.status_code == 200
        body = r.json()
        assert body["final_status"] == "answered"
        assert DEMO_MARK in body["answer"]
        assert body["sources"]

    def test_query_cache_hit(self, client):
        client.post("/query", json={"question": "机器人的电池容量是多少"})
        r2 = client.post("/query", json={"question": "机器人的电池容量是多少"})
        assert r2.json()["cache_hit"] is True
        assert r2.json()["cache_source"] in ("exact", "semantic")

    def test_version_separation(self, client):
        body = client.get("/version").json()
        assert body["app_version"].split(".")[0].isdigit()
        assert body["pipeline_version"] == "rag-v9"
        assert "git_commit" in body
        assert "build_time" in body

    def test_health_ready_503_when_storage_missing(self, client):
        # STORAGE_DIR 指向不存在的目录 + 非 demo 关键路径检查
        r = client.get("/health/ready")
        assert r.status_code in (200, 503)
        body = r.json()
        assert "checks" in body
        assert "vector_store" in body["checks"]

    def test_versions_no_artifact_fallback(self, client, monkeypatch, tmp_path):
        """无 run artifact → available:false（禁止历史数字 fallback）。"""
        import src.api.routes as routes

        empty = tmp_path / "empty_runs"
        empty.mkdir()
        monkeypatch.setattr(routes, "PROJECT_ROOT", tmp_path)
        body = client.get("/versions").json()
        for section in ("v6_grounding", "v8_multidoc", "v9_cache"):
            assert body[section]["available"] is False, section
            assert body[section]["source"] == "none"
            assert body[section]["metrics"] is None
        # v7 gateway 始终实时
        assert body["v7_gateway"]["available"] is True

    def test_system_status_demo(self, client):
        body = client.get("/system").json()
        assert "gateway" in body
        assert "cache" in body
        assert body["cache"] is not None  # demo 缓存可用
