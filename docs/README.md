# Documentation Index（文档导航）

本仓库文档按 **Current（当前事实源）→ Engineering → Evaluation → Career → History** 组织。
原则：**当前状态只维护一份事实源**（工程报告 + 指标）；历史文档一律标注 HISTORICAL，不等同于当前 HEAD。

---

## Current（当前事实源）

| 文档 | 说明 |
|---|---|
| [../README.md](../README.md) | 项目首页（产品定位 / 指标 / 架构 / 管线 / 限制 / 快速开始） |
| [engineering/FINAL_ENGINEERING_REPORT.md](engineering/FINAL_ENGINEERING_REPORT.md) | **当前工程报告（唯一）**：架构 / 管线 / 评估 / 可靠性 / 验证表 |
| [evaluation/CURRENT_RESUME_METRICS.md](evaluation/CURRENT_RESUME_METRICS.md) | **当前指标（唯一）**：commit / run_id / 测试 / 覆盖率 / Demo 基准 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 当前架构事实源（V0–V9 链路、模块边界、评测边界） |
| [DATA_CONTRACTS.md](DATA_CONTRACTS.md) | 数据契约（Chunk / QA / QueryResult / ExperimentRun） |
| [DATA_LICENSE.md](DATA_LICENSE.md) | 数据来源分类与版权声明（商业说明书不随仓库分发） |

## Engineering（工程深潜）

- [engineering/RAG_ENGINEERING_DEEP_DIVE.md](engineering/RAG_ENGINEERING_DEEP_DIVE.md) — RAG 工程 17 问（含代码证据）
- [engineering/TECHNICAL_TRADEOFFS.md](engineering/TECHNICAL_TRADEOFFS.md) — 真实工程权衡（dense/sparse、RRF、bi/cross-encoder、grounding、cache…）
- [engineering/evaluation.md](engineering/evaluation.md) — 评测体系（数据集版本化 / 指标 / 运行方式）

## Evaluation（评估与实验）

- [evaluation/CURRENT_RESUME_METRICS.md](evaluation/CURRENT_RESUME_METRICS.md) — 当前指标（唯一）
- [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md) — 实验方法论（控制变量 / 数据集使用规则 / 必测指标）
- 实验产物：`runs/<run_id>/`（Experiment Registry：config / metadata / metrics / failures / report）

## Career（求职 / 面试材料）

- [career/INTERVIEW_GUIDE.md](career/INTERVIEW_GUIDE.md) — 面试深挖 30 问（代码实证版）
- [career/RESUME_PROJECT_DRAFT.md](career/RESUME_PROJECT_DRAFT.md) — 简历项目草稿（数字来源：CURRENT_RESUME_METRICS）

## History（历史记录 — 非当前状态）

> 以下文件均为 **HISTORICAL**：记录 V0–V9 开发过程 / 阶段性报告 / 已修复问题的审计。
> 引用其中数字时须注明「历史记录，重构后未重跑 / 非当前 HEAD」。

- [history/V0_V9_EXPERIMENTS.md](history/V0_V9_EXPERIMENTS.md) — V0–V9 实验史（历史 benchmark）
- [history/ENGINEERING_REPORT_PHASE1.md](history/ENGINEERING_REPORT_PHASE1.md) — Phase 1 工程升级报告（当时 Coverage/Demo/E2E 未完成）
- [history/FINAL_ENGINEERING_AUDIT.md](history/FINAL_ENGINEERING_AUDIT.md) — Final Pass 起点审计（P0 问题已全部修复）
- [history/FINAL_BASELINE.md](history/FINAL_BASELINE.md) — 重构前基线快照（231 passed / 68%）
- [history/ENGINEERING_AUDIT.md](history/ENGINEERING_AUDIT.md) — 修复前全量审计
- [history/RESUME_METRICS_PHASE1.md](history/RESUME_METRICS_PHASE1.md) — 旧 commit 指标（已废弃）
- [history/PROGRESS.md](history/PROGRESS.md) / [history/ROADMAP.md](history/ROADMAP.md) / [history/ENGINEERING_ROADMAP.md](history/ENGINEERING_ROADMAP.md) — V0–V9 推进与路线图
- [history/SESSION_LOG.md](history/SESSION_LOG.md) — 开发会话日志
- [history/PHASE_0_IMPLEMENTATION_BRIEF.md](history/PHASE_0_IMPLEMENTATION_BRIEF.md) — Phase 0 实施任务书

## Internal / 协作协议

- [PROJECT_CHARTER.md](PROJECT_CHARTER.md) — 项目宪章（目标 / 范围 / 默认技术决策）
- [DECISIONS.md](DECISIONS.md) — 决策日志（D-001~D-011）
- [IMPLEMENTER_PROTOCOL.md](IMPLEMENTER_PROTOCOL.md) — 外部实现 AI 协作协议
- [ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md) — 阶段验收标准
- [GITHUB_METADATA_UPDATE.md](GITHUB_METADATA_UPDATE.md) — GitHub 展示元数据维护说明

## 清理记录

- [REPOSITORY_CLEANUP_REPORT.md](REPOSITORY_CLEANUP_REPORT.md) — 本轮文档清理（Removed / Moved / Updated / Corrected Claims）
