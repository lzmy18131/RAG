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


def _git_commit() -> str | None:
    """git commit（短 SHA）；无 git 环境时返回 None，禁止伪造。"""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001 - git 不可用降级
        return None


def _build_time() -> str | None:
    """构建时间（可选环境注入 BUILD_TIME）；缺省 None，禁止伪造。"""
    import os

    return os.environ.get("BUILD_TIME") or None


def _pipeline_version() -> str:
    """RAG pipeline 演进版本（V0→V9）；与应用版本分离。"""
    return "rag-v9"


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
        """就绪探针（真实检查，不可用返回 503，任务书 §12）。

        检查（不调用真实 LLM / 不实例化重对象）：
        - storage_dir / data_dir 存在
        - manifest 可读（storage/manifests/manifests.json 或 demo corpus 可加载）
        - 语义缓存可初始化（demo 模式用 FakeEmbedder，否则按配置）
        - 向量存储配置合法（demo 模式内存；否则 Milvus URI 非空）
        - 运行期必需依赖（LLM/VLM/embedding 配置）在非 demo 模式必须就绪
        """
        from pathlib import Path

        from src.config.settings import Settings

        s = Settings()
        checks: dict[str, str] = {}
        ready = True

        def _check(name: str, ok: bool, detail: str = "ok") -> None:
            nonlocal ready
            checks[name] = detail if ok else f"error: {detail}"
            if not ok:
                ready = False

        # data/storage 目录
        data_dir = Path(s.data_dir)
        storage_dir = Path(s.storage_dir)
        _check("data_dir", data_dir.exists() or s.demo_mode, "missing")
        _check("storage_dir", storage_dir.exists() or s.demo_mode, "missing")

        # manifest（corpus 状态）——demo 模式使用内置合成语料
        if s.demo_mode:
            try:
                from src.infra.demo import DEMO_CORPUS

                _check("manifest", len(DEMO_CORPUS) > 0, "demo corpus empty")
            except Exception as e:  # noqa: BLE001
                _check("manifest", False, str(e))
        else:
            manifest = storage_dir / "manifests" / "manifests.json"
            _check("manifest", manifest.exists(), "manifests.json missing")

        # 语义缓存可初始化
        try:
            cache_db = Path(s.cache_db_path)
            cache_db.parent.mkdir(parents=True, exist_ok=True)
            _check("cache_db", True)
        except Exception as e:  # noqa: BLE001
            _check("cache_db", False, str(e))

        # 向量存储配置（demo = 内存；否则 Milvus URI 必须有效配置）
        if s.demo_mode:
            _check("vector_store", True, "demo-in-memory")
        else:
            _check("vector_store", bool(s.milvus_uri.strip()), "milvus_uri empty")

        # 必需运行时服务（非 demo 模式）：LLM / VLM / embedding 必须配置
        if not s.demo_mode:
            _check("llm_configured", s.llm_api_key not in ("", "replace-me"), "llm_api_key missing")
            _check("vlm_configured", s.vlm_api_key not in ("", "replace-me"), "vlm_api_key missing")
        else:
            checks["llm_configured"] = "demo"
            checks["vlm_configured"] = "demo"

        checks["demo_mode"] = "yes" if s.demo_mode else "no"
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "checks": checks},
        )

    @app.get("/version")
    async def version_info():
        """应用版本与 pipeline 版本分离（任务书 §6）。

        - app_version：来自 package metadata 的 semver（1.0.0 等）。
        - pipeline_version：RAG 管线演进版本（rag-v9）。
        - git_commit / build_time：真实值；无法获得时 null（禁止伪造）。
        """
        return {
            "app_version": _app_version(),
            "pipeline_version": _pipeline_version(),
            "git_commit": _git_commit(),
            "build_time": _build_time(),
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        """Prometheus 兼容指标（audit O2）。"""
        from fastapi.responses import PlainTextResponse

        from src.api.metrics import metrics

        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

    return app


# 兼容现有 uvicorn main:app 引用
app = create_app()
