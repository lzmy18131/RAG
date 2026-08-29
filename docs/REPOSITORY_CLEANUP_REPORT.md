# REPOSITORY_CLEANUP_REPORT

> 本轮文档清理（docs/README + metadata + historical alignment）。**未新增任何 RAG 功能**；核心代码仅两处一致性微调（见 Updated）。

## Removed（移除）

- 根目录 `RESUME_METRICS.md` / `ENGINEERING_REPORT.md` / `TECHNICAL_TRADEOFFS.md`（自根目录移除，分别归入 history / engineering，见下）。
- 根目录多余 md 已清空（根目录现仅保留 README.md + LICENSE + pyproject/Makefile/Dockerfile/compose/.env.example 等运行文件）。
- 无 benchmark 数字被修改或删除（历史数字原样保留，仅移动 + 标注 Historical）。

## Moved（移动，git mv 保留历史）

| 旧路径 | 新路径 |
|---|---|
| `ENGINEERING_REPORT.md`（根） | `docs/history/ENGINEERING_REPORT_PHASE1.md` |
| `RESUME_METRICS.md`（根） | `docs/history/RESUME_METRICS_PHASE1.md` |
| `TECHNICAL_TRADEOFFS.md`（根） | `docs/engineering/TECHNICAL_TRADEOFFS.md` |
| `docs/CURRENT_RESUME_METRICS.md` | `docs/evaluation/CURRENT_RESUME_METRICS.md` |
| `docs/FINAL_ENGINEERING_REPORT.md` | `docs/engineering/FINAL_ENGINEERING_REPORT.md` |
| `docs/RAG_ENGINEERING_DEEP_DIVE.md` | `docs/engineering/RAG_ENGINEERING_DEEP_DIVE.md` |
| `docs/evaluation.md` | `docs/engineering/evaluation.md` |
| `docs/INTERVIEW_GUIDE.md` | `docs/career/INTERVIEW_GUIDE.md` |
| `docs/RESUME_PROJECT_DRAFT.md` | `docs/career/RESUME_PROJECT_DRAFT.md` |
| `docs/EXPERIMENT_LOG.md` | `docs/history/V0_V9_EXPERIMENTS.md` |
| `docs/ENGINEERING_AUDIT.md` / `FINAL_BASELINE.md` / `FINAL_ENGINEERING_AUDIT.md` / `PROGRESS.md` / `ROADMAP.md` / `SESSION_LOG.md` / `ENGINEERING_ROADMAP.md` | `docs/history/`（同名） |
| `docs/phases/PHASE_0_IMPLEMENTATION_BRIEF.md` | `docs/history/PHASE_0_IMPLEMENTATION_BRIEF.md` |

移动后已全仓库更新引用（docs 内为反引号内联路径，逐处替换为 `docs/engineering|evaluation|career|history/` 前缀；README 真链接同步更新）。

## Updated（更新）

- **README.md**：按产品化顺序重排（定位 → Hero → Metrics → Architecture → Pipeline → Retrieval → Grounding → Evaluation → Features → Demo → Testing → 历史 → 限制 → Origin）；V0–V9 压缩为 Version/Problem/Change/Outcome/Tradeoff 五列；指标表改为当前实测口径（CI 子集 226 / 覆盖 72.46% · 本地全量 294/77.8%）。
- **docs/evaluation/CURRENT_RESUME_METRICS.md**：测试/覆盖率数字更新为当前真实执行（226/72.46% CI；294/77.8% 本地全量）；21 个 artifact 依赖失败用例明确列出。
- **docs/engineering/FINAL_ENGINEERING_REPORT.md**：commit 引用更新（df7ebdb）+ 验证表数字更新。
- **docs/engineering/evaluation.md**：删除过时「231 passed」硬编码，改为引用 CURRENT_RESUME_METRICS。
- **docs/history/V0_V9_EXPERIMENTS.md**：V6 状态 RUNNING → DONE（历史）；补充 V3/V4/V5/V7 覆盖说明。
- **frontend/README.md**：Vite 模板 → 真实前端文档（Role/Stack/Routes/API/SSE/Dev/Test/Build）。
- **LICENSE**：新增（MIT，对齐 pyproject 声明与 Project Origin 归属）。
- **pyproject.toml**：新增 `[project.urls]`（Homepage/Repository/Issues → lzmy18131/RAG）。
- **tests/smoke/test_project_structure.py**：governance 文档断言更新为新目录结构。
- **frontend/src/App.tsx**：侧栏陈旧标签 `V5 · FastAPI` → `rag-v9 · FastAPI`（与 `/version` pipeline_version 一致）。

## Corrected Technical Claims（修正的技术表述）

- **Multimodal**：统一为 **caption-based（VLM 辅助图像理解）**；明确「不是 native image-text joint embedding」；补充说明 VLM caption 链路（VLMClient / scripts/ingest_v1.py），当前摄取默认路径为纯文本解析。修正 `PROJECT_CHARTER.md`「统一向量空间」措辞。
- **Grounding**：当前默认 scorer = **Cross-Encoder（BGE-Reranker，`GROUNDING_SCORER=reranker`）**，非 BGE-M3 cosine；cosine 仅为可选/历史路径。文档统一「cross-encoder relevance-based deterministic grounding」，relevance ≠ entailment 明示。
- **Generation 指标**：移除文档中无实现的独立指标（Refusal Accuracy / Citation Correctness / Citation Completeness）；改为「RAGAS faithfulness/context precision/context recall + 脚本 answer_relevancy + 确定性 citation_accuracy + Failure Taxonomy（含 OVER/UNDER_REFUSAL）」。
- **Threshold 表述**：由「阈值由校准数据决定」改为「阈值经校准脚本曲线辅助选择（settings 硬编码默认值，非自动回写）」。
- **LangGraph**：表述为 **workflow orchestration（单一 StateGraph，非 Multi-Agent）**。
- **Cache**：明示 scope 绑定 = doc_filter + corpus_version + schema:v1（**不绑定** prompt/model version）。
- **Docker**：改为「镜像在 CI 构建验证；本地 compose 未端到端验证」。
- **API**：v1 为当前契约，legacy 无前缀路由明确标注兼容。

## Historical Documents（标注 HISTORICAL）

`docs/history/` 下全部文件顶部标注 **HISTORICAL DOCUMENT — 历史记录，不是当前工程状态**，并指向当前事实源。包括：Phase 1 报告、旧指标、修复前审计、FINAL_BASELINE、FINAL_ENGINEERING_AUDIT、V0–V9 实验史、PROGRESS/ROADMAP/SESSION_LOG/ENGINEERING_ROADMAP、Phase 0 brief。

## Current Sources of Truth（当前唯一事实源）

- 工程报告：`docs/engineering/FINAL_ENGINEERING_REPORT.md`
- 指标：`docs/evaluation/CURRENT_RESUME_METRICS.md`
- 文档导航：`docs/README.md`
- 项目首页：根 `README.md`

## Known Limitations（本轮未解决 / 需环境）

- 真实模型 full benchmark（BGE-M3/Milvus/LLM）NOT RUN（需 GPU + 模型权重 + API key）。
- Docker 本地未端到端验证（仅 CI 镜像构建）。
- 前端 DEMO 横幅无条件渲染（注释与代码不一致的 UI 细节，未在本轮改动范围内）。
- `coverage.json`（本地 artifact，未跟踪）与 CI 口径存在差异：文档以 CI 子集 72.46%（gate=70）为准。
