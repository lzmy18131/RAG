"""统一检索契约与配置统一测试（audit R1/R2 / §23、§35-36）。"""

from __future__ import annotations

import pytest

from src.retrieval.contracts import RetrievedChunk
from src.retrieval.hybrid_retriever import HybridRetriever


class TestRetrievedChunk:
    def test_from_dict_maps_existing_keys(self):
        c = RetrievedChunk.from_dict(
            {
                "chunk_id": "abc123",
                "source_file": "/data/manual.pdf",
                "page_number": 7,
                "content_type": "text",
                "content": "内容",
                "retrieval_score": 0.85,
                "rerank_score": 0.92,
                "retrieval_channel": "hybrid",
            }
        )
        assert c.chunk_id == "abc123"
        assert c.page == 7
        assert c.dense_score == pytest.approx(0.85)  # retrieval_score → dense_score
        assert c.rerank_score == pytest.approx(0.92)

    def test_to_dict_roundtrip(self):
        c = RetrievedChunk(
            chunk_id="x",
            source_file="/a.pdf",
            page=3,
            content_type="image",
            content="pic",
            dense_score=0.5,
            fusion_score=0.7,
        )
        d = c.to_dict()
        assert d["page_number"] == 3
        assert d["dense_score"] == 0.5
        assert d["fusion_score"] == 0.7

    def test_none_scores(self):
        c = RetrievedChunk.from_dict({"chunk_id": "x"})
        assert c.dense_score is None
        assert c.rerank_score is None

    def test_metadata_keeps_unknown_keys(self):
        c = RetrievedChunk.from_dict({"chunk_id": "x", "custom_flag": True})
        assert c.metadata.get("custom_flag") is True


class TestRetrievalConfig:
    def test_hybrid_retriever_reads_settings_defaults(self):
        h = HybridRetriever()
        assert h.rrf_k == 60
        assert h.dense_top_k == 20
        assert h.bm25_top_k == 20

    def test_explicit_override_wins(self):
        h = HybridRetriever(rrf_k=10, dense_top_k=5)
        assert h.rrf_k == 10
        assert h.dense_top_k == 5
        assert h.bm25_top_k == 20  # 未覆盖的用默认

    def test_no_magic_numbers_in_search(self):
        # 搜索路径不应再出现硬编码 20/k=60（config 驱动）
        src = open(HybridRetriever.__module__.replace(".", "/") + ".py", encoding="utf-8").read()
        assert "top_k=20" not in src
