<!-- =====================================================================
  HISTORICAL DOCUMENT — 历史记录，不是当前工程状态。
  当前唯一事实源：docs/engineering/FINAL_ENGINEERING_REPORT.md
  （工程报告）与 docs/evaluation/CURRENT_RESUME_METRICS.md（指标）。
  文档导航：docs/README.md。
===================================================================== -->

> 修复前（2026-08-29）的全量审计；审计发现的问题已在 Final Pass 中修复。

# -RAG- 工程审计报告（ENGINEERING_AUDIT）

> 审计日期：2026-08-29
> 审计方式：全量源码只读审计（src 10.6k 行 Python + 前端 React 19/Vite 8 + 18 个测试文件 + 23 个脚本），所有结论基于代码与实测，带文件:行号证据。
> 审计范围：README / pyproject / requirements / main.py / src/{config,api,infra,ingestion,retrieval,generation,workflow,eval} / tests / scripts / configs/experiments / data / storage / docs / frontend。

---

## 1. Current Architecture（真实现状）

```
React 19 + Vite 前端 (frontend/)  ── HTTP ──>  FastAPI (main.py + src/api/)
                                                  │  deps.py lru_cache 单例注入
              ┌──────────────┬────────────────────┴───────────────┐
              ▼              ▼                                    ▼
       离线摄取链路          在线问答链路                         评测系统
  PDF→VLM caption→        /query → Semantic Cache(精确+语义)     golden_100 / extended_123
  chunk→BGE-M3→Milvus     → Hybrid(BGE-M3 dense + BM25 jieba)     RAGAS + LLM-judge
  +BM25 索引 +manifest    → RRF 融合 → BGE-Reranker 精排         storage/runs/ 实验产物
  (SHA256 增量)           → LangGraph Verify → 生成 → Grounding
                          → 引用审计 → answer/refuse/fallback
```

- **V0–V9 能力均有代码+测试+实验产物**（详见 §5 资产盘点）。
- 依赖注入：`deps.py` 用 `lru_cache` 提供 embedder/reranker/milvus/bm25/retriever/vqa/cache/indexer 单例；模型为懒加载类（非 import-time 初始化）✓。
- LangGraph 仅承担 `retrieve → check_relevance → generate → verify → decide` 状态流转（非 Agent 堆砌）✓ 符合定位。
- Golden Dataset：20（v0_questions）/ 100（golden_100）/ 123（golden_extended）条，schema 含 `question/question_type/difficulty/modality_required/gold_pages/reference_answer/reference_context(s)/source_document/review_status`。

## 2. Existing Strengths（禁止重复建设）

1. **V0–V9 控制变量实验资产**：configs/experiments/*.yaml + storage/runs/ 产物 + 可追溯指标表（README §六）。
2. **LangGraph 验证流程**：verified_qa.py 的 retrieve→relevance→generate→verify→decide 状态机 + max_retries=1 重试 + refuse/fallback 语义。
3. **V6 确定性 Grounding**：句级拆分 → 交叉编码器/余弦打分 → 支持率 → 引用审计（`_CIT_RE` 正则 + basename 匹配），非 LLM 自查。
4. **V7 LLM Gateway**：超时/指数退避+jitter/断路器(CLOSED→OPEN→HALF_OPEN)/三 provider failover/兜底文案，test_gateway 23 用例（纯 fake）。
5. **V9 Semantic Cache**：SQLite 持久化 + 精确 SHA256 + 语义余弦，线程安全（check_same_thread=False + 锁）。
6. **V5 增量索引**：manifest SHA256 分类 added/unchanged/modified/deleted + 集成测试（同库真增量）。
7. **测试基建**：grounding/gateway/cache/phase6 全 fake/mock 可离线跑；测试不调真实 API。
8. **chunk_id 确定性**：`sha256(document_id|p{page}|s{seq})[:16]`。
9. **多文档隔离**：doc_filter（source_file）贯穿 dense(转义 filter 表达式)/bm25/hybrid/reranked/缓存 salt。

## 3. Engineering Gaps

### P0 — 安全/数据完整性（立即修）

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| P0-1 | **上传路径穿越**：`dest = raw_dir / file.filename`，无文件名消毒/大小限制/MIME 校验 | `src/api/routes.py:115`（仅 :107-109 校验扩展名） | 恶意文件名（`../x.pdf`）可写任意位置 |
| P0-2 | **增量摄取遇坏文件整批崩溃**：`incremental.process` 无 per-file 容错；`data/raw_docs/test.pdf`（16B 无效 PDF）使整批失败 | `src/ingestion/incremental.py:34-75`；`data/raw_docs/test.pdf` | 上传一个坏 PDF → 全库索引中断 |
| P0-3 | **manifest 非原子写**：`json.dump` 直接覆盖 | `src/ingestion/manifest.py:80-85` | 中断损坏 manifests.json |
| P0-4 | **缓存 key 缺 corpus_version**：知识库更新后缓存仍返回旧答案 | `src/infra/semantic_cache.py:62-76`（key=salt+query）；`routes.py:192` | stale answer（README/前端自认需手动清理） |

### P1 — 工程闭环（本次升级主体）

| # | 问题 | 证据 |
|---|---|---|
| P1-1 | **依赖未声明**：fastapi/uvicorn/langgraph/jieba/rank_bm25/python-multipart 不在 requirements.txt（实测缺失导致安装后无法运行） | requirements.txt vs 实际导入 |
| P1-2 | **配置三套脱节**：configs/experiments/*.yaml 只有 ingest.py/query.py 读取，检索器不读；settings.py 与 deps 的 .env 重建分叉；代码硬编码 RRF k=60 / dense_top_k=20 / bm25_top_k=20 / MIN_RELEVANCE_SCORE=0.05 | `hybrid_retriever.py:27,140,150`；`verified_qa.py:38`；`deps.py:21-22` vs `settings.py:82` |
| P1-3 | **test_phase8.py 与代码脱节（真 bug）**：断言 version=="V5"（实际 V9）；fake_run 缺 `doc_filter` 参数 → /query 500 | tests/test_phase8.py:74,38-60 vs routes.py:87,207 |
| P1-4 | **测试隔离问题**：test_phase9c/9d 单独跑全过、全套跑报错（import main + patch 时序 + 全局态泄漏） | 实测：单独 6/6，全套 0/6 |
| P1-5 | **评测延迟失真**：`retrieval_latency = generation_latency = total_latency`（未分阶段计时）；README "平均延迟" 不可信 | `scripts/final_evaluation.py:223-224` |
| P1-6 | **评测方法学**：V0 的 RAGAS 指标仅 30/100 分层抽样 + phase1_cached 复用；123 题扩展集仅 retrieval-only | run_phase2_eval.py:77-88,153-163 |
| P1-7 | **storage 产物含他机绝对路径**（`D:\Agentproject1\...`），本地不可复现；无 git 历史 | storage/runs/*.json、manifests.json |
| P1-8 | **README 与代码不一致**：`.env.example` 不存在（README 声称存在）；默认 reranker 模型 `bge-reranker-large` vs 文档 `bge-reranker-v2-m3`；"grounding 用 BGE-M3 余弦" vs 默认交叉编码器；"pdf_parser 提取表格/图片" vs 仅文本；前端 "V5" 标签 vs 后端 V9 | README.md:29,47,98,145,167,181,191,256,307 |
| P1-9 | **无 /metrics、/health/live、/health/ready、/version、request_id、SSE、限流** | src/api/routes.py 路由清单 |
| P1-10 | **无统一契约**：检索结果/LLM 返回/评测记录三种 dict 形状；75 处弱类型；无 RetrievedChunk/LLMResponse dataclass | src/retrieval/*.py、gateway.py:288-299 |
| P1-11 | **grounding 阈值两套并存**（settings 0.55/0.35/0.9 vs grounding.py 默认值），默认 reranker 路径只用 scorer_floor+min_support_ratio | settings.py:46-50 vs grounding.py:221-232 |
| P1-12 | **引用审计默认关闭**（audit_citations=False），citation 是 LLM 生成自由文本 + 正则反解 | grounding.py:115-124；deps.py |
| P1-13 | **raw_docs 数据卫生**：16B test.pdf / 11B test.txt / 重复 manual.pdf；vlm smoke 引用 data/下载.jpg | data/raw_docs/ |
| P1-14 | **无 LICENSE 文件**（§121：不得假装存在）；无 .env.example | 根目录 |

### P2 — 清理与优化

| # | 问题 | 证据 |
|---|---|---|
| P2-1 | 死代码：`infra/milvus_client.py`（仅 smoke 用）、`llm_client._ensure_client/_client`（chat 全走 gateway）、metrics.py 三个被 ragas 取代的 judge | grep 实测 |
| P2-2 | 重复实现：`_latest_col()` 7+ 脚本重复；`_compute_mrr/_recall_at_k` 4 处重复；LLM verifier prompt 三份；MILVUS_URI env hack 15+ 处；拒答短语 4 处耦合 | 全仓 grep |
| P2-3 | 无 nDCG；K 只支持固定集合 | final_evaluation.py:61-74 |
| P2-4 | 语义缓存全表扫描 + 读路径写库（hit_count）+ TTL 不清理 | semantic_cache.py:98-126 |
| P2-5 | sys.path.insert 38 处（脚本/测试）；无打包（pip install -e 不可用） | grep |
| P2-6 | chunk_id 潜在碰撞（多模态与文本 chunk 的 seq 空间重叠）；document_id 基于绝对路径 | document.py:12-20；ingest_v1.py:107-139 |
| P2-7 | /versions 回退数字硬编码（v6 95/100、v8 0.9756 等） | routes.py:272-330 |
| P2-8 | 前端 QAPanel experiment 选择器后端不生效；App.tsx "V5" 过期标签；frontend README 为 Vite 模板 | frontend/src/App.tsx:35 |
| P2-9 | 无 abiom/校准：cache_threshold=0.9、grounding 阈值凭经验 | settings.py:47-50,71 |

## 4. Technical Debt（逐文件）

| 文件 | 债务 |
|---|---|
| `src/api/routes.py` | P0-1 路径穿越、P1-9 无 metrics/SSE/request_id、/versions 硬编码、_extract_metrics 静默 except |
| `src/ingestion/incremental.py` | P0-2 无 per-file 容错、P2-6 半成品无补偿 |
| `src/ingestion/manifest.py` | P0-3 非原子写 |
| `src/infra/semantic_cache.py` | P0-4 key 缺 corpus_version、P2-4 全表扫描/写放大、无 close() |
| `src/retrieval/hybrid_retriever.py` | P1-2 硬编码 k/top_k、分数键冗余（rrf_score==fusion_score）、裸 except |
| `src/workflow/verified_qa.py` | P1-2 MIN_RELEVANCE 硬编码、decide 不更新 answer 导致 refused 时返回旧 answer、拒答文案硬编码 |
| `src/workflow/grounding.py` | P1-11 阈值两套、P1-12 引用审计默认关、_cos 补零掩盖维度错误、异常吞掉无日志 |
| `src/generation/generator.py` | SYSTEM_PROMPT 硬编码、citations=全部 chunks（语义误导）、citation 自由文本 |
| `src/config/settings.py` | P1-8 默认模型名与文档不符、无生产校验、CORS/host 不在此 |
| `src/eval/metrics.py` | 解析失败→0.0（失败与极差不可分）、一半死代码 |
| `main.py` | sys.path hack、version="V9" 硬编码、CORS 硬编码 |
| `requirements.txt` | P1-1 缺 6+ 依赖、混入 dev 依赖 |
| `pyproject.toml` | 仅 testpaths；无 ruff/cov/typecheck 配置 |
| `tests/test_phase8.py` | P1-3 与当前代码脱节 |
| `frontend/README.md` | Vite 模板残留 |

## 5. Architecture Inconsistencies（README/前端 vs 代码）

1. **`.env.example` 不存在**，README:167,256 指导 `cp .env.example .env`。
2. **reranker 模型名**：README/前端/实验元数据 = `bge-reranker-v2-m3`，settings 默认 = `bge-reranker-large`。
3. **grounding 实现**：README 称 "BGE-M3 余弦计算引用"，默认 deps 走 reranker 交叉编码器（cosine 为可选）。
4. **pdf_parser 职责**：README 称"文本/表格/图片提取"，实际仅文本（表格/图片在 ingest_v1 脚本）。
5. **前端版本标签**："V5 · FastAPI" vs 后端 V9。
6. **experiment 选择器**：前端 v4/v3/v2 选择后端不生效（管线固定 V6+V9）。
7. **test_phase8 断言 V5** vs 实际 V9（P1-3）。
8. **data/manifests 与 storage/manifests 双目录**并存。

## 6. BEFORE Baseline（实测，2026-08-29）

| 项 | 结果 |
|---|---|
| pytest（装 python-multipart 后） | **157 passed / 28 failed**（185 collected） |
| 失败归类 | GPU/模型依赖 22（phase3/4/5/7_integration/rag：需 BGE 模型+Milvus 集合）+ 真 bug 6（test_phase8×5、phase9c 隔离×1） |
| 前端 build / lint | ✓ / ✓（oxlint 0 issue） |
| 覆盖率 | 未测（待 Phase 1 建立 gate 后测真实基线） |
| RAG 指标 | **NOT RUN**（需 BGE-M3/Reranker 权重 + Milvus 集合 + 他机产物不可复现） |
| torch/sentence-transformers | 安装中（后台）；BGE 权重不随仓库分发，需首次下载 |

*本审计基于 2026-08-25 仓库快照（zip 分发，无 git 历史）。*
