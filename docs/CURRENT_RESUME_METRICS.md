# CURRENT_RESUME_METRICS（只记录当前 commit / 当前 run）

> 原则：只收录当前 commit 真实执行数字；NOT RUN 如实标注；历史 V0-V9 不在本表。

## 当前 commit

- git commit：`cc7bb87`（Final Pass 交付 HEAD；此前 b66936a 为基线）
- 分支：main · origin = https://github.com/lzmy18131/RAG

## 当前 Verified Run

- run_id：`demo_retrieval_v1`（runs/demo_retrieval_v1/）
- dataset：demo_golden_v1（12 条人工核验查询，合成硬件手册语料 20 chunks）
- 管线：Hybrid(BGE-like dense + BM25) → RRF → Cross-Encoder-like rerank（demo 确定性模型，复用真实代码路径）
- 说明：Demo Mode 基准（CI 离线回归用）；真实 BGE/Milvus/LLM benchmark 需 GPU+模型+API → NOT RUN

## Backend

| 指标 | 值 |
|---|---|
| Backend tests（离线子集） | **273 passed / 42 deselected（GPU 用例）** |
| Overall coverage（branch） | **77%**（gate=70；基线 68%） |
| 关键模块覆盖 | hybrid_retriever 89% · reranked_retriever 86% · retriever 81% · grounding 92% · semantic_cache 94% · gateway 84% · retrieval_metrics 100% |
| mypy | **0 errors**（54 files） |
| ruff check / format | ✅ |

## Eval / Benchmark（当前 run）

| 指标 | 值 |
|---|---|
| Demo retrieval Recall@5 | **0.9167** |
| Demo retrieval MRR | **0.9167** |
| Demo retrieval nDCG@5 | **0.8792** |
| Cache exact hits | **12/12** |
| Cache false-hit rate | **0.0** |
| RAGAS full（golden_100，真实模型） | NOT RUN（需 LLM/GPU） |
| Retrieval eval（真实 BGE/Milvus） | NOT RUN（需模型权重+Milvus 集合） |

## Frontend

| 指标 | 值 |
|---|---|
| Vitest+RTL | **7 passed** |
| lint / typecheck / build | ✅ / ✅ / ✅ |
| Playwright E2E（Demo Mode） | **7/7 passed**（本地实测） |
| CI E2E | 待 push 后验证 |

## CI / Docker

| 项 | 值 |
|---|---|
| GitHub Actions | 待 push 后验证（backend/frontend/e2e/docker jobs） |
| Docker 本地 | NOT RUN（本环境无 Docker） |

## 项目核心（当前 commit）

- Hybrid Retrieval（BGE-M3 + BM25 + RRF + Cross-Encoder Rerank）
- 确定性 Grounding + Citation Validator + Cite-or-Abstain
- Semantic Cache（corpus_version + schema_version 防 stale）
- Incremental Index（SHA256 manifest 原子写）
- LLM Gateway（retry / circuit breaker / failover）
- v1 API + SSE streaming + cancellation；Evidence Panel（developer）
- Evaluation：统一指标 / Bootstrap CI / McNemar / Failure Taxonomy / Experiment Registry
- Demo Mode：无 API key / GPU / 模型下载完整体验
