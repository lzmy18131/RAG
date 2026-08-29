"""FastAPI 入口（薄）。uvicorn main:app 启动。

NOTE: Milvus Lite 要求 SINGLE-PROCESS 访问——不要用多 worker 启动。
"""

from __future__ import annotations

from src.api.app import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
