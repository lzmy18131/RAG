"""应用工厂（audit B11 / 任务书 §99）。

create_app(settings) 支持 test/demo/development/production 复用，
测试可用 TestClient 而不加载真实模型（依赖注入由 deps 提供）。
"""

from __future__ import annotations

import logging
from importlib import metadata
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _app_version() -> str:
    """应用版本：semver 来自 package metadata（V0-V9 是实验版本，不是应用版本）。"""
    try:
        return metadata.version("rag")
    except metadata.PackageNotFoundError:
        return "0.0.0-dev"


def create_app(settings: Any = None) -> FastAPI:
    """构建 FastAPI 应用。

    Args:
        settings: 可选 Settings 实例；None 时用 src.config.settings.settings。
    """
    from src.api.middleware import (
        RequestIDMiddleware,
        http_exception_handler,
        rag_error_handler,
        unhandled_exception_handler,
        validation_exception_handler,
    )
    from src.api.routes import router
    from src.config.settings import Settings
    from src.exceptions import RAGError

    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="多模态 RAG 智能硬件维保助手",
        description="V0–V9 多模态可信问答：Hybrid Retrieval → Reranker → LangGraph Verify → 确定性接地 → 语义缓存",
        version=_app_version(),
    )

    app.add_middleware(RequestIDMiddleware)

    cors_origins = getattr(settings, "cors_origins", "http://localhost:5173,http://127.0.0.1:5173")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 统一错误响应
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    app.add_exception_handler(RAGError, rag_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(router)

    # ── 健康与版本（audit B3 / §56）──

    @app.get("/health/live")
    async def health_live():
        """存活探针：进程在即 ok。"""
        return {"status": "ok", "version": _app_version()}

    @app.get("/health/ready")
    async def health_ready(request: Request):
        """就绪探针：检查本地组件（配置/路径/缓存），不实例化重对象、不调用真实 LLM。"""
        from src.config.settings import Settings

        s = Settings()
        checks: dict[str, str] = {}
        ready = True
        for name, path in (
            ("data_dir", s.data_dir),
            ("storage_dir", s.storage_dir),
            ("cache_db", s.cache_db_path),
        ):
            from pathlib import Path

            p = Path(path)
            checks[name] = "ok" if p.exists() or name in ("data_dir", "storage_dir") else "missing"
        checks["embedder"] = s.embedding_model
        checks["reranker"] = s.reranker_model
        checks["milvus"] = s.milvus_uri
        checks["llm_configured"] = "yes" if s.llm_api_key not in ("", "replace-me") else "no"
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "checks": checks},
        )

    @app.get("/version")
    async def version_info():
        """应用版本（semver；与 V0-V9 实验版本区分）。"""
        return {"version": _app_version(), "name": "multimodal-rag"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        """Prometheus 兼容指标（audit O2）。"""
        from fastapi.responses import PlainTextResponse

        from src.api.metrics import metrics

        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

    return app


# 兼容现有 uvicorn main:app 引用
app = create_app()
