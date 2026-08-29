# RESUME_METRICS（可写入简历的真实量化指标）

> 仅收录本环境**真实执行**的数字；未能运行的标注 NOT RUN（不得编造）。

## 工程量化（本环境实测）

| 指标 | 数值 | 说明 |
|---|---|---|
| 后端测试 | **231 passed / 0 failed**（离线子集） | 42 个需 GPU/模型的用例 deselected |
| 修复测试真 bug | 6 → 0 | fixture 补丁生命周期、V5 版本断言、multipart 缺失 |
| P0 安全问题修复 | 4 个 | 路径穿越 / 坏文件崩溃 / manifest 原子写 / 缓存陈旧 |
| ruff | check + format 全绿（104 文件） | E501/E402 决策见 pyproject |
| 前端 | build + lint ✓ | Vite 8 + oxlint |
| 评测数据集 | golden_v1(100) + extended_v1(123) 版本化 | dataset_hash + calibration/test split |
| 新增测试 | **74 个**（本轮升级） | eval foundation + API baseline + metrics 等 |

## 能力清单（代码实现 + 测试支撑）

- **Retrieval Evaluation**：Recall@K / HitRate@K / Precision@K / MRR / **nDCG@K**（K∈{1,3,5,10,20}）统一模块
- **Citation Validation**：确定性三态校验（页面/来源/证据支撑），8 个测试
- **RAG Failure Taxonomy**：12 类确定性归因 + failures.jsonl
- **Statistical Evaluation**：Bootstrap 95% CI + McNemar 配对检验
- **Experiment Registry**：runs/\<run_id\>/{metadata,config,metrics,failures}，git_commit/dataset_hash 入 metadata
- **Grounding Threshold Calibration**：threshold→precision/recall/F1/abstain/coverage 扫描
- **Latency 分阶段**：StageTimer p50/p90/p95/max
- **Prompt Registry**：generation/verification 收拢 + 变量契约
- **Prompt Injection Defense**：`<untrusted>` 边界 + 系统级指令
- **Semantic Cache 可靠性**：corpus_version 失效（知识库更新后缓存自动失效）
- **API Production**：request_id / 错误 envelope / health(live/ready) / version(semver) / Prometheus /metrics
- **DevOps**：CI（无 key 全绿）、Docker multi-stage、pre-commit、Makefile、DATA_LICENSE

## NOT RUN（如实标注）

| 指标 | 原因 |
|---|---|
| Hybrid vs Dense MRR 提升 % | 需 BGE-M3/Reranker 权重 + Milvus 集合（本环境无 GPU/模型缓存） |
| V0–V4 全量 RAGAS 指标重跑 | storage 产物含他机绝对路径不可复现 |
| 覆盖率 % | cov gate 未建立（ROADMAP） |
| Docker 启动验证 | 本环境无 Docker |

> 建议：在有 GPU 的环境安装模型后运行 `scripts/final_evaluation.py --dataset golden_100`，
> 用 `src/eval/registry.py` 注册 run，再更新本表（RESUME_METRICS 只收真实数字）。
