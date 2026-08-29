"""
统一检索契约（audit R1 / 任务书 §23）。

RetrievedChunk 是检索结果的正式类型：替代散落的 dict[str, Any]。
现有代码返回的 dict 键（chunk_id/content/source_file/page_number/content_type/
retrieval_score/rerank_score/dense_rank/bm25_rank/rrf_score/fusion_score）
通过 from_dict/to_dict 双向映射，保持向后兼容。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievedChunk:
    """检索结果单元。"""

    chunk_id: str
    document_id: str = ""
    source_file: str = ""
    page: int = 0
    content_type: str = "text"
    content: str = ""
    dense_score: float | None = None
    sparse_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None
    dense_rank: int | None = None
    bm25_rank: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── 与既有 dict 结果的双向映射 ──

    @classmethod
    def from_dict(cls, d: dict) -> RetrievedChunk:
        return cls(
            chunk_id=str(d.get("chunk_id", d.get("id", ""))),
            document_id=str(d.get("document_id", "")),
            source_file=str(d.get("source_file", "")),
            page=int(d.get("page_number", d.get("page", 0)) or 0),
            content_type=str(d.get("content_type", "text")),
            content=str(d.get("content", "")),
            dense_score=_as_float(d.get("dense_score", d.get("retrieval_score"))),
            sparse_score=_as_float(d.get("bm25_score", d.get("sparse_score"))),
            fusion_score=_as_float(d.get("fusion_score", d.get("rrf_score"))),
            rerank_score=_as_float(d.get("rerank_score")),
            dense_rank=_as_int(d.get("dense_rank")),
            bm25_rank=_as_int(d.get("bm25_rank")),
            metadata={k: v for k, v in d.items() if k not in _RESERVED},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_file": self.source_file,
            "page_number": self.page,
            "content_type": self.content_type,
            "content": self.content,
            "dense_score": self.dense_score,
            "sparse_score": self.sparse_score,
            "fusion_score": self.fusion_score,
            "rerank_score": self.rerank_score,
            "dense_rank": self.dense_rank,
            "bm25_rank": self.bm25_rank,
            "retrieval_channel": "hybrid",
        }


_RESERVED = {
    "chunk_id",
    "id",
    "document_id",
    "source_file",
    "page_number",
    "page",
    "content_type",
    "content",
    "dense_score",
    "retrieval_score",
    "bm25_score",
    "sparse_score",
    "fusion_score",
    "rrf_score",
    "rerank_score",
    "dense_rank",
    "bm25_rank",
    "retrieval_channel",
}


def _as_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _as_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def chunks_to_dicts(chunks: list[RetrievedChunk]) -> list[dict]:
    return [c.to_dict() for c in chunks]
