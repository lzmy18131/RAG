# Demo Retrieval Eval (demo_retrieval_v1)

> Demo Mode 确定性基准：合成硬件手册语料（20 chunks）+ Hybrid(RRF) + Rerank。
> CI 离线回归用；不是真实模型 benchmark。

| Metric | Value |
|---|---:|
| recall@1 | 0.5417 |
| recall@3 | 0.9167 |
| recall@5 | 0.9167 |
| hit@5 | 1.0 |
| mrr | 0.9167 |
| ndcg@5 | 0.8792 |

## Cache benchmark
- exact hits: 12 / 12
- semantic hits: 1
- false hit rate: 0.0