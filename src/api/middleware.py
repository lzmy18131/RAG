"""请求中间件与统一错误响应（audit B1-B2 / 任务书 §53-55）。

- RequestIDMiddleware：X-Request-ID 透传/生成 + ContextVar 关联。
- 统一错误 envelope：{"error": {"code", "message", "request_id"}}，绝不返回 stack trace。
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.exceptions import RAGError

logger = logging.getLogger(__name__)

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id() -> str:
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求注入 X-Request-ID 并建立日志关联；同时记录 HTTP 指标（audit O2）。"""

    async def dispatch(self, request: Request, call_next):
        from src.api.metrics import inc_http_request

        client_id = request.headers.get("X-Request-ID", "")
        rid = client_id if client_id and len(client_id) <= 64 else uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_var.set(rid)
        status = 500
        response = None
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            request_id_var.reset(token)
            inc_http_request(request.method, _normalize_path(request.url.path), status)
            if response is not None:
                response.headers["X-Request-ID"] = rid


def _normalize_path(path: str) -> str:
    """路径归一化：长动态段折叠，避免指标高基数。"""
    parts = path.split("/")
    return "/".join("{id}" if len(p) >= 16 and p.isalnum() else p for p in parts)


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": get_request_id()}},
    )


async def rag_error_handler(request: Request, exc: RAGError) -> JSONResponse:
    """领域异常 → HTTP 错误（不泄漏内部细节）。"""
    status_map = {
        "CONFIGURATION_ERROR": 500,
        "DOCUMENT_PARSE_ERROR": 422,
        "INDEXING_ERROR": 500,
        "RETRIEVAL_ERROR": 503,
        "RERANK_ERROR": 503,
        "MODEL_PROVIDER_ERROR": 503,
        "GROUNDING_ERROR": 500,
        "CACHE_ERROR": 500,
    }
    status = status_map.get(exc.code, 500)
    logger.warning("领域异常: code=%s msg=%s", exc.code, exc.message)
    return error_response(exc.code, exc.message, status)


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """FastAPI HTTPException → error envelope。"""
    code = _status_code_name(exc.status_code)
    message = exc.detail if isinstance(exc.detail, str) else "请求错误"
    return error_response(code, message, exc.status_code)


async def validation_exception_handler(request: Request, exc) -> JSONResponse:
    errors = exc.errors() if hasattr(exc, "errors") else []
    first = errors[0] if errors else {}
    loc = ".".join(str(x) for x in first.get("loc", []))
    return error_response("VALIDATION_ERROR", f"参数校验失败: {loc}", 422)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理异常: %s %s", request.method, request.url.path)
    return error_response("INTERNAL_ERROR", "服务器内部错误", 500)


def _status_code_name(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, f"HTTP_{status_code}")
