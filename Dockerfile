# -RAG- 后端镜像（multi-stage, 非 root）
# 默认不下载模型权重（首次运行由 HF cache volume 下载，见 docker-compose.yml）
# Milvus Lite 单进程：生产仅 1 个 backend 容器

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 PORT=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY main.py pyproject.toml ./
COPY data ./data

# 非 root
RUN useradd --create-home --uid 10001 rag
RUN mkdir -p /app/storage /app/runs && chown -R rag:rag /app
USER rag

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
