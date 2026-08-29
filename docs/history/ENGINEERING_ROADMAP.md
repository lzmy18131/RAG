<!-- =====================================================================
  HISTORICAL DOCUMENT — 历史记录，不是当前工程状态。
  当前唯一事实源：docs/engineering/FINAL_ENGINEERING_REPORT.md
  （工程报告）与 docs/evaluation/CURRENT_RESUME_METRICS.md（指标）。
  文档导航：docs/README.md。
===================================================================== -->

> 阶段路线图；其中标注的任务绝大多数已在 Final Pass 完成，本文件仅作历史参考。

# -RAG- 工程路线图（ENGINEERING_ROADMAP）

> 依据 `docs/history/ENGINEERING_AUDIT.md`。原则：**先补工程闭环，再加新算法**；不推倒重写；保护 V0–V9 实验资产可复现。
> 每项含 Impact / Effort / Risk / Files / Acceptance / Measurement。

---

## 汇总

| 优先级 | 数量 | 主题 |
|---|---|---|
| P0 | 4 | 上传穿越、坏文件崩溃、manifest 原子写、缓存 corpus_version |
| P1 | 14 | 依赖、配置统一、测试修复、评测方法学、观测、契约、README 一致性 |
| P2 | 9 | 死代码、重复、nDCG、缓存性能、打包、前端一致性 |

实施阶段（对齐任务书 Phase 0–9）：Audit → Hygiene → Evaluation Foundation → Backend Production → RAG Reliability → Observability → Performance → Frontend → DevOps → Showcase。

---

## Phase 0 — Audit（已完成）

- [x] `docs/history/ENGINEERING_AUDIT.md`
- [x] `docs/history/ENGINEERING_ROADMAP.md`
- [x] BEFORE baseline（157 passed / 28 failed；前端 build/lint ✓；RAG 指标 NOT RUN）
- [ ] git init + 基线提交

## Phase 1 — Repository Hygiene（P0 + 基础 P1）

| # | 任务 | Impact | Effort | Risk | Files | Acceptance / Measurement |
|---|---|---|---|---|---|---|
| H1 | **依赖声明**：requirements 补 fastapi/uvicorn/langgraph/jieba/rank-bm25/python-multipart；dev 拆 optional | 高 | 小 | 低 | requirements.txt / pyproject | `pip install -r requirements.txt` 后 `uvicorn main:app` 可起 |
| H2 | **上传安全（P0-1）**：文件名消毒（uuid 命名）、大小上限、MIME/内容校验、扩展名白名单 | 高 | 小 | 低 | src/api/routes.py | 恶意文件名/超大文件测试 |
| H3 | **坏文件容错（P0-2）**：incremental per-file try/except + failures 记录；清理 raw_docs 垃圾文件 | 高 | 小 | 低 | incremental.py、data/raw_docs | 坏 PDF 不中断整批 |
| H4 | **manifest 原子写（P0-3）**：tmp+rename + fsync | 高 | 小 | 低 | manifest.py | 中断不损坏 |
| H5 | **sys.path/打包**：`pip install -e .` 可工作；main.py 去 sys.path hack；pyproject 完整化 | 高 | 中 | 中 | pyproject.toml、main.py、scripts | `import src.retrieval.hybrid_retriever` 从任意 CWD 成功 |
| H6 | **git 初始化 + .gitignore**（storage/模型缓存/__pycache__）+ 基线提交 | 高 | 小 | 低 | 根目录 | git log 有基线 |
| H7 | **.env.example** 按 settings 全集生成；README 修正（存在性/reranker 模型名/grounding 描述） | 中 | 小 | 低 | .env.example、README | 与代码一致 |
| H8 | **test_phase8 修复（P1-3）**：对齐 V9 + doc_filter 参数 | 高 | 小 | 低 | tests/test_phase8.py | 全套 phase8 绿 |
| H9 | **测试隔离（P1-4）**：9c/9d 全套可跑 | 中 | 小 | 中 | tests/test_phase9*.py | 全套 0 error |
| H10 | **LICENSE 决策**：无 LICENSE——按任务书 §121 不擅自选择；标记待所有者决定；README 不宣称 license | 中 | 小 | 低 | README、docs | 如实标注 |

## Phase 2 — Evaluation Foundation（最高优先级之一）

| # | 任务 | Impact | Effort | Risk | Files | Acceptance / Measurement |
|---|---|---|---|---|---|---|
| E1 | **Dataset 版本化 + schema 落地**：`evals/datasets/{golden_v1,extended_v1,adversarial_v1}.jsonl` + dataset_version/hash；calibration/test split（防 leakage） | 高 | 中 | 中 | evals/datasets/、docs | dataset hash 进入实验 metadata |
| E2 | **Experiment Registry**：`runs/` 结构化（run_id/timestamp/git_commit/dataset_version/hash/config/metrics/failures/report.md） | 高 | 中 | 中 | src/eval/registry.py、scripts | 每张指标表可溯源到 run |
| E3 | **Retrieval metrics 统一**：Recall@K/HitRate@K/Precision@K/MRR/nDCG@K（K∈{1,3,5,10,20}）单模块 | 高 | 中 | 低 | src/eval/retrieval_metrics.py | 与 golden 数据集回归 |
| E4 | **Generation metrics 分层**：deterministic（citation/refusal/support_ratio）+ LLM-judge（faithfulness/relevancy）分开 | 高 | 中 | 中 | src/eval/generation_metrics.py | 不把一切交给 LLM |
| E5 | **Citation eval（deterministic）**：页面存在/source 匹配/证据支撑三态 | 高 | 中 | 中 | src/eval/citation.py | 引用由程序控制 |
| E6 | **Failure Taxonomy**：RETRIEVAL_MISS/RANKING_ERROR/RERANKER_REGRESSION/GENERATION_HALLUCINATION/CITATION_ERROR/OVER_REFUSAL/UNDER_REFUSAL/CACHE_FALSE_HIT/MODEL_PROVIDER_ERROR → failures.jsonl | 高 | 中 | 中 | src/eval/failures.py | 报告"剩下 X% 为什么错" |
| E7 | **Statistical CI**：bootstrap 95% CI + McNemar（版本对比） | 中 | 中 | 中 | src/eval/stats.py | 差异显著性判断 |
| E8 | **Ablation runner**：`make eval-ablation`（V0→V4 统一跑）→ reports/ablation.md | 高 | 中 | 中 | scripts/ablation.py、Makefile | Recall/MRR/nDCG/Faithfulness/Citation/Latency p50/p95/Cost |
| E9 | **Latency 分阶段**：parse/embedding/dense/bm25/fusion/rerank/generation/grounding/total（p50/p90/p95/max） | 高 | 中 | 中 | src/retrieval/*、eval | 回答"V3 为什么 3s→20s" |

## Phase 3 — Backend Production Baseline

| # | 任务 | Impact | Effort | Risk | Files | Acceptance |
|---|---|---|---|---|---|---|
| B1 | request_id middleware + 日志关联 | 高 | 小 | 低 | src/api/middleware.py | 每响应 X-Request-ID |
| B2 | 错误 envelope `{error:{code,message,request_id}}` + 领域异常（RAGError 族） | 高 | 中 | 中 | src/api/errors.py、src/exceptions.py | 无 stack trace 到前端 |
| B3 | `/health/live` `/health/ready` `/version`（semver，不叫 V9） | 高 | 小 | 低 | src/api/routes.py | 就绪探针不调 LLM |
| B4 | API 版本化 `/api/v1/`（向后兼容） | 中 | 小 | 中 | routes、frontend | 旧路径兼容或文档化迁移 |
| B5 | 查询 schema：QueryRequest/QueryResponse（answer/status/citations/sources/grounding/usage/latency/cache/request_id） | 高 | 中 | 中 | src/api/schemas.py | 前端不猜 JSON |
| B6 | SSE `/query/stream`（start/retrieving/reranking/generating/grounding/citation_check/done/error，禁 CoT） | 高 | 中 | 中 | routes、frontend | 阶段事件可用 |
| B7 | 取消生成（断开→取消 LLM 调用） | 中 | 中 | 中 | routes | 停止后不烧 token |
| B8 | 重模型生命周期：lifespan 初始化/关闭；禁 import-time 重初始化 | 高 | 中 | 中 | src/api/deps.py、app 工厂 | 无每请求加载 |
| B9 | 资源并发保护：MAX_CONCURRENT_RERANKS semaphore | 中 | 小 | 低 | reranker、deps | 并发下无 OOM 风暴 |
| B10 | 限流扩展点（内存实现） | 中 | 小 | 低 | middleware | 可配 |
| B11 | app 工厂 `create_app(settings)`（test/demo/prod） | 高 | 中 | 中 | src/api/app.py | TestClient 不加载真模型 |

## Phase 4 — RAG Reliability

| # | 任务 | Impact | Effort | Risk | Files | Acceptance |
|---|---|---|---|---|---|---|
| R1 | **统一检索契约**：RetrievedChunk dataclass（chunk_id/document_id/source_file/page/content_type/dense_score/sparse_score/fusion_score/rerank_score/metadata） | 高 | 中 | 中 | src/retrieval/contracts.py | 替换 dict 传递 |
| R2 | **配置统一**：RRF k / dense_top_k / bm25_top_k / rerank_candidate_k / final_top_k 进 settings；configs yaml 与代码打通（或删除脱节 yaml 改 settings 为 source of truth） | 高 | 中 | 中 | settings.py、hybrid/reranked | 无 magic number |
| R3 | **缓存 key 加 corpus_version（P0-4）** + metadata filter scope 回归测试 | 高 | 中 | 中 | semantic_cache.py、manifest | 知识库更新后缓存失效 |
| R4 | **Grounding 阈值校准脚本**：threshold → precision/recall/F1/abstain/coverage 曲线 + calibration split | 高 | 中 | 中 | scripts/calibrate_grounding.py | 阈值有数据支撑 |
| R5 | **Cite-or-Abstain 三态**：ANSWER / ANSWER_WITH_WARNING / ABSTAIN（前端展示） | 高 | 中 | 中 | grounding、generator、routes | 前端可见 |
| R6 | **Citation 结构化**：LLM 输出 claim/citation_ids → 系统渲染（非自由文本） | 高 | 中 | 中 | generator、grounding | 引用程序控制 |
| R7 | **Prompt Registry**：generation/verification/vlm_caption/query_rewrite 收拢到 src/prompts/（name/version/required_vars），prompt_version 进实验 metadata | 高 | 中 | 中 | src/prompts/ | 无散落 prompt |
| R8 | **Prompt Injection 防御**：检索/文件/VLM caption 标记 untrusted + 对抗文档/对抗 caption 测试 | 高 | 中 | 中 | prompts、tests | 注入用例被拒 |
| R9 | **Provider failure 分级 fallback**：reranker 失败→hybrid 降级（已有）；embedder 失败不伪造；LLM 全 down→degraded | 高 | 中 | 中 | infra、verified_qa | 故障注入测试 |
| R10 | **Timeout budget**：request 级总预算（retrieval/rerank/generation 分段） | 中 | 中 | 中 | settings、routes | 不无限等 |

## Phase 5 — Observability

| # | 任务 | Impact | Effort | Risk | Files | Acceptance |
|---|---|---|---|---|---|---|
| O1 | 结构化日志（LOG_FORMAT=json）+ 字段（request_id/run_id/stage/latency/model/cache_hit） | 高 | 中 | 低 | src/api/logging.py | JSON 模式 |
| O2 | `/metrics` Prometheus：rag_requests/retrieval/rerank/llm/grounding 时长、tokens、cache hit/miss、grounding_rejections、provider_failures（无高基数 label） | 高 | 中 | 低 | src/api/metrics.py | curl 出指标 |
| O3 | **RetrievalTrace**（debug 模式）：dense/BM25/RRF/reranker 各阶段候选与分数 → 前端"检索详情"面板 | 高 | 中 | 中 | src/retrieval/trace.py、routes | debug=true 返回 |
| O4 | LLM/VLM usage 遥测（token/延迟/重试/失败/成本表 configs/model_pricing.yaml） | 高 | 中 | 中 | gateway、llm_client | 不伪造 unknown |
| O5 | tracing 抽象（可选 OTel；TRACE_CONTENT=false 默认不发 raw content） | 中 | 中 | 中 | src/api/tracing.py | 不开 OTel 也能跑 |
| O6 | 隐私：默认不记录完整 query/文档内容 | 中 | 小 | 低 | logging | 扫描无泄漏 |

## Phase 6 — Performance

| # | 任务 | Impact | Effort | Risk | Files | Acceptance / Measurement |
|---|---|---|---|---|---|---|
| P1 | reranker 基准：batch rerank/candidate 尺寸/预热/fp16（硬件允许）/CPU fallback，前后必须 benchmark | 高 | 中 | 中 | benchmark/reranker_bench.py | p50/p95 报告 |
| P2 | hybrid 参数 sweep（RRF k × candidate K × rerank top K 合理 grid）→ quality/latency Pareto frontier | 高 | 中 | 中 | scripts/sweep.py | 最优 vs 最佳性价比结论 |
| P3 | 并发基准（1/2/4 并发）：GPU OOM/Milvus error/cache lock/latency 增长 → 定 MAX_CONCURRENT | 中 | 中 | 中 | benchmark/concurrency.py | 配置有依据 |
| P4 | cache 专项基准：exact/paraphrase/false semantic hit/知识更新失效/doc filter 隔离/语言 | 高 | 中 | 中 | scripts/cache_bench.py | hit/false-hit/节省 |
| P5 | SQLite cache 调优：busy_timeout/WAL/连接生命周期 | 中 | 小 | 低 | semantic_cache.py | 无锁竞争 |

## Phase 7 — Frontend

| # | 任务 | Impact | Effort | Risk | Files | Acceptance |
|---|---|---|---|---|---|---|
| F1 | Q&A 页产品化：流式回答/citation/grounding status/cache badge/latency/stop/retry/copy/evidence 展开 | 高 | 中 | 中 | frontend/src/pages/QAPanel.tsx | 可用 |
| F2 | Evidence Panel（debug 模式展示 dense/BM25/RRF/rerank 四阶段） | 高 | 中 | 中 | frontend/src/components/EvidencePanel.tsx | 面试官可见 hybrid 真实 |
| F3 | KnowledgeBase：上传进度/parse 状态/chunk 数/索引状态/文档版本/删除/错误态 | 高 | 中 | 中 | KnowledgeBase.tsx | 错误清楚 |
| F4 | Experiments 页读 JSON 报告 + 双版本对比 | 中 | 中 | 中 | Experiments.tsx | 不写死 |
| F5 | System Status 页（不显示 secret） | 中 | 小 | 低 | SystemStatus.tsx | 合规 |
| F6 | 前端测试：Vitest + RTL（stream parser/abort/citation 渲染/error state） | 高 | 中 | 中 | frontend/src/**/*.test.* | 覆盖关键逻辑 |
| F7 | 无障碍/响应式 + Playwright E2E（demo mode，CI 用 mock） | 中 | 大 | 中 | e2e/ | 关键流 |

## Phase 8 — DevOps

| # | 任务 | Impact | Effort | Risk | Files | Acceptance |
|---|---|---|---|---|---|---|
| D1 | CI：`.github/workflows/ci.yml`（backend lint/format/typecheck/pytest/cov + frontend lint/typecheck/test/build + docker build） | 高 | 中 | 低 | .github/ | 无 key 全绿 |
| D2 | Docker：backend/frontend Dockerfile（multi-stage 非 root）+ docker-compose（CPU profile；GPU profile 可选） | 高 | 中 | 中 | Dockerfile、compose | demo/CPU 可启动 |
| D3 | pre-commit（whitespace/EOF/YAML/ruff/format） | 中 | 小 | 低 | .pre-commit-config.yaml | hook 可用 |
| D4 | Makefile（install/dev/lint/test/eval*/benchmark/docker-*） | 中 | 小 | 低 | Makefile | Windows 文档化原始命令 |
| D5 | 安全 CI：pip-audit/npm audit（合理 severity，不刷红） | 中 | 小 | 低 | CI | 无高危或已记录 |
| D6 | Demo Mode（DEMO_MODE=true：StubLLM/StubVLM/小语料；前端 DEMO 标记） | 高 | 中 | 中 | src/config、deps、frontend | 无 key 完整体验 |
| D7 | 数据许可证审计：docs/DATA_LICENSE.md（商业说明书不随仓库分发，提供合成 demo 语料） | 高 | 小 | 低 | docs/ | 风险消除 |

## Phase 9 — Showcase

| # | 任务 | Impact | Effort | Risk | Files | Acceptance |
|---|---|---|---|---|---|---|
| S1 | README 重构（结果优先 + 追溯 run_id；架构 Mermaid；Demo 指引） | 高 | 中 | 低 | README.md | 5 分钟看懂 |
| S2 | docs/ARCHITECTURE.md + RAG_ENGINEERING_DEEP_DIVE.md + EXPERIMENT_ANALYSIS.md + ADR-001~006 + CONTRIBUTING + SECURITY | 高 | 中 | 低 | docs/ | 链接组织 |
| S3 | 前端 README 定制 | 中 | 小 | 低 | frontend/README.md | 非模板 |
| S4 | 最终重跑 benchmark → docs/history/ENGINEERING_REPORT_PHASE1.md + docs/history/RESUME_METRICS_PHASE1.md + docs/engineering/TECHNICAL_TRADEOFFS.md | 高 | 中 | 低 | 根目录 | 真实数字 |

---

## 验收红线（DoD 摘要）

- Backend：format/lint/typecheck/unit/integration/cov gate/startup 全过；`pip install -e .` 可导入。
- Frontend：lint/typecheck/test/build 全过；关键 E2E（demo/mock）。
- RAG：Dense / Hybrid / Hybrid+Rerank / 默认管线可复现；Recall@5/MRR/nDCG/Citation Accuracy/Grounding/p50/p95。
- Eval：离线确定性 + retrieval + full online（RUN_ONLINE 门控）+ ablation + failure report + CI。
- Production：docker compose 可启动；Demo 无 key 可跑；CI 无 key 可过；无 secret；有 health/metrics/request_id/structured logs。
- 测试真实性：只写真实执行结果；无法运行标注 NOT RUN + 原因。
