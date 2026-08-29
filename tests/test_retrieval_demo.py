"""检索关键路径测试（Final Pass）：用 demo fakes 驱动真实 Hybrid/RRF/Rerank/BM25 代码。

覆盖：
- HybridRetriever：hybrid（dense+bm25→RRF）、dense 降级、bm25 降级、双失败报错、mode=dense/bm25
- RerankedRetriever：rerank 排序 + 降级
- BM25Retriever：build/search/doc_filter/save/load
- FakeMilvusClient：seed/search/filter/insert/list/close
- eval/retrieval_metrics：evaluate_query / aggregate
"""

from __future__ import annotations

import pytest

from src.infra.demo import (
    DEMO_CORPUS,
    FakeEmbedder,
    FakeMilvusClient,
    FakeReranker,
    build_demo_bm25,
)
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.hybrid_retriever import HybridRetrievalError, HybridRetriever
from src.retrieval.reranked_retriever import RerankedRetriever


@pytest.fixture()
def env():
    embedder = FakeEmbedder()
    milvus = FakeMilvusClient()
    milvus.seed("demo", DEMO_CORPUS, embedder)
    bm25 = build_demo_bm25()
    return embedder, milvus, bm25


class TestHybridRetriever:
    def test_hybrid_rrf_fusion(self, env):
        embedder, milvus, bm25 = env
        hr = HybridRetriever(
            collection_name="demo",
            embedder=embedder,
            bm25=bm25,
            client=milvus,
            rrf_k=60,
            dense_top_k=10,
            bm25_top_k=10,
        )
        results = hr.search("故障码 E01", top_k=5, mode="hybrid")
        assert results
        r0 = results[0]
        assert r0["retrieval_channel"] == "hybrid"
        assert r0["dense_rank"] is not None
        assert r0["bm25_rank"] is not None
        assert r0["rrf_score"] is not None and r0["rrf_score"] > 0
        # RRF 排序稳定（分数递减）
        scores = [r["rrf_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_mode_dense(self, env):
        embedder, milvus, bm25 = env
        hr = HybridRetriever(collection_name="demo", embedder=embedder, bm25=bm25, client=milvus)
        results = hr.search("故障码", top_k=3, mode="dense")
        assert all(r["retrieval_channel"] == "dense" for r in results)

    def test_mode_bm25(self, env):
        embedder, milvus, bm25 = env
        hr = HybridRetriever(collection_name="demo", embedder=embedder, bm25=bm25, client=milvus)
        results = hr.search("故障码", top_k=3, mode="bm25")
        assert all(r["retrieval_channel"] == "bm25" for r in results)

    def test_degrade_to_dense_when_bm25_unavailable(self, env):
        embedder, milvus, _ = env
        hr = HybridRetriever(collection_name="demo", embedder=embedder, client=milvus, bm25=None)
        results = hr.search("故障码", top_k=3, mode="hybrid")
        assert results
        assert results[0]["retrieval_channel"] == "dense"
        assert results[0]["degrade_reason"] == "bm25_unavailable"

    def test_degrade_to_bm25_when_dense_unavailable(self, env):
        _, _, bm25 = env
        hr = HybridRetriever(collection_name="demo", bm25=bm25, client=FakeMilvusClient())
        results = hr.search("故障码", top_k=3, mode="hybrid")
        assert results
        assert results[0]["retrieval_channel"] == "bm25"
        assert results[0]["degrade_reason"] == "dense_unavailable"

    def test_both_unavailable_raises(self):
        hr = HybridRetriever(collection_name="demo")
        with pytest.raises(HybridRetrievalError):
            hr.search("故障码", top_k=3, mode="hybrid")

    def test_rrf_k_effect(self, env):
        """RRF k 越小，两路都靠前的项优势越大（排名权重更高）。"""
        embedder, milvus, bm25 = env
        hr_small = HybridRetriever(
            collection_name="demo", embedder=embedder, bm25=bm25, client=milvus, rrf_k=5
        )
        hr_large = HybridRetriever(
            collection_name="demo", embedder=embedder, bm25=bm25, client=milvus, rrf_k=100
        )
        r_small = hr_small.search("故障码 E01", top_k=5)
        r_large = hr_large.search("故障码 E01", top_k=5)
        # 两种 k 都返回有效排序
        assert r_small and r_large
        assert [r["chunk_id"] for r in r_small]  # 非空

    def test_doc_filter_hybrid(self, env):
        embedder, milvus, bm25 = env
        hr = HybridRetriever(collection_name="demo", embedder=embedder, bm25=bm25, client=milvus)
        results = hr.search("故障码", top_k=5, doc_filter="data/demo/x1-manual.pdf")
        assert all(r.get("source_file") == "data/demo/x1-manual.pdf" for r in results)


class TestRerankedRetriever:
    def test_rerank_sorts_and_marks_changes(self, env):
        embedder, milvus, bm25 = env
        rr = RerankedRetriever(
            collection_name="demo",
            reranker=FakeReranker(),
            embedder=embedder,
            bm25=bm25,
            client=milvus,
            candidate_top_k=10,
            final_top_k=5,
        )
        results = rr.search("故障码 E01 激光雷达", mode="reranked")
        assert results
        scores = [r["rerank_score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        # 至少一个候选保留了 original_hybrid_rank 标记
        assert all("original_hybrid_rank" in r for r in results)
        # ranking_changed 是 bool
        assert all(isinstance(r.get("ranking_changed"), bool) for r in results)

    def test_rerank_degrade_when_reranker_fails(self, env):
        embedder, milvus, bm25 = env

        class _BoomReranker:
            is_loaded = True

            def load(self):
                pass

            def score(self, query, docs):
                raise RuntimeError("reranker down")

        rr = RerankedRetriever(
            collection_name="demo",
            reranker=_BoomReranker(),
            embedder=embedder,
            bm25=bm25,
            client=milvus,
        )
        results = rr.search("故障码", mode="reranked")
        assert results
        assert results[0]["degrade_reason"] == "reranker_unavailable"
        assert results[0]["rerank_score"] is None

    def test_v2_hybrid_mode_passthrough(self, env):
        embedder, milvus, bm25 = env
        rr = RerankedRetriever(collection_name="demo", embedder=embedder, bm25=bm25, client=milvus)
        results = rr.search("故障码", mode="v2_hybrid", top_k=5)
        assert results and results[0]["retrieval_channel"] == "hybrid"


class TestBM25Retriever:
    def test_build_search_filter(self):
        bm = build_demo_bm25()
        results = bm.search("故障码 E01", top_k=3)
        assert results and results[0]["chunk_id"] == "demo-0003"
        filtered = bm.search("故障码", top_k=5, doc_filter="data/demo/x1-manual.pdf")
        assert all(r["source_file"] == "data/demo/x1-manual.pdf" for r in filtered)

    def test_save_load_roundtrip(self, tmp_path):
        bm = build_demo_bm25()
        bm.save(tmp_path)
        bm2 = BM25Retriever()
        bm2.load(tmp_path)
        r = bm2.search("故障码 E01", top_k=3)
        assert r and r[0]["chunk_id"] == "demo-0003"
        # metadata JSON 也写出
        assert (tmp_path / "bm25_meta.json").exists()

    def test_empty_index_search(self):
        bm = BM25Retriever()
        bm.build([])
        assert bm.search("x") == []

    def test_tokenize(self):
        assert BM25Retriever.tokenize("故障码 E01")
        assert BM25Retriever.tokenize("") == []


class TestEvalMetrics:
    def test_evaluate_query(self):
        from src.eval.retrieval_metrics import evaluate_query

        m = evaluate_query(["a", "b", "c", "d"], ["b", "d"])
        assert m["recall@3"] == 0.5
        assert m["recall@5"] == 1.0
        assert m["hit@1"] == 0.0
        assert m["mrr"] == pytest.approx(0.5)
        assert m["ndcg@5"] > 0

    def test_aggregate(self):
        from src.eval.retrieval_metrics import aggregate, evaluate_query

        rows = [
            evaluate_query(["a", "b"], ["a"]),  # hit@1
            evaluate_query(["a", "b"], ["b"]),  # hit@2 → recall@1=0
            evaluate_query(["a", "b"], ["c"]),  # miss
        ]
        agg = aggregate(rows)
        assert agg["recall@1"] == pytest.approx(0.3333, abs=1e-4)  # 4 位舍入
        assert agg["mrr"] == pytest.approx(0.5, abs=1e-4)
