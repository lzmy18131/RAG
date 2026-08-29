# RESUME_METRICS（当前 commit 真实指标）

> ⚠️ 最新数字以 **docs/CURRENT_RESUME_METRICS.md** 为准（记录 commit 与 run_id）。
> 本文件保留为入口摘要；历史 V0-V9 数字见 README「Historical Results」（NOT VERIFIED AFTER REFACTOR）。

## 当前 HEAD 实测（Final Pass）

| 指标 | 数值 |
|---|---|
| git commit | `cc7bb87`（Final Pass 交付 HEAD） |
| Backend tests（离线子集） | **273 passed** |
| Coverage（branch） | **77%**（gate=70；基线 68%） |
| mypy | **0 errors**（54 files） |
| ruff | ✅ check + format |
| Frontend Vitest / Playwright E2E | **7 / 7**（Demo Mode） |
| Demo retrieval Recall@5 / MRR / nDCG@5 | **0.9167 / 0.9167 / 0.8792**（run demo_retrieval_v1） |
| Cache exact hits / false-hit | **12/12 / 0.0** |
| 关键模块覆盖 | retrieval 86~89% · grounding 92% · cache 94% · gateway 84% |
| Docker 本地 | NOT RUN（无 Docker） |
| 真实模型 benchmark（BGE/Milvus/LLM） | NOT RUN（需 GPU + 模型权重 + API key） |

## 能力清单（代码 + 测试支撑）

- Hybrid Retrieval（BGE-M3 + BM25 + RRF + Cross-Encoder Rerank，参数配置化）
- 确定性 Grounding + Citation Validator + Cite-or-Abstain（relevance ≠ entailment 诚实声明）
- Semantic Cache（corpus_version + schema_version 防 stale；false-hit 度量）
- Incremental Index（SHA256 manifest 原子写；Milvus Lite 无事务限制文档化）
- LLM Gateway（retry / circuit breaker / failover）
- v1 API + SSE streaming + cancellation（CancelledError 不包装 500）
- Evaluation：统一指标 / Bootstrap CI / McNemar / 12 类 Failure Taxonomy / Experiment Registry
- Observability：request_id / Prometheus /metrics / /health/ready 真实 503 / /version app+pipeline 分离
- Demo Mode：无 API key / GPU / 模型下载完整体验（合成语料 + 确定性模型，复用真实管线代码）
- CI：mypy / coverage 真 gate；E2E（Playwright Demo）；Docker build

## NOT RUN（如实标注）

| 项 | 原因 |
|---|---|
| RAGAS full（golden_100） | 需真实 LLM API |
| Retrieval eval（BGE/Milvus） | 需模型权重 + Milvus 集合 |
| Docker compose 启动 | 本环境无 Docker |
| 在线 evals | 需 API key（RUN_ONLINE_EVALS 门控） |
