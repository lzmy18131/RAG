"""API v1 路由包（query / documents / system）。"""

from __future__ import annotations

from fastapi import APIRouter

from src.api.routes_v1.documents import router as documents_router
from src.api.routes_v1.query import router as query_router
from src.api.routes_v1.system import router as system_router

v1_router = APIRouter()
v1_router.include_router(query_router)
v1_router.include_router(documents_router)
v1_router.include_router(system_router)

__all__ = ["v1_router"]
