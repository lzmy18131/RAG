# CURRENT_RESUME_METRICS（只记录当前 commit / 当前 run）

> 原则：只收录当前 commit 真实执行数字；NOT RUN 如实标注；历史 V0-V9 不在本表（见 `docs/history/V0_V9_EXPERIMENTS.md`）。

## 当前 commit

- 数字实测 commit：`1a388cd`（该 commit CI 全绿；后续 docs 同步 commit 不改变任何数字）
- 功能交付：`df7ebdb` · E2E 冷启动修复 `f12eb75` · Demo 全链路 `cc7bb87` · 基线 `b66936a`
- 分支：main · origin = https://github.com/lzmy18131/RAG

## 当前 Verified Run

- run_id：`demo_retrieval_v1`（runs/demo_retrieval_v1/）
- dataset：demo_golden_v1（12 条人工核验查询，合成硬件手册语料 20 chunks）
- 管线：Hybrid(BGE-like dense + BM25) → RRF → Cross-Encoder-like rerank（demo 确定性模型，复用真实代码路径）
- 说明：Demo Mode 基准（CI 离线回归用）；真实 BGE/Milvus/LLM benchmark 需 GPU+模型+API → NOT RUN

## Backend（当前 commit 实测）

| 指标 | 值 |
|---|---|
| Backend tests（CI 子集，-k 排除 artifact/GPU 依赖） | **226 passed / 89 deselected**（CI 全绿） |
| 本地全量 pytest（本机无 storage 产物/Milvus/GPU） | **294 passed / 21 failed**（21 个均为 artifact/模型依赖用例，见下） |
| Overall coverage（branch-adjusted TOTAL） | **CI 子集 72.46%** · 本地全量 77.8%（statements 80.3% / branches 66.9%）；gate=70，基线 68% |
| 关键模块覆盖 | hybrid_retriever 89% · reranked_retriever 86% · retriever 81% · grounding 92% · semantic_cache 94% · gateway 84% · retrieval_metrics 100% |
| mypy | **0 errors**（54 files） |
| ruff check / format | ✅ |

> 21 个本地失败用例构成：`test_phase3`（5，需 Milvus v0/v1 集合）、`test_phase4`（5，需真实集合）、`test_phase5`（4，需 reranker 权重）、`test_phase7_integration`（6，需真实 Milvus 增量）、`test_rag::test_milvus_collection_available`（1，需真实 Milvus）。CI 通过 `-k` 显式排除，非回归。

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
| Playwright E2E（Demo Mode） | **7/7 passed**（本地全新缓存 + CI 实测） |

## CI / Docker

| 项 | 值 |
|---|---|
| GitHub Actions | **全部 green**：Backend / Frontend / E2E / Docker build；full-eval 仅 workflow_dispatch（跳过） |
| Docker 本地 | NOT RUN（本环境无 Docker，Docker 镜像在 CI 构建验证） |

## 项目核心（当前 commit）

- Hybrid Retrieval（BGE-M3 + BM25 + RRF + Cross-Encoder Rerank）
- 确定性 Grounding（默认 Cross-Encoder scorer；relevance ≠ entailment）+ Citation Validator + Cite-or-Abstain
- Semantic Cache（exact SHA256 + embedding-cosine 语义命中；key 含 doc_filter/corpus_version/schema:v1 防 stale）
- Incremental Index（SHA256 manifest 原子写；避免对未变更文档重复索引）
- LLM Gateway（retry / circuit breaker / failover）
- v1 API + SSE streaming + cancellation；Evidence Panel（developer）
- Evaluation：统一指标 / Bootstrap CI / McNemar / Failure Taxonomy / Experiment Registry
- Demo Mode：无 API key / GPU / 模型下载完整体验
