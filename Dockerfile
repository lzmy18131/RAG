# 后端镜像（真正 multi-stage）
# Stage 1: build —— 安装依赖（含 wheel 构建）
# Stage 2: runtime —— 最小运行镜像，非 root 用户，模型权重缓存于 /models（HF_HOME）
# Milvus Lite 单进程：生产仅 1 个 backend 容器

# ── Stage 1: builder ──
FROM python:3.12-slim AS builder
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
WORKDIR /build
COPY requirements.txt pyproject.toml ./
# 安装依赖到独立目录（不运行应用，避免每层重复）
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ──
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PORT=8000 \
    # 模型权重缓存目录：非 root 用户可写（/models volume）
    HF_HOME=/models \
    TRANSFORMERS_CACHE=/models/hub \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence-transformers

WORKDIR /app

# 从 builder 拷贝依赖
COPY --from=builder /install /usr/local

# 拷贝应用源码与配置
COPY src ./src
COPY main.py pyproject.toml ./
COPY data ./data
COPY configs ./configs

# 非 root 用户 + 可写目录（storage / runs / models）
RUN useradd --create-home --uid 10001 rag \
    && mkdir -p /app/storage /app/runs /models \
    && chown -R rag:rag /app /models
USER rag

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)" || exit 1

# Milvus Lite 单进程：--workers 1（不可多 worker）
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
