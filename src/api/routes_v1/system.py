"""API v1 — system 路由（状态 / 版本 / 健康检查由 app.py 提供全局端点）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.api.deps import get_settings
from src.api.schemas import SystemStatusResponse

router = APIRouter(prefix="/api/v1")


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status_v1(request: Request):
    """系统状态（不含 secret）：embedding/reranker/向量存储/网关/缓存/corpus 版本。"""
    from src.api.deps import get_semantic_cache
    from src.infra.demo import DEMO_COLLECTION
    from src.infra.gateway import get_gateway

    settings = get_settings()
    cache = get_semantic_cache() if settings.cache_enabled else None
    gateway = get_gateway()

    corpus_version = None
    if settings.demo_mode:
        corpus_version = DEMO_COLLECTION
    else:
        try:
            from src.api.routes import _corpus_version

            corpus_version = _corpus_version(settings)
        except Exception:  # noqa: BLE001
            pass

    return SystemStatusResponse(
        demo_mode=settings.demo_mode,
        embedding_model="demo-fake" if settings.demo_mode else settings.embedding_model,
        reranker_model="demo-fake" if settings.demo_mode else settings.reranker_model,
        vector_store="demo-in-memory" if settings.demo_mode else settings.milvus_uri,
        corpus_version=corpus_version,
        cache=cache.stats() if cache else None,
        gateway=gateway.state_dump() if gateway else None,
        grounding={
            "verifier_mode": settings.verifier_mode,
            "scorer": settings.grounding_scorer,
            "scorer_floor": settings.grounding_scorer_floor,
            "min_support_ratio": settings.grounding_min_support_ratio,
        },
        llm_configured=settings.llm_api_key not in ("", "replace-me"),
        vlm_configured=settings.vlm_api_key not in ("", "replace-me"),
    )
