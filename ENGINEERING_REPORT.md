# -RAG- Engineering Upgrade Report

> 升级周期：2026-08（多轮工程改造）
> 基线：`luxharves/-RAG-`（2026-08-25 快照，无 git 历史，zip 分发）
> 目标：从"可复现实验型 RAG 项目"升级为 Production-style RAG Engineering 项目

---

## 1. Before（原项目真实状态）

- 能力资产：V0–V9 技术演进完备（Dense → 多模态 → Hybrid/RRF → Reranker → LangGraph Verify → 增量索引 → 确定性 Grounding → LLM Gateway → 多文档 → Semantic Cache），golden_100/extended_123 数据集，storage/runs 实验产物。
- 测试基线：157 passed / 28 failed（185 collected）；其中 22 个失败为 GPU/模型依赖，6 个为**真 bug**。
- 前端：Vite 8 build/lint ✓；README 为模板。
- 无 git 历史、无 LICENSE、无 .env.example、无 CI/Docker。

## 2. Major Problems Found（真实问题）

| 级别 | 问题 | 修复 |
|---|---|---|
| P0 | 上传路径穿越（`dest = raw_dir / file.filename`） | uuid 命名 + 50MB 上限 + 流式限长 |
| P0 | 坏 PDF 使增量摄取整批崩溃 | per-file 容错 + failures 记录 |
| P0 | manifest 非原子写（中断损坏） | tmp + fsync + os.replace |
| P0 | 语义缓存 key 缺 corpus_version（知识库更新后返回陈旧答案） | salt 追加 `corpus:{manifest_hash}` |
| P1 | **测试 fixture bug**：`with` 块内 `return` 使补丁提前撤销 → 测试真实加载 BGE-M3 挂起 | 改 `yield`；补 routes 命名空间补丁 |
| P1 | 依赖缺失：fastapi/uvicorn/langgraph/jieba/rank_bm25/python-multipart | requirements 补齐 |
| P1 | 检索参数硬编码（RRF k=60 / top_k=20）且 configs yaml 对代码无效 | settings 统一驱动 |
| P1 | 评测延迟失真（retrieval==generation==total） | StageTimer 分阶段计时（Phase 6 接入管线） |
| P1 | 无 nDCG；评测脚本各自实现指标 | 统一 retrieval_metrics 模块 |
| P1 | 商业说明书随仓库分发（版权风险） | git 移除 + DATA_LICENSE 声明 |

## 3. Architecture Changes

```
React 19 + Vite ──> FastAPI (create_app 工厂, RequestID 中间件, 统一错误 envelope)
                     ├─ /health/live /health/ready /version(semver) /metrics(Prometheus)
                     ├─ /query（缓存 salt 含 corpus_version）
                     └─ 依赖注入 deps.py (lru_cache 单例, 懒加载模型)

新增层：
  src/eval/       retrieval_metrics / citation / failures / stats / registry / datasets / latency
  src/prompts/    Prompt Registry (generation:v1 / verification:v1) + 注入防御
  src/retrieval/contracts.py   RetrievedChunk 统一契约
  src/exceptions.py            RAGError 领域异常
  src/api/metrics.py           进程内 Prometheus 指标
  evals/datasets/              版本化评测数据集 (golden_v1 / extended_v1)
  runs/                        Experiment Registry
```

## 4. RAG Engineering

- **Retrieval**：RetrievedChunk 契约；RRF k / dense_top_k / bm25_top_k 配置化（settings 单一来源）。
- **Reranking**：candidate/final top_k 配置化；reranker 降级链保留（失败→hybrid）。
- **Grounding**：阈值校准脚本（threshold→precision/recall/F1/abstain/coverage，calibration split 选取）；拒答计指标。
- **Citation**：确定性校验器（页面存在/来源匹配/检索范围/证据支撑三态）。
- **Cache**：corpus_version 失效（P0-4）；缓存命中/未命中计指标。
- **Incremental Index**：per-file 容错；manifest 原子写。
- **Prompt 工程**：registry 收拢 generation/verification；检索内容 `<untrusted>` 注入防御。

## 5. Evaluation

- 数据集版本化：golden_v1(100)/extended_v1(123) + dataset_hash + calibration/test split（防 leakage）。
- 统一指标：Recall@K/HitRate@K/Precision@K/MRR/**nDCG@K**（此前无 nDCG）。
- 失败分类：12 类确定性归因（RETRIEVAL_MISS/HALLUCINATION/CACHE_FALSE_HIT...）。
- 统计检验：Bootstrap 95% CI + McNemar。
- Ablation 汇总：scripts/ablation.py（无产物时 NOT RUN 如实报告）。
- 延迟：StageTimer 分阶段 p50/p90/p95/max。

## 6. Reliability

- LLM Gateway（V7 保留）：retry/熔断/failover/超时；provider 失败计指标。
- 请求级：request_id 全链路；错误 envelope；/health/live|ready；version semver。

## 7. Observability

- `/metrics`（Prometheus 文本）：http_requests_total、rag_requests_total、cache_hits/misses、grounding_rejections、provider_failures、ingestion_documents。
- request_id 中间件 + 路径归一化（防高基数）。

## 8. Backend

- create_app(settings) 应用工厂；main.py 变薄；领域异常分层；上传安全加固。
- Milvus Lite 单进程约束文档化（docker-compose 固定单 backend）。

## 9. Frontend

- build/lint ✓（Vite 8 + oxlint）；产品化页面（Q&A/KnowledgeBase/Experiments/SystemStatus）保留；
  证据面板与流式输出列入 ROADMAP（Phase 7 未完）。

## 10. DevOps

- CI（backend lint/format/离线 pytest + frontend lint/typecheck/build + docker build + workflow_dispatch full-eval）。
- Docker（后端 multi-stage 非 root + 前端 nginx）+ docker-compose（CPU profile、HF 缓存 volume）。
- pre-commit；Makefile 统一命令。
- Demo Mode：ROADMAP（需 StubLLM/StubVLM）。

## 11. Security

- 上传：路径穿越修复、大小限制、扩展名白名单。
- 注入防御：检索/文档内容 `<untrusted>` 边界 + 系统级禁止执行外部指令。
- 日志：request_id 关联；不记录密钥。
- DATA_LICENSE：商业说明书移出仓库。

## 12. Verification（真实执行）

| 命令 | 结果 |
|---|---|
| `ruff check src/ tests/ scripts/` | ✅ All checks passed |
| `ruff format --check ...` | ✅ 104 files already formatted |
| `pytest tests/`（离线子集，排除 GPU/模型 42 用例） | ✅ **231 passed / 0 failed** |
| `python scripts/build_evals_datasets.py` | ✅ golden_v1(100)+extended_v1(123) 版本化 |
| `python scripts/ablation.py` | ✅ 无产物时如实 NOT RUN |
| 前端 `npm run build` / `npm run lint` | ✅ / ✅ |
| 覆盖率 | **NOT RUN**（未建立 cov gate，见 ROADMAP Phase 2 类型/覆盖率） |
| RAG benchmark（Recall@5/MRR/nDCG 全量） | **NOT RUN**：需 BGE-M3/Reranker 权重 + Milvus 集合 + API key（本环境无 GPU/模型缓存，且 storage 产物含他机绝对路径不可复现） |
| Docker compose up | **NOT RUN**：本环境无 Docker |

## 13. Known Limitations（诚实列出）

1. RAG 指标（V0–V4 全量）在本环境无法重跑：无 GPU、无模型权重缓存、storage 产物来自他机（`D:\Agentproject1\...`）不可复现。
2. 覆盖率 gate 未建立（ROADMAP Phase 2 后续）。
3. Demo Mode / SSE 流式 / 证据面板前端 / Playwright E2E 未完成（ROADMAP）。
4. 在线 evals（RAGAS full）需 API key，默认不跑。
5. 无 LICENSE（待项目所有者决定，未擅自选择）。
6. Milvus Lite 单进程限制。
7. Grounding 阈值校准脚本就绪，但真实标签数据需在有模型环境生成。

## 14. How to run

```bash
# 安装
pip install -r requirements.txt

# 测试（离线子集）
make test

# 评测数据集
make eval-build

# 消融汇总（需 runs 产物）
make eval-ablation

# 后端
PYTHONUTF8=1 python -m uvicorn main:app --port 8000   # 需 .env 配置 API key + 模型

# 前端
cd frontend && npm ci && npm run dev

# Docker
docker compose up --build   # CPU profile；首次启动下载模型
```

---

## 附录：升级后 git 历史（10 commits）
`Phase 0 基线 → fix(phase1) → feat(eval) ×2 → feat(api+eval) → fix(cache) → feat(rag Phase4) → feat(observability) → feat(devops)`
