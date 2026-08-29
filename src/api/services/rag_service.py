"""RAG 应用服务层（HTTP route → service → RAG core）。

封装 v1 query 管线：缓存查找 → Hybrid 检索（dense+BM25+RRF）→ rerank →
相关性判断 → 生成 → 确定性接地 → 引用校验 → 缓存写入，并对每个阶段计时。
与 VerifiedQA 图共享相同的检索/生成/验证组件（单一事实来源）。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from src.api.schemas import (
    CacheInfo,
    Citation,
    GroundingResult,
    UsageInfo,
)


@dataclass
class QueryResult:
    """v1 query 管线结果（内部表示）。"""

    answer: str
    status: str  # answered | refused | fallback
    citations: list[Citation] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    grounding: GroundingResult = field(default_factory=lambda: GroundingResult(status="abstained"))
    usage: UsageInfo = field(default_factory=UsageInfo)
    latency: dict[str, Any] = field(default_factory=dict)
    cache: CacheInfo = field(default_factory=CacheInfo)
    request_id: str = "-"
    trace: dict[str, Any] | None = None


def _stage_timer(stages: dict[str, float], name: str):
    t0 = time.perf_counter()

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            stages[name] = round((time.perf_counter() - t0) * 1000, 2)
            return False

    return _Ctx()


class RAGService:
    """v1 query 管线服务。"""

    REFUSE_ANSWER = "根据现有说明书内容无法回答此问题。"

    def __init__(
        self,
        retriever,
        generator_fn: Callable,
        verifier_fn: Callable,
        cache=None,
        relevance_threshold: float = 0.05,
    ):
        self.retriever = retriever
        self.generator_fn = generator_fn
        self.verifier_fn = verifier_fn
        self.cache = cache
        self.relevance_threshold = relevance_threshold

    # ── 工具 ──

    def _resolve_doc_filter(self, document_ids: list[str] | None) -> str | None:
        """document_ids（friendly name）→ source_file filter（V8 doc_filter 语义）。"""
        if not document_ids:
            return None
        from src.eval.doc_registry import source_document_map

        mapping = source_document_map()
        resolved = [mapping.get(d) for d in document_ids]
        resolved = [p for p in resolved if p]
        return resolved[0] if len(resolved) == 1 else None

    def _corpus_version(self) -> str:
        """corpus_version：由 manifests.json 派生（与 legacy /query 一致）。"""
        import hashlib
        from pathlib import Path

        p = Path.cwd() / "storage" / "manifests" / "manifests.json"
        try:
            if p.exists():
                return hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        except Exception:  # noqa: BLE001
            pass
        from src.infra.demo import DEMO_COLLECTION

        return DEMO_COLLECTION

    # ── 主入口 ──

    def query(
        self,
        question: str,
        top_k: int = 5,
        document_ids: list[str] | None = None,
        use_cache: bool = True,
        debug: bool = False,
        request_id: str = "-",
    ) -> QueryResult:
        """非流式 v1 query：跑完整管线，返回 QueryResult。"""
        result: QueryResult | None = None
        for _stage, _detail, _ms in self.run_stages(
            question,
            top_k=top_k,
            document_ids=document_ids,
            use_cache=use_cache,
            debug=debug,
            request_id=request_id,
        ):
            result = _detail.get("result") if _detail.get("result") is not None else result
        assert result is not None
        return result

    def run_stages(
        self,
        question: str,
        top_k: int = 5,
        document_ids: list[str] | None = None,
        use_cache: bool = True,
        debug: bool = False,
        request_id: str = "-",
    ):
        """分阶段执行管线，逐步 yield (stage, detail, duration_ms)。

        stages: cache_lookup / retrieving / reranking / generating / grounding /
                citation_check / usage / done。
        供 SSE 流式端点实时下发；非流式 query() 消费同一实现（单一事实来源）。
        """
        stages: dict[str, float] = {}
        t_total = time.perf_counter()
        doc_filter = self._resolve_doc_filter(document_ids)
        corpus_version = self._corpus_version()
        # salt 含响应 schema 版本：v1 契约与 legacy /query 缓存不串用（任务书 §26）
        cache_salt = f"{doc_filter or ''}|corpus:{corpus_version}|schema:v1"

        # ── 1. 缓存查找 ──
        with _stage_timer(stages, "cache_lookup_ms"):
            cached_raw = None
            if use_cache and self.cache is not None:
                cached_raw = self.cache.get(question, salt=cache_salt)
        if cached_raw is not None:
            resp, source = cached_raw
            try:
                result = QueryResult(
                    answer=resp.get("answer", ""),
                    status=resp.get("status", "answered"),
                    citations=[Citation(**c) for c in resp.get("citations", [])],
                    sources=resp.get("sources", []),
                    grounding=GroundingResult(**resp.get("grounding", {})),
                    usage=UsageInfo(**resp.get("usage", {})),
                    cache=CacheInfo(hit=True, source=source, corpus_version=corpus_version),
                    request_id=request_id,
                )
            except Exception:  # noqa: BLE001 - 缓存条目 schema 不兼容 → 视为未命中
                cached_raw = None

        if cached_raw is not None:
            result.latency = {"total_ms": 0, "cache_hit": True, **stages}
            yield (
                "cache_lookup",
                {"cache_hit": True, "source": source, "result": result},
                stages["cache_lookup_ms"],
            )
            yield "done", {"result": result}, 0
            return

        yield "start", {"question": question, "top_k": top_k}, 0

        # ── 2. 检索（hybrid → rerank） ──
        with _stage_timer(stages, "retrieve_ms"):
            try:
                chunks = self.retriever.search(
                    question, top_k=top_k, mode="reranked", doc_filter=doc_filter
                )
            except Exception:  # noqa: BLE001 - 检索失败 → fallback
                chunks = []
        yield "retrieving", {"chunks": len(chunks)}, stages["retrieve_ms"]
        yield "reranking", {"reranked": True}, stages.get("retrieve_ms", 0)

        # 相关性判断
        best = max(
            (c.get("rerank_score") or c.get("retrieval_score") or 0.0 for c in chunks),
            default=0.0,
        )
        relevant = bool(chunks) and best >= self.relevance_threshold

        if not relevant:
            result = QueryResult(
                answer=self.REFUSE_ANSWER,
                status="refused",
                sources=[self._source_dict(c) for c in chunks],
                grounding=GroundingResult(
                    status="abstained",
                    support_ratio=0.0,
                    unsupported_claims=["问题与说明书内容无关或证据不足"],
                ),
                latency={"total_ms": 0, **stages},
                request_id=request_id,
            )
            if debug:
                result.trace = self._build_trace(question, chunks, stages)
            self._maybe_cache(question, result, cache_salt, use_cache)
            result.latency["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)
            yield "grounding", {"status": "abstained", "result": result}, 0
            yield "usage", {"llm_calls": 0, "result": result}, 0
            yield "done", {"result": result}, 0
            return

        # ── 3. 生成 ──
        with _stage_timer(stages, "generate_ms"):
            gen = self.generator_fn(question, chunks)
        answer = gen.get("answer", "")
        usage_raw = gen.get("usage")
        usage = UsageInfo(
            llm_calls=1 if gen.get("model") else 0,
            input_tokens=usage_raw.get("input_tokens") if isinstance(usage_raw, dict) else None,
            output_tokens=usage_raw.get("output_tokens") if isinstance(usage_raw, dict) else None,
            total_tokens=usage_raw.get("total_tokens") if isinstance(usage_raw, dict) else None,
            model=gen.get("model"),
        )
        yield "generating", {"model": gen.get("model"), "answer": answer}, stages["generate_ms"]

        # ── 4. 确定性接地 ──
        with _stage_timer(stages, "grounding_ms"):
            try:
                vr = self.verifier_fn(question, answer, chunks)
            except Exception:  # noqa: BLE001
                vr = {"supported": False, "unsupported_claims": ["grounding error"]}
        supported = bool(vr.get("supported"))
        unsupported = vr.get("unsupported_claims", []) or []
        g_status: Literal["supported", "warning", "abstained"] = (
            "supported" if supported else ("warning" if unsupported else "abstained")
        )
        grounding = GroundingResult(
            status=g_status,
            support_ratio=vr.get("support_ratio"),
            unsupported_claims=unsupported,
            scorer="reranker",
        )
        yield "grounding", {"status": g_status}, stages["grounding_ms"]

        # ── 5. 引用校验 ──
        with _stage_timer(stages, "citation_ms"):
            citations = self._build_citations(chunks, question, answer)
        yield "citation_check", {"citations": len(citations)}, stages["citation_ms"]

        final_status = "answered" if supported else "refused"
        final_answer = answer if supported else self.REFUSE_ANSWER

        result = QueryResult(
            answer=final_answer,
            status=final_status,
            citations=citations,
            sources=[self._source_dict(c) for c in chunks],
            grounding=grounding,
            usage=usage,
            latency={"total_ms": 0, **stages},
            request_id=request_id,
        )
        if debug:
            result.trace = self._build_trace(question, chunks, stages)
        self._maybe_cache(question, result, cache_salt, use_cache)
        result.latency["total_ms"] = round((time.perf_counter() - t_total) * 1000, 2)

        yield "usage", {"llm_calls": usage.llm_calls, "result": result}, 0
        yield "done", {"result": result}, 0

    # ── 内部 ──

    def _maybe_cache(self, question: str, result: QueryResult, salt: str, use_cache: bool) -> None:
        if use_cache and self.cache is not None and result.status == "answered":
            try:
                self.cache.put(
                    question,
                    {
                        "answer": result.answer,
                        "status": result.status,
                        "citations": [c.model_dump() for c in result.citations],
                        "sources": result.sources,
                        "grounding": result.grounding.model_dump(),
                        "usage": result.usage.model_dump(),
                    },
                    salt=salt,
                )
            except Exception:  # noqa: BLE001 - 缓存失败不影响回答
                pass

    def _build_citations(self, chunks: list[dict], question: str, answer: str) -> list[Citation]:
        """由系统计算引用：只引用真实检索返回的 chunk（任务书 §36/§37）。"""
        out: list[Citation] = []
        for c in chunks[:5]:
            out.append(
                Citation(
                    chunk_id=str(c.get("chunk_id", "")),
                    source_file=str(c.get("source_file", "")),
                    page=int(c.get("page_number", 0) or 0),
                    content_type=str(c.get("content_type", "text")),
                    content_excerpt=str(c.get("content", ""))[:200],
                    dense_score=c.get("dense_score"),
                    bm25_score=c.get("bm25_score"),
                    rrf_score=c.get("rrf_score"),
                    rerank_score=c.get("rerank_score"),
                )
            )
        return out

    @staticmethod
    def _source_dict(c: dict) -> dict[str, Any]:
        return {
            "chunk_id": c.get("chunk_id", ""),
            "source_file": c.get("source_file", ""),
            "page_number": c.get("page_number", 0),
            "content_type": c.get("content_type", "text"),
            "dense_score": c.get("dense_score"),
            "bm25_score": c.get("bm25_score"),
            "rrf_score": c.get("rrf_score"),
            "rerank_score": c.get("rerank_score"),
        }

    def _build_trace(self, question: str, chunks: list[dict], stages: dict) -> dict:
        return {
            "query": question,
            "stages": stages,
            "candidates": [
                {
                    "chunk_id": c.get("chunk_id", ""),
                    "dense_rank": c.get("dense_rank"),
                    "bm25_rank": c.get("bm25_rank"),
                    "rrf_score": c.get("rrf_score"),
                    "rerank_score": c.get("rerank_score"),
                    "rerank_rank": c.get("rerank_rank"),
                    "ranking_changed": c.get("ranking_changed"),
                }
                for c in chunks
            ],
        }
