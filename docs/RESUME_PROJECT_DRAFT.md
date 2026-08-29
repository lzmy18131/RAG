# RESUME_PROJECT_DRAFT（简历项目草稿 · 数字来源：docs/CURRENT_RESUME_METRICS.md）

> 面试前按当前 commit 真实数字核对后使用；禁止添加未验证业务成果。

## 项目标题

**多模态可信 RAG 智能硬件维保知识助手（Production-style Multimodal RAG & Evaluation System）**

定位：Deep RAG Engineering（与 LingYi 的 Multi-Agent Application Engineering 区分）

## 技术栈（真实使用）

Python · FastAPI · React 19 + Vite · BGE-M3（Dense）· BM25（jieba）· RRF · BGE-Reranker（Cross-Encoder）· Milvus Lite · SQLite · LangGraph（Verify 流程）· Prompt Registry · Prometheus · Docker · GitHub Actions

## 简历 Bullets（≤5 条，数字来自当前 verified run）

1. **Hybrid Retrieval**：基于 BGE-M3 Dense Retrieval + BM25 构建 Hybrid Retrieval，通过 RRF 融合并用 Cross-Encoder Reranker 优化 Top-K 排序（top-20 → top-5）；基于固定 Golden Dataset 对 Dense / Hybrid / Rerank 做控制变量实验，量化 Recall@5 / MRR / nDCG 与延迟 tradeoff（demo 基准 Recall@5=0.92，MRR=0.92，可追溯 run_id）。
2. **Grounding / Citation**：设计句级 deterministic grounding、citation validator 与 cite-or-abstain 策略，引用由系统从真实检索结果计算（非 LLM 声称）；诚实声明 relevance ≠ entailment，并通过 adversarial/calibration 评估 unsupported claim 与过拒/误拒。
3. **Eval / Ablation**：构建版本化 Evaluation / Experiment Registry（runs/<run_id> 含 metadata/metrics/failures/report），覆盖 retrieval / generation / citation / cache / failure taxonomy（12 类），使用 Bootstrap CI 与配对比较分析版本差异，防 test-set leakage。
4. **Cache / Index / Reliability**：实现 incremental indexing（SHA256 manifest 原子写）、corpus-version-aware semantic cache（防 stale/false-hit，demo 基准 false-hit=0.0）与 LLM Gateway（retry / circuit breaker / provider failover），量化缓存命中与 p95 延迟。
5. **Application Engineering**：FastAPI + SSE（分阶段流式 + 取消不包装 500）+ React（Q&A / Evidence Panel / Citation UI / Experiments / System Status），Docker multi-stage 非 root，CI 含 **mypy / coverage 真 gate** 与 Playwright E2E（Demo Mode，7 场景全绿），Prometheus 可观测。

## 明确不写

- ✗ 故障处理时间下降 X% / 自助率提升 X%（无真实用户研究）。
- ✗ V0-V9 历史数字当最新（标注 NOT VERIFIED AFTER REFACTOR）。
- ✗ "Native image-text unified embedding"（实际是 VLM caption → text → BGE）。
- ✗ Agent 数量 / Multi-Agent（本项目是 RAG 深度工程，不是 Agent 编排）。

## 可写入的数字（当前 commit 实测，见 docs/CURRENT_RESUME_METRICS.md）

| 指标 | 值 |
|---|---|
| Backend tests | 273 passed |
| Coverage（branch） | 77%（gate 70） |
| mypy | 0 errors |
| Frontend tests / E2E | 7 / 7（Demo Mode） |
| Demo retrieval Recall@5 / MRR / nDCG@5 | 0.9167 / 0.9167 / 0.8792 |
| Cache false-hit rate | 0.0 |
