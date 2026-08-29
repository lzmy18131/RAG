# 评估文档（Evaluation）

## 数据集（版本化）

| 数据集 | 规模 | dataset_hash | split (cal/test) |
|---|---|---|---|
| golden_v1 | 100 | `253762c4f90e1e8c` | 20/80 |
| extended_v1 | 123 | `131cf8860a5186fc` | 24/99 |

- 构建：`python scripts/build_evals_datasets.py` → `evals/datasets/*.jsonl + *_meta.json`。
- 修改数据集必须递增 `DATASET_VERSIONS`；指标报告必须携带 dataset_hash。

## 指标

- **检索**：Recall@K / HitRate@K / Precision@K / MRR / nDCG@K（`src/eval/retrieval_metrics.py`，K∈{1,3,5,10,20}）。
- **引用**：确定性三态（supported/unconfirmed/unmatched，`src/eval/citation.py`）。
- **失败分类**：12 类（`src/eval/failures.py`），输出 failures.jsonl。
- **统计**：Bootstrap 95% CI + McNemar（`src/eval/stats.py`）。

## 运行

```bash
make eval-build      # 构建数据集
make eval-ablation   # 消融汇总（需 runs 产物）
make eval-retrieval  # 检索评估（需模型+Milvus）
make eval-online     # 在线评估（需 API key）
```

## 校准与 leakage 防护

- Grounding 阈值校准：`python scripts/calibrate_grounding.py --data <标注样本>`（threshold→precision/recall/F1/abstain/coverage）。
- calibration/test split 分离：**不得在 test 集上反复调参**（数据量有限，校准集小——已知局限）。

## 当前可运行性

- 当前 commit 实测（测试数 / 覆盖率 / Demo 基准）以 `docs/evaluation/CURRENT_RESUME_METRICS.md` 为准（记录 commit 与 run_id）。
- 真实模型 RAG 全量指标（BGE-M3/Milvus/LLM，golden_100 / extended_123）**NOT RUN**：需 GPU + 模型权重 + API key；有环境后经 Experiment Registry 注册 run。
