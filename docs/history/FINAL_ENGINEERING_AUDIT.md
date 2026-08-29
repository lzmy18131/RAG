<!-- =====================================================================
  HISTORICAL DOCUMENT — 历史记录，不是当前工程状态。
  当前唯一事实源：docs/engineering/FINAL_ENGINEERING_REPORT.md
  （工程报告）与 docs/evaluation/CURRENT_RESUME_METRICS.md（指标）。
  文档导航：docs/README.md。
===================================================================== -->

> 本文件是 Final Pass 起点（HEAD b66936a）的审计；所列 P0 问题在后续提交中已全部修复。

# FINAL_ENGINEERING_AUDIT（RAG Final Pass · 以当前 HEAD 为唯一事实来源）

> 生成时间：2026-08（Final Pass 起点）
> HEAD：`b66936a`（clean tree）· origin = https://github.com/lzmy18131/RAG
> 原则：所有结论来自真实执行；未运行的标注 NOT RUN，禁止猜测。

## Current Architecture

```
React 19 + Vite (frontend/, 无单测/无 E2E)
   └─> FastAPI (main.py -> src/api/app.py create_app)
         ├─ /health /health/live /health/ready /version /metrics
         ├─ /query /documents/ingest /documents /system /versions /evaluate
         ├─ /experiments /experiments/{id} /final_eval
         ├─ RequestID 中间件 + 统一错误 envelope
         └─ deps.py: lru_cache 单例（真实加载 BGE-M3 / Reranker / Milvus Lite）
               └─ VerifiedQA (src/workflow/verified_qa.py)
                    ├─ RerankedRetriever (hybrid BGE-M3+BM25 -> RRF -> Cross-Encoder)
                    ├─ generate_answer (LLM, src/generation/generator.py)
                    └─ GroundingVerifier (CrossEncoderScorer 确定性句级接地)
               └─ SemanticCache (exact SHA256 + BGE-M3 cosine, SQLite, corpus_version salt)
               └─ IncrementalIndexer (manifest SHA256 + Milvus)
```

- 源文件：`src/{api,config,eval,generation,infra,ingestion,prompts,retrieval,workflow}`
- 评测数据集：`evals/datasets/{golden_v1,extended_v1}`（版本化 + dataset_hash + cal/test split）
- 实验产物：`storage/runs/*`（历史 artifact）；`runs/`（registry 目标目录，当前为空 → **双目录不一致**）
- 文档：docs/ 19 个文件（PROJECT_CHARTER/ARCHITECTURE/…/phases）

## Existing Strengths（真实存在且测试支撑）

- **Hybrid Retrieval**：BGE-M3 dense + BM25 (jieba/rank_bm25) + RRF + Cross-Encoder rerank，参数配置化（settings.retrieval_*）
- **确定性 Grounding**：句级拆分 + Cross-Encoder 打分 + 阈值校准 + 拒答/重试（src/workflow/grounding.py，91% 覆盖）
- **Citation Validator**：确定性三态校验（tests/test_citation.py）
- **Experiment Registry**：runs/<run_id>/{config,metadata,metrics,failures}（src/eval/registry.py）
- **统一评测指标**：Recall@K/HitRate/MRR/nDCG + Bootstrap CI + McNemar（src/eval/*）
- **LLM Gateway**：retry/熔断/failover/超时（src/infra/gateway.py，83% 覆盖）
- **Semantic Cache**：corpus_version 失效 + doc_filter 隔离（94% 覆盖）
- **增量索引**：SHA256 manifest 原子写（src/ingestion/manifest.py）
- **Prompt Registry + 注入防御**（src/prompts/）
- 上传安全：uuid 文件名 + 50MB 限流 + PDF 校验
- 231 个离线测试全绿；ruff check/format 全绿

## Current Test Baseline（真实执行）

| 项 | 结果 |
|---|---|
| `pytest tests/ -k "not phase3/4/5/7_integration/milvus_collection"` | **231 passed / 42 deselected**（99.7s） |
| `pytest tests/`（全量 273） | **FAILS + 挂起**：42 个 GPU/模型用例真实加载 BGE 模型（本环境无模型缓存、无网络下载 → 挂起超时） |
| ruff check / format | ✅ All checks passed（104 文件） |

## Current Coverage（真实执行，branch）

```
pytest tests/ --cov=src --cov-branch
TOTAL   2453 statements   68%  (branch)
```

关键模块（任务要求 85~90%）当前：

| 模块 | 覆盖 | 原因 |
|---|---|---|
| retrieval/hybrid_retriever.py | **14%** | 需真实 Milvus+BGE；离线测试未覆盖 |
| retrieval/reranked_retriever.py | **0%** | 同上 |
| retrieval/retriever.py | **27%** | 同上 |
| infra/reranker.py | **0%** | 需模型权重 |
| infra/vlm_client.py | **0%** | 需 API |
| infra/milvus_client.py | **0%** | 需 Milvus 集合 |
| eval/metrics.py | **0%** | LLM-as-judge 路径未离线测 |
| ingestion/incremental.py | **39%** | 需 embedder |
| retrieval/bm25.py | **40%** | 部分需持久化索引 |
| infra/embedder.py | **28%** | 需模型权重 |
| workflow/grounding.py | **91%** ✅ | 有离线测试 |
| infra/gateway.py | **83%** ✅ | 有离线测试 |
| infra/semantic_cache.py | **94%** ✅ | 有离线测试 |

## Current Eval Baseline

- `scripts/build_evals_datasets.py`：✅ 离线可跑 → golden_v1(100, hash=253762c4, cal20/test80) + extended_v1(123, hash=131cf886)
- retrieval/generation/cache/grounding 全量 benchmark：**NOT RUN**（需 BGE 模型权重 + Milvus 集合 + LLM/VLM API；本环境无模型缓存）
- `scripts/ablation.py`：**NOT RUN**（runs/ 无产物）

## Current Benchmark（README V0-V9 数字）

- **全部为历史数字**（来自旧机器 storage 产物 / README），**重构后未重跑** → 一律标注 NOT VERIFIED AFTER REFACTOR
- **P0 问题**：`GET /versions`（src/api/routes.py）对 v6/v8/v9 **硬编码历史 benchmark 作为 fallback**（`"answered": 95, "v3_mrr": 0.8916, "overall_hit_rate": 0.6667`…），docstring 明言“README values as fallback so the page renders” → 违反任务书 §5（无 artifact 必须返回 available:false）

## P0 Problems（必须修复）

| # | 问题 | 位置 | 修复方向 |
|---|---|---|---|
| P0-1 | `/versions` 硬编码历史 benchmark fallback | src/api/routes.py:309-428 | 无 artifact → `{"available": false, "source": "none", ...}`；历史数字仅 docs |
| P0-2 | **DEMO_MODE 声称存在但完全未实现**：Settings 无 demo_mode；无 StubLLM/StubVLM/DemoRetriever | .env.example / src/config/settings.py / src/api/deps.py | 实现 fake 全链路（见 Phase 3） |
| P0-3 | `/health/ready` 永远 200（ready 恒 True） | src/api/app.py:health_ready | 真实检查 storage/manifest/cache/向量配置/网关；不可用 → 503 |
| P0-4 | `/version` 无 app/pipeline 分离、无 git_commit/build_time | src/api/app.py:version_info | `{app_version, pipeline_version, git_commit, build_time}` |
| P0-5 | pyproject **非真实 package**（无 [project]）→ `pip install -e .` 不可用、`metadata.version("rag")` 返回 0.0.0-dev | pyproject.toml | 完整 [project] + setuptools 配置 |
| P0-6 | **typecheck 假 gate**：`mypy ... 2>/dev/null \|\| echo "typecheck: 见 roadmap"`；CI 无 typecheck | Makefile / .github/workflows/ci.yml | 真 mypy gate（CI 安装 mypy，fail → job fail） |
| P0-7 | **无 coverage gate**：pytest-cov 未装、CI 无 cov | CI / pyproject | `--cov-fail-under` + critical 模块门禁 |
| P0-8 | Dockerfile 注释声称 multi-stage 但**只有一个 FROM**；`USER rag` + HF volume 挂 `/root/.cache/huggingface`（权限矛盾） | Dockerfile / docker-compose.yml | 真 multi-stage + `HF_HOME=/models` + volume `rag-models:/models`（rag 用户可写） |
| P0-9 | 前端**无单元测试、无 typecheck 脚本、无 Playwright E2E** | frontend/package.json | Vitest+RTL + `typecheck` script + Playwright（Demo Mode） |
| P0-10 | CI eval 步骤 `|| echo "NOT RUN"` 假绿；full-eval 同样 | ci.yml | 去掉假绿；PR=deterministic，main/manual=full，workflow_dispatch=online |

## P1 Problems

| # | 问题 | 位置 | 修复方向 |
|---|---|---|---|
| P1-1 | Settings 缺 APP_ENV/APP_HOST/APP_PORT/DEMO_MODE/CORS_ORIGINS/LOG_FORMAT/MAX_UPLOAD_MB/MAX_PDF_PAGES/MAX_CONCURRENT_QUERIES/MAX_CONCURRENT_RERANKS；.env.example 与代码漂移 | settings.py / .env.example | 补齐并统一 |
| P1-2 | routes.py 670 行单文件；无 /api/v1 前缀；无 SSE streaming；无 CancelledError 处理 | src/api/routes.py | 拆分 routes/{query,documents,system,experiments}.py + services 层 + /api/v1/query/stream |
| P1-3 | QueryResponse 缺 citations/grounding 状态/usage/latency 分阶段/cache 明细/request_id | routes.py | 新 v1 契约 |
| P1-4 | runs/（registry 写）与 storage/runs/（API 读）**双目录不一致** | registry.py / routes.py | 统一：runs/ 为 evaluation artifacts（registry 与 API 都读 runs/）；storage/ 仅 runtime state；迁移现有 storage/runs → runs/ |
| P1-5 | grounding README 仍写“BGE-M3 余弦”旧描述（默认 scorer 已是 reranker）；Multimodal 描述可能被误读为 native image embedding | README | 改为 “VLM-assisted caption-based multimodal retrieval” |
| P1-6 | 上传配置硬编码（50MB、无页数限制） | routes.py:125 | MAX_UPLOAD_MB / MAX_PDF_PAGES 配置化 |
| P1-7 | 结构化日志：LOG_FORMAT 未进 Settings；无 run_id/stage/duration 字段约定 | 无 logging 模块 | 统一 logging（dev text / prod JSON） |
| P1-8 | `/health` 返回 version=V9（实验版本当应用版本） | routes.py:94 | 用 app semver |
| P1-9 | storage/phase0_smoke_result.json 提交在 git | git | 移出版本控制 |

## P2 Experiments（可选，不进 default）

- Query Rewrite（必须 benchmark 证明收益，默认不加）
- Adaptive Retrieval（低置信 → candidate expansion；需 reranker score 证据）
- Native multimodal embedding（对比 caption pipeline：Image Recall/MRR/VRAM/Index size）
- Chunking 对比（fixed vs structure-aware）
- 复杂解析器（MinerU/Docling）——需 complex-PDF benchmark 证明收益
- Reranker batch（candidate_k∈{5,10,15,20} Pareto）

## Documentation Inconsistencies

- README “V6 可复现：引用由 BGE-M3 余弦‘计算’” vs 实际默认 `GROUNDING_SCORER=reranker`
- README “多模态检索：文本、表格、图片统一进入同一个向量空间” 未明确是 caption-based
- README 核心指标表（V0-V4/V6/V8/V9）全部为历史值，未标注 NOT VERIFIED AFTER REFACTOR
- `.env.example` 声称 `DEMO_MODE=true → StubLLM/StubVLM`，代码无实现
- Dockerfile 注释 “multi-stage” 与实际不符

## Resume Risk Items

1. **历史 benchmark 当最新指标展示**（/versions fallback + README）→ 违反 Integrity，必须修
2. Demo Mode 承诺未兑现 → 招聘者运行 `DEMO_MODE=true docker compose up` 直接失败
3. typecheck/coverage 假 gate → “production-style” 声明不成立
4. 前端无任何测试 → “Application Engineering” 缺证据

## Definition of Done

- [ ] P0-1~P0-10 全部修复并有测试
- [ ] P1-1~P1-5 完成（Settings 对齐 / v1 API+SSE / 契约 / runs 统一 / README 精准）
- [ ] Demo Mode 真跑通：`DEMO_MODE=true` 无 Key/GPU 完整 query→stream→citation→grounding→cache
- [ ] 关键模块覆盖（fake 支撑）：retrieval/reranker/vlm/milvus/eval ≥ 85%
- [ ] 前端：Vitest 测试 + Playwright E2E（Demo）+ Evidence Panel
- [ ] CI：typecheck/coverage 真 gate；无 `|| echo` 假绿
- [ ] README 重构（定位优先、历史 vs 当前分离、无编造业务指标）
- [ ] 全量验证 + push + 远程 SHA 校验
