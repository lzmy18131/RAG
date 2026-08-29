# 多模态可信 RAG 智能硬件维保知识助手

**Production-style Multimodal RAG & Evaluation System**

基于 **BGE-M3 Dense + BM25 Hybrid Retrieval + RRF 融合 + Cross-Encoder Reranker + 确定性 Grounding + Citation Validation + Semantic Cache** 的多模态 RAG 应用，配套完整 Evaluation / Experiment Registry / Observability / CI / Docker / Demo Mode。

> ⚠️ 本项目为 AI Application / RAG Engineering 实践项目，输出仅供参考，**不构成设备维修或医疗建议**。

---

## Hero

![LingYi RAG Demo（DEMO MODE）](docs/screenshots/demo-qa.png)

> 真实 UI 截图（DEMO Mode 下问答：答案 + 引用 + Grounding 徽章 + DEMO 标记）。

## Key Engineering Metrics（当前 commit 实测）

| Metric | Result |
|---|---:|
| Backend tests（离线子集） | **273 passed** |
| Backend coverage（branch） | **77%**（gate=70） |
| Typecheck（mypy） | **0 errors**（54 files） |
| ruff check / format | ✅ |
| Frontend unit tests（Vitest+RTL） | **7 passed** |
| Playwright E2E（Demo Mode） | **7 scenarios** |
| Demo retrieval benchmark（Recall@5 / MRR / nDCG@5） | **0.9167 / 0.9167 / 0.8792** |
| Semantic cache（exact hit / false-hit rate） | **12/12 / 0.0** |
| Critical modules coverage | retrieval 86~89% · grounding 92% · cache 94% · gateway 84% |

> 全部数字来自当前 commit 真实执行（`docs/CURRENT_RESUME_METRICS.md` 记录 commit/run_id）。
> 历史 V0–V9 benchmark 见 [Historical Results](#historical-results-v0v9)（重构后**未重跑**，标注 NOT VERIFIED AFTER REFACTOR）。

---

## 核心架构

```text
User (React 19 + Vite)
   │ HTTP / SSE
   ▼
FastAPI (RequestID / 统一错误 envelope / Prometheus /metrics)
   │
   ▼
RAGService (src/api/services/rag_service.py — 分阶段计时 + SSE stage 事件)
   │
   ├─ SemanticCache (exact SHA256 + BGE-M3 cosine, corpus_version + schema_version salt)
   │
   ▼
RerankedRetriever (二阶段)
   ├─ Stage1 HybridRetriever: BGE-M3 Dense + BM25 (jieba) → RRF 融合 (top-20)
   ├─ Stage2 Cross-Encoder Reranker (BGE-Reranker-v2-m3) → top-5
   ▼
Generator (LLM, Prompt Registry + 注入防御 <untrusted>)
   ▼
GroundingVerifier (句级 Cross-Encoder 确定性接地)
   ▼
Citation Validator（引用由系统从真实检索结果计算，非 LLM 声称）
   ▼
Cite-or-Abstain（answered / refused）
```

## Hybrid Retrieval（为什么这样设计）

- **BGE-M3（Bi-Encoder）**：语义近似（"无法开机" ↔ "电源故障"），query 与 doc 独立编码 → 可预计算向量 → 快。
- **BM25（Sparse，jieba 分词）**：精确术语（"PTC"、"E07"、型号名）在向量空间会被稀释，关键词匹配是硬需求。
- **RRF 融合**：`score = Σ 1/(k + rank)`，只看排名不看分数 → 不需要归一化 dense cosine 与 BM25 无界频率分（量纲不同不能直接相加）。k=60 偏向"两路都靠前"的项。
- **Cross-Encoder Reranker（Stage 2）**：query+doc 拼接联合编码 → 精确但慢 → 只对 top-20 精排取 top-5（质量-延迟 Pareto）。

参数全部配置化（`retrieval_rrf_k / dense_top_k / bm25_top_k / rerank_candidate_k / final_top_k`），无 magic number。

## Grounding / Citation / Abstain

- **Grounding**：答案拆句 → 每句与检索 chunk 用 Cross-Encoder 联合打分 → 无支撑句子标记。文档诚实声明：这是 **deterministic relevance-based grounding**，`relevance ≠ entailment`——交叉编码器拦不住"主题相关但编造"（Frankenstein 边界），不是"彻底解决幻觉"。
- **Threshold 由校准数据决定**：`scripts/calibrate_grounding.py` 输出 threshold→precision/recall/F1/abstain/coverage 曲线，不拍脑袋选阈值。
- **Cite-or-Abstain**：输出状态 `ANSWER / ANSWER_WITH_WARNING / ABSTAIN`（前端展示 Supported / Warning / Abstained）。证据不足 → 拒答，不硬答。
- **Citation Validator**：引用（chunk_id/source/page）由系统从**真实检索结果**计算，不允许 LLM 自行写页码 → 不存在"引用第 37 页但第 37 页不存在"。

## Evaluation & Experimentation

- **统一指标模块**（`src/eval/retrieval_metrics.py`）：Recall@K / HitRate@K / Precision@K / MRR / nDCG@K（K∈{1,3,5,10,20}），禁止散落脚本各算各的。
- **Generation 指标**：Faithfulness / Answer Relevancy / Context Precision / Context Recall / Citation Correctness / Citation Completeness / Refusal Accuracy（区分 deterministic 与 LLM-as-Judge）。
- **统计检验**：Bootstrap 95% CI + McNemar 配对比较——0.858 → 0.861 不宣称"显著提升"。
- **Failure Taxonomy**：12 类确定性归因（RETRIEVAL_MISS / RERANKER_REGRESSION / CACHE_FALSE_HIT / GENERATION_HALLUCINATION…），输出 failures.jsonl。
- **Experiment Registry**（`runs/<run_id>/`）：config / metadata（git_commit、dataset_version、dataset_hash、corpus_version、模型、prompt_version）/ metrics / failures / report。README 每个 benchmark 可追溯 run_id。
- **Ablation**：`scripts/ablation.py` 汇总 Dense / Hybrid / Hybrid+Rerank 的 Recall@5 / MRR / nDCG / Faithfulness / Citation / p50 / p95 / tokens / cost。
- **防 leakage**：calibration/dev 与 test split 分离，禁止用 test set 反复调参（README 明示）。

### Current Verified Benchmark（demo corpus，run `demo_retrieval_v1`）

| Pipeline | Recall@5 | MRR | nDCG@5 | 说明 |
|---|---:|---:|---:|---|
| Demo Hybrid + Rerank（合成语料，12 题） | **0.9167** | **0.9167** | **0.8792** | 确定性可复现（CI 离线回归） |

> 真实 BGE-M3/Milvus/LLM benchmark 需 GPU + 模型权重 + API key（见 Known Limitations；`scripts/final_evaluation.py`）。

## Semantic Cache & Incremental Index

- **Cache key 防 stale**：`query + corpus_version + schema_version + doc_filter`——知识库更新或响应契约变化 → 缓存自动失效；doc_filter 隔离跨文档命中。
- **Cache eval 指标**：hit rate 之外重点看 **false-hit rate**（相似 ≠ 同义），当前 demo 基准 false-hit = 0.0。
- **Incremental Index**：SHA256 manifest 原子写（tmp + rename）；per-file 容错；chunk_id 稳定派生（document_id|page|chunk_index）。Milvus Lite 无事务 → 删除旧+写新非原子（文档化限制）。

## Application Features

- **Q&A**：v1 契约（answer / citations / grounding / usage / latency / cache / request_id），SSE 流式（stage 事件 + demo token 流），停止生成（CancelledError 不包装 500）。
- **Evidence Panel（developer）**：Dense rank / BM25 rank / RRF score / Rerank score / chunk_id / page——证明 Hybrid Retrieval 真实实现。
- **Citation UI**：点击引用展开 source/page/excerpt + 各通道分数。
- **Knowledge Base**：文档列表（demo 内置语料）/ 上传（真实模式，MAX_UPLOAD_MB / MAX_PDF_PAGES 配置化）。
- **Experiments 页面**：从 Experiment Registry 真实读取（`runs/`）；无 run → 显示 no verified run。
- **System Status**：embedding / reranker / vector store / gateway 熔断状态 / cache / corpus version（不含 secret）。

## Observability

- request_id 全链路；统一错误 envelope；`/health/live`（存活）/ `/health/ready`（真实检查，不可用 503）/ `/version`（app_version/pipeline_version/git_commit 分离）。
- Prometheus `/metrics`：http/rag 分阶段 latency、llm 调用/失败/重试、provider failover、circuit open、cache hit/miss、grounding rejections、input/output tokens（不把 query/request_id 当 label）。
- LLM Gateway：retry / circuit breaker / provider failover / timeout；usage 缺失 → null 不伪造 0。

## Demo Mode（无 API key / GPU / 模型下载）

```bash
DEMO_MODE=true python -m uvicorn main:app --port 8000
# 或 Docker 一键：
DEMO_MODE=true docker compose up --build
```

- 内置**合成硬件手册语料**（20 chunks，公开可分发，非真实品牌手册）。
- FakeEmbedder / FakeReranker / FakeMilvusClient / DemoLLM 复用**真实管线代码**（Hybrid→RRF→Rerank→Grounding→Cache），确定性可复现。
- 页面显著 DEMO MODE 标记；输出带「DEMO 演示模式 · 非真实维修结论」。
- 可完整体验：检索 → 引用 → 接地 → 缓存命中 → 越界拒答 → SSE 流式。

## Quick Start

```bash
# 1. Demo（推荐先体验）
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
DEMO_MODE=true .venv/Scripts/python -m uvicorn main:app --port 8000
cd frontend && npm ci && npm run dev   # http://127.0.0.1:5173

# 2. 真实模型开发
#    .env 配置 LLM/VLM API key + 本地 BGE 模型（EMBEDDING_MODEL/RERANKER_MODEL）
python scripts/ingest.py               # 索引真实说明书
python -m uvicorn main:app --port 8000

# 3. Docker
docker compose up --build
```

## Testing & CI

```bash
ruff check src/ tests/ scripts/ && ruff format --check src/ tests/ scripts/
mypy src                                   # typecheck gate（fail → fail）
pytest tests/ --cov=src --cov-branch       # coverage gate（fail_under=70）
python scripts/demo_retrieval_eval.py      # 离线检索基准（CI 回归）
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
npx playwright test                        # E2E（Demo Mode）
```

CI（`.github/workflows/ci.yml`）：backend（ruff/format/**mypy**/pytest/**coverage**/offline eval/pip-audit）+ frontend（lint/typecheck/**vitest**/build/npm audit）+ **E2E（Playwright Demo）** + **Docker build** + full-eval（workflow_dispatch，需 MILVUS_URI+模型）。PR 不调用真实 LLM / 不产生费用。

## Historical Results（V0→V9）

> ⚠️ 以下为历史实验数字（旧环境 artifact），**本重构后未重跑 → NOT VERIFIED AFTER REFACTOR**。
> 保留作为 RAG 技术演进故事（Dense → 多模态 → Hybrid → Rerank → Verify → 增量 → 确定性 Grounding → Gateway → 多文档 → 语义缓存）。
> 当前可信数字见上方 Key Metrics / Current Verified Benchmark（可追溯 run_id）。

| 版本 | 做了什么 | 历史核心指标 |
|---|---|---|
| V0 | Dense Retrieval | Recall@5 0.89 |
| V1 | + 多模态（VLM caption） | 覆盖图片问题 |
| V2 | + Hybrid (BM25+RRF) | MRR 0.76→0.84 |
| V3 | + Cross-Encoder Rerank | Recall@5 0.88→0.91，延迟 6x |
| V4 | + LangGraph Verify | 越界拒答 |
| V5 | + 增量索引 | unchanged 0 embedding |
| V6 | + 确定性 Grounding | 投毒测试拦截 82% |
| V7 | + LLM Gateway | retry/熔断/failover |
| V8 | + 多文档 + doc_filter | 123 题 retrieval-only MRR 0.89 |
| V9 | + 语义缓存 | 精确命中 ~31ms |

## Known Limitations（诚实声明）

- **Golden Dataset 规模有限**（100/123 条，领域窄：智能硬件说明书）。
- **Grounding 是 relevance 不是 entailment**：拦不住主题相关编造（Frankenstein 边界）。
- **VLM 依赖**：多模态走 VLM caption → text → BGE，**不是** native image-text unified embedding（README 不夸大）。
- **Milvus Lite 单进程**：无事务，删除+重建非原子；不能多 worker。
- **Semantic Cache 是近似**：语义命中可能 false-hit（有 corpus_version/schema 失效缓解）。
- **未做互联网规模压力测试**；业务数据规模有限。
- **Demo 是 deterministic fake**：合成语料 + 确定性模型，非真实诊断/维修结论。
- 未接入 Query Rewrite / Adaptive Retrieval / Native Multimodal（无 benchmark 证明收益前不加——见 docs/DECISIONS.md）。

## Project Origin / License

本项目在开源项目 `luxharves/-RAG-`（2026-08-25 快照）基础上进行生产化工程改造（评估体系 / 可靠性 / 可观测性 / 测试 / CI / Docker / Demo）。商业说明书 PDF 不随仓库分发（见 `docs/DATA_LICENSE.md`）。License：MIT。

## 文档

- [docs/FINAL_ENGINEERING_AUDIT.md](docs/FINAL_ENGINEERING_AUDIT.md) — 收尾审计
- [docs/FINAL_ENGINEERING_REPORT.md](docs/FINAL_ENGINEERING_REPORT.md) — 最终工程报告
- [docs/CURRENT_RESUME_METRICS.md](docs/CURRENT_RESUME_METRICS.md) — 当前 commit 指标
- [docs/RAG_ENGINEERING_DEEP_DIVE.md](docs/RAG_ENGINEERING_DEEP_DIVE.md) — RAG 工程深潜（含代码证据）
- [docs/INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md) — 面试深挖 30 问
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) / [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md) / [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md) / [docs/DECISIONS.md](docs/DECISIONS.md)
