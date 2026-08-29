<!-- =====================================================================
  HISTORICAL DOCUMENT — 历史记录，不是当前工程状态。
  当前唯一事实源：docs/engineering/FINAL_ENGINEERING_REPORT.md
  （工程报告）与 docs/evaluation/CURRENT_RESUME_METRICS.md（指标）。
  文档导航：docs/README.md。
===================================================================== -->

> 本文件是 Final Pass 重构前的基线快照（HEAD b66936a）。其中「FINAL」字样指当时的阶段结论，不代表当前状态。

# FINAL_BASELINE（RAG Final Pass · 代码修改前基线）

> 全部为修改前、当前 HEAD（b66936a）真实执行结果。

## Backend

| 命令 | 结果 |
|---|---|
| `ruff check src/ tests/ scripts/` | ✅ All checks passed |
| `ruff format --check src/ tests/ scripts/` | ✅ 104 files already formatted |
| `pytest tests/ -q -k "not test_phase3 and not test_phase4 and not test_phase5 and not test_phase7_integration and not milvus_collection"` | ✅ **231 passed / 42 deselected**（99.7s） |
| `pytest tests/`（全量 273） | ❌ 42 个 GPU/模型用例挂起（需 BGE 权重下载，无网络）→ 本地 **NOT RUNNABLE** |
| `pytest --cov=src --cov-branch`（离线子集） | **68%**（2453 statements）；关键检索/rerank/vlm/milvus 模块 0~40%（见 AUDIT） |

## Eval / Benchmark

| 命令 | 结果 |
|---|---|
| `python scripts/build_evals_datasets.py` | ✅ golden_v1(100, hash=253762c4) + extended_v1(123, hash=131cf886) |
| retrieval eval / generation eval / cache benchmark / grounding eval | **NOT RUN**（需 BGE 权重 + Milvus 集合 + LLM/VLM API） |
| `python scripts/ablation.py` | NOT RUN（runs/ 无产物） |

## Frontend

| 命令 | 结果 |
|---|---|
| `npm ci` | node_modules 已存在（未重跑） |
| `npm run lint`（oxlint） | ✅（此前 CI 验证） |
| `npx tsc -b --noEmit` | ✅（build 内含 tsc -b） |
| `npm test` | ❌ **无 test script / 无测试框架**（package.json 无 vitest） |
| `npm run build` | ✅（此前 CI 验证） |
| Playwright E2E | ❌ **不存在**（无 e2e 目录 / 无 playwright 依赖） |

## Docker

| 命令 | 结果 |
|---|---|
| `docker compose build` | **NOT RUN**（本环境无 Docker） |
| Dockerfile multi-stage 声明 | ❌ 假声明（单 FROM）→ 修 |

## 其他

- Python 3.12.6（venv）；torch/sentence-transformers/pymilvus/milvus-lite 已安装但**无模型权重缓存**（`~/.cache/huggingface` 仅有 datasets）
- pip 可通过 `--trusted-host pypi.org --trusted-host files.pythonhosted.org` 联网 → 已补装 pytest-cov/coverage/mypy/ragas/datasets
- runs/（registry 目标）空；storage/runs/ 有历史 artifact → 双目录不一致（P1-4）
