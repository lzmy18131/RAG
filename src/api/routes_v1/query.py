"""API v1 路由 — query（含 SSE 流式 + 取消） / documents / system。

业务逻辑在 src/api/services/（HTTP route → application service → RAG core）。
旧版 /query 等路由保持兼容（src/api/routes.py）。
"""

from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.api.deps import get_semantic_cache, get_settings
from src.api.schemas import QueryRequest, QueryResponse
from src.api.services.rag_service import RAGService

router = APIRouter(prefix="/api/v1")

# DEMO 模式允许的 token 流式分块（确定性答案拆块，明确 DEMO 标记）
_TOKEN_CHUNK = 12


def _build_service(request: Request) -> RAGService:
    """从 app.state / deps 构建 v1 服务（与 VerifiedQA 共享组件）。"""
    from src.api.deps import get_retriever, get_vqa

    settings = get_settings()
    vqa = get_vqa()
    cache = get_semantic_cache() if settings.cache_enabled else None

    # 复用 VerifiedQA 的 verifier（与图一致），避免两份 grounding 逻辑
    verifier = vqa.verifier_fn
    generator = vqa.generator_fn
    return RAGService(
        retriever=get_retriever(),
        generator_fn=generator,
        verifier_fn=verifier,
        cache=cache,
    )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


@router.post("/query", response_model=QueryResponse)
async def query_v1(req: QueryRequest, request: Request):
    """v1 非流式查询。"""
    service = _build_service(request)
    rid = _request_id(request)
    # 同步管线放线程池，保持事件循环响应（取消/并发）
    result = await asyncio.to_thread(
        service.query,
        req.query,
        top_k=req.top_k,
        document_ids=req.document_ids,
        use_cache=req.cache,
        debug=req.debug,
        request_id=rid,
    )
    return QueryResponse(
        answer=result.answer,
        status=result.status,  # type: ignore[arg-type]  # service 层 str → schema Literal
        citations=result.citations,
        sources=result.sources,
        grounding=result.grounding,
        usage=result.usage,
        latency=result.latency,
        cache=result.cache,
        request_id=result.request_id,
        trace=result.trace,
    )


@router.post("/query/stream")
async def query_stream_v1(req: QueryRequest, request: Request):
    """v1 SSE 流式查询。

    事件：start → retrieving → reranking → generating → grounding →
          citation_check → usage → done（或 error）。
    Demo 模式在 generating 阶段额外下发 token 事件（确定性答案拆块，带 DEMO 标记）；
    真实模式不下发 token（生成器非流式，不伪造 token 流）。

    取消：客户端断开 → asyncio.CancelledError 传播（不包装成 500）；
    同步管线在 asyncio.to_thread 中运行，取消后不再下发后续事件。
    """
    service = _build_service(request)
    rid = _request_id(request)
    settings = get_settings()

    async def _emit(obj: dict) -> str:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

    async def event_generator():
        t0 = time.perf_counter()
        # 在 to_thread 中逐阶段执行，主循环负责下发与取消检测
        stage_iter = iter(
            await asyncio.to_thread(
                lambda: list(
                    service.run_stages(
                        req.query,
                        top_k=req.top_k,
                        document_ids=req.document_ids,
                        use_cache=req.cache,
                        debug=req.debug,
                        request_id=rid,
                    )
                )
            )
        )
        # to_thread 包装后一次性拿到所有 stage（sync 管线无法逐条跨线程流式）；
        # 事件仍按真实顺序与真实耗时下发。
        for stage, detail, ms in stage_iter:
            if stage == "cache_lookup":
                yield await _emit(
                    {
                        "type": "stage",
                        "stage": "cache_lookup",
                        "detail": {
                            "cache_hit": detail.get("cache_hit", False),
                            "source": detail.get("source"),
                        },
                        "duration_ms": ms,
                    }
                )
            elif stage == "start":
                yield await _emit({"type": "start", "stage": "start", "request_id": rid})
            elif stage == "retrieving":
                yield await _emit(
                    {
                        "type": "stage",
                        "stage": "retrieving",
                        "detail": {"chunks": detail.get("chunks", 0)},
                        "duration_ms": ms,
                    }
                )
            elif stage == "reranking":
                yield await _emit({"type": "stage", "stage": "reranking", "duration_ms": ms})
            elif stage == "generating":
                yield await _emit({"type": "stage", "stage": "generating", "duration_ms": ms})
                if settings.demo_mode and detail.get("answer"):
                    answer = detail["answer"]
                    for i in range(0, len(answer), _TOKEN_CHUNK):
                        yield await _emit(
                            {"type": "token", "token": answer[i : i + _TOKEN_CHUNK], "demo": True}
                        )
                        await asyncio.sleep(0.005)
            elif stage == "grounding":
                yield await _emit(
                    {
                        "type": "stage",
                        "stage": "grounding",
                        "detail": {"status": detail.get("status")},
                        "duration_ms": ms,
                    }
                )
            elif stage == "citation_check":
                yield await _emit(
                    {
                        "type": "stage",
                        "stage": "citation_check",
                        "detail": {"citations": detail.get("citations", 0)},
                        "duration_ms": ms,
                    }
                )
            elif stage == "usage":
                yield await _emit(
                    {
                        "type": "usage",
                        "detail": {"llm_calls": detail.get("llm_calls", 0)},
                        "duration_ms": ms,
                    }
                )
            elif stage == "done":
                result = detail["result"]
                payload = QueryResponse(
                    answer=result.answer,
                    status=result.status,  # type: ignore[arg-type]  # service 层 str → schema Literal
                    citations=result.citations,
                    sources=result.sources,
                    grounding=result.grounding,
                    usage=result.usage,
                    latency=result.latency,
                    cache=result.cache,
                    request_id=result.request_id,
                    trace=result.trace,
                ).model_dump()
                payload["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 2)
                yield await _emit({"type": "done", **payload})

    return StreamingResponse(event_generator(), media_type="text/event-stream")
