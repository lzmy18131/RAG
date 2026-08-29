# RAG Final Engineering Report

> RAG Final Pass（收尾）· 数字实测于 commit `1a388cd`（CI 全绿；后续 docs 同步 commit 不改数字）· 功能交付 `df7ebdb` · 仓库 lzmy18131/RAG
> 所有数字来自当前 commit 真实执行；NOT RUN 已注明。当前指标见 `docs/evaluation/CURRENT_RESUME_METRICS.md`。

## Final Architecture

```
React 19 + Vite (frontend/) ──> FastAPI (main.py → src/api/app.py create_app)
  ├─ /api/v1/query + /query/stream (SSE)          ← v1 契约（Final Pass）
  ├─ /api/v1/documents, /api/v1/system/status
  ├─ /query /documents /system /versions (legacy, 兼容)
  ├─ /health/live /health/ready(503) /version(app/pipeline 分离) /metrics
  ├─ RequestID 中间件 + 统一错误 envelope
  └─ services/rag_service.py（分阶段计时 + run_stages 生成器）
        ├─ SemanticCache (exact + cosine; corpus_version + schema_version salt)
        ├─ RerankedRetriever (Hybrid: Dense+BM25 → RRF → Cross-Encoder rerank)
        ├─ Generator (LLM, Prompt Registry + <untrusted> 注入防御)
        ├─ GroundingVerifier (句级 Cross-Encoder 确定性接地)
        └─ Citation Validator（引用由系统计算）
```

## RAG Pipeline（当前实现）

- **Ingestion**：PDF → 文本/表格/图片(VLM caption) → chunk → embed → Milvus/BM25；SHA256 manifest 增量（原子写）。
- **Retrieval**：BGE-M3 Dense（top-20）+ BM25 jieba（top-20）→ RRF（k=60）→ Cross-Encoder Rerank → top-5；参数配置化。
- **Reranking**：candidate_top_k=20 / final_top_k=5；rerank 失败降级 hybrid（degrade_reason 标注）。
- **Grounding**：答案拆句 → CrossEncoderScorer 逐句核对 → support_ratio / unsupported_claims；阈值由校准脚本决定。
- **Citation**：引用（chunk_id/source/page/excerpt/各通道分数）由系统从真实检索结果计算。
- **Abstain**：相关性阈值（rerank_score ≥ 0.05）不达标 → refused；接地不支撑 → 拒答。
- **Cache**：exact SHA256 + semantic cosine；key = query + doc_filter + corpus_version + schema_version。
- **Incremental Index**：per-file 容错 + manifest 原子写；Milvus Lite 无事务限制已文档化。

## Evaluation

- 统一指标：Recall@K / HitRate@K / Precision@K / MRR / nDCG@K（K∈{1,3,5,10,20}）。
- 统计检验：Bootstrap 95% CI + McNemar（src/eval/stats.py）。
- Failure Taxonomy：12 类（RETRIEVAL_MISS / RERANKER_REGRESSION / CACHE_FALSE_HIT / GENERATION_HALLUCINATION / …）。
- Experiment Registry：runs/<run_id>/{config,metadata,metrics,failures,report}；git_commit/dataset_hash/corpus_version 入 metadata。
- Ablation：scripts/ablation.py（Dense/Hybrid/Hybrid+Rerank 统一指标表）。
- 防 leakage：calibration/test split（golden_v1 cal20/test80）。

## Current Verified Benchmark

| 项 | 值 | run |
|---|---:|---|
| Demo retrieval Recall@5 / MRR / nDCG@5 | 0.9167 / 0.9167 / 0.8792 | demo_retrieval_v1 |
| Cache exact hits / false-hit | 12/12 / 0.0 | demo_retrieval_v1 |
| RAGAS / 真实模型 benchmark | NOT RUN（需 GPU+模型+API） | — |

## Reliability

- LLM Gateway：retry（指数退避）/ circuit breaker / provider failover / timeout；provider 失败计指标。
- 取消：SSE CancelledError 传播不包装 500；同步管线 asyncio.to_thread。
- /health/ready 真实检查（storage/manifest/cache/vector store/LLM+VLM 配置），缺失 503。

## Observability

- request_id 全链路；/metrics（Prometheus）：http/rag 分阶段 latency、llm 调用/失败/重试、failover、circuit open、cache hit/miss、grounding rejections、tokens（不把 query/request_id 当 label）。
- /version：app_version（package metadata semver）/ pipeline_version（rag-v9）/ git_commit / build_time。

## Backend / Frontend / Testing / CI / Docker

- Backend：FastAPI 工厂、v1 路由拆分（query/documents/system）、services 层、统一错误。
- Frontend：Q&A（v1 契约 + Evidence Panel + 引用展开 + DEMO 横幅）、Knowledge Base、Experiments（读真实 runs/）、System Status；Vitest 7 + Playwright 7 全绿。
- CI：backend（ruff/format/**mypy**/pytest/**coverage**/demo eval/pip-audit）+ frontend（lint/typecheck/**vitest**/build/npm audit）+ **E2E（Playwright Demo）** + Docker build + full-eval（workflow_dispatch）。
- Docker：真 multi-stage（builder+runtime）、非 root、HF_HOME=/models volume。

## Security

- 上传：uuid 文件名、MAX_UPLOAD_MB / MAX_PDF_PAGES 配置化、PDF 校验。
- 注入防御：检索内容 <untrusted> 边界 + 系统级指令（prompts/）。
- 错误不泄漏堆栈；metrics 无高基数 label；System Status 不含 secret。

## Verification（当前 commit）

| 命令 | 结果 |
|---|---|
| ruff check / format | ✅ |
| mypy src | ✅ 0 errors（54 files） |
| pytest（CI 子集，-k 排除 artifact/GPU 依赖） | ✅ **226 passed / 89 deselected** |
| pytest --cov（branch-adjusted TOTAL） | ✅ **72.46%**（CI 子集；gate 70）· 本地全量 77.8% |
| python scripts/demo_retrieval_eval.py | ✅ Recall@5=0.9167（run demo_retrieval_v1） |
| python scripts/build_evals_datasets.py | ✅ golden_v1(100)/extended_v1(123) |
| frontend lint/typecheck/vitest/build | ✅ / ✅ / 7 / ✅ |
| npx playwright test | ✅ **7/7**（Demo Mode，本地全新缓存 + CI） |
| docker compose 本地 | NOT RUN（无 Docker；镜像在 CI 构建验证） |

> 本地全量 pytest = 294 passed / 21 failed；21 个失败均为 artifact/模型/Milvus 依赖用例（需 storage 产物/GPU/真实集合），CI 已用 `-k` 显式排除（见 `docs/evaluation/CURRENT_RESUME_METRICS.md`）。

## Known Limitations

见 README「Known Limitations」：数据集规模有限、grounding 是 relevance 非 entailment、VLM caption 依赖、Milvus Lite 单进程、语义缓存近似、未做互联网规模压测、Demo 为 deterministic fake、未接入 Query Rewrite/Adaptive/Native Multimodal（无 benchmark 收益不加）。

## Resume Highlights

1. **Hybrid Retrieval Engineering**：BGE-M3 + BM25 + RRF + Cross-Encoder Rerank 二阶段管线，参数配置化，基于固定 Golden Dataset 控制变量实验量化 Recall@K/MRR/nDCG 与延迟 tradeoff。
2. **Grounding / Citation / Abstain**：句级确定性接地 + 系统计算引用 + cite-or-abstain，诚实声明 relevance ≠ entailment。
3. **Evaluation / Experimentation**：统一指标、Bootstrap CI、McNemar、12 类 Failure Taxonomy、Experiment Registry（runs/ 可追溯）。
4. **Cache / Index / Reliability**：corpus_version 感知语义缓存、增量索引原子 manifest、LLM Gateway 熔断/failover、取消不包装 500。
5. **Application Engineering**：FastAPI + SSE + React（Evidence Panel/Citation UI）、Vitest + Playwright E2E、Docker、CI（mypy/coverage 真 gate）、Prometheus、Demo Mode 无 Key/GPU 可跑。
