"""API v1 契约（Pydantic models，前端不猜 JSON）。

覆盖：QueryRequest/QueryResponse、Citation、Grounding、Usage、SSE 事件。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ==================== Query ====================


class QueryRequest(BaseModel):
    """POST /api/v1/query 请求。"""

    query: str = Field(..., min_length=1, description="用户问题")
    top_k: int = Field(5, ge=1, le=20, description="返回证据条数")
    document_ids: list[str] | None = Field(
        None, description="限定检索的文档（friendly name，如 ['Roborock G10S']）；None = 全部"
    )
    debug: bool = Field(False, description="是否返回完整检索 trace（developer mode）")
    cache: bool = Field(True, description="是否使用语义缓存")


class Citation(BaseModel):
    """答案引用（由系统从检索结果计算，不是 LLM 声称）。"""

    chunk_id: str
    source_file: str = ""
    page: int = 0
    content_type: str = "text"
    content_excerpt: str = ""
    dense_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class GroundingResult(BaseModel):
    """确定性接地验证结果。relevance ≠ entailment，不包装成「概率」。"""

    status: Literal["supported", "warning", "abstained"]
    support_ratio: float | None = None
    unsupported_claims: list[str] = Field(default_factory=list)
    scorer: str = "reranker"


class UsageInfo(BaseModel):
    """LLM/VLM 用量；provider 未返回时 null（禁止伪造 0）。"""

    llm_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    model: str | None = None
    provider: str | None = None


class CacheInfo(BaseModel):
    """缓存命中信息。"""

    hit: bool = False
    source: Literal["exact", "semantic", "none"] = "none"
    corpus_version: str | None = None


class QueryResponse(BaseModel):
    """POST /api/v1/query 响应。"""

    answer: str
    status: Literal["answered", "refused", "fallback"]
    citations: list[Citation] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    grounding: GroundingResult
    usage: UsageInfo = Field(default_factory=UsageInfo)
    latency: dict[str, Any] = Field(default_factory=dict)  # total_ms + per-stage
    cache: CacheInfo = Field(default_factory=CacheInfo)
    request_id: str = "-"
    trace: dict[str, Any] | None = None  # debug=true 时返回完整检索 trace


# ==================== SSE 事件（POST /api/v1/query/stream） ====================


class SSEStage(BaseModel):
    """阶段事件：start / retrieving / reranking / generating / grounding /
    citation_check / usage / done / error。"""

    type: Literal[
        "start",
        "retrieving",
        "reranking",
        "generating",
        "grounding",
        "citation_check",
        "usage",
        "done",
        "error",
        "token",
    ]
    stage: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None


# ==================== Documents ====================


class DocumentIngestRequest(BaseModel):
    """POST /api/v1/documents —— multipart file；本模型仅占位（实际用 UploadFile）。"""


class DocumentItem(BaseModel):
    document_id: str
    source_file: str
    version: str = ""
    num_chunks: int = 0
    pages: int = 0
    status: str = "indexed"


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


# ==================== System ====================


class SystemStatusResponse(BaseModel):
    demo_mode: bool
    embedding_model: str
    reranker_model: str
    vector_store: str
    corpus_version: str | None = None
    cache: dict[str, Any] | None = None
    gateway: dict[str, Any] | None = None
    grounding: dict[str, Any] | None = None
    llm_configured: bool
    vlm_configured: bool
