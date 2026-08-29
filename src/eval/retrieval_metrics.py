"""
统一检索指标（audit E3 / 任务书 §12）。

支持 Recall@K / HitRate@K / Precision@K / MRR / nDCG@K，K ∈ {1,3,5,10,20}。
输入约定：
- ranked_ids: 检索器返回的候选 chunk_id 列表（按相关性降序）
- relevant_ids: 该 query 的 ground-truth 相关 chunk_id 集合
输出：单 query 指标 dict 或聚合 dict（含各 K 值 + 样本数）。
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

# 支持的 K 值（统一实现，禁止散落脚本各自计算）
SUPPORTED_KS: tuple[int, ...] = (1, 3, 5, 10, 20)


def _dcg(ranks: Sequence[int], k: int) -> float:
    """DCG@K：rank 列表（1-based 排名，仅相关项）。"""
    return sum(1.0 / math.log2(r + 1) for r in ranks if r <= k)


def _idcg(k: int, num_relevant: int) -> float:
    """理想 DCG@K。"""
    return sum(1.0 / math.log2(r + 1) for r in range(1, min(k, num_relevant) + 1))


def evaluate_query(
    ranked_ids: Sequence[str],
    relevant_ids: Iterable[str],
    ks: Sequence[int] = SUPPORTED_KS,
) -> dict:
    """计算单 query 的全部检索指标。

    Returns:
        {
          "recall@{k}": float, "hit@{k}": float, "precision@{k}": float,
          "ndcg@{k}": float, ...,
          "mrr": float, "top1_hit": bool, "num_relevant": int, "num_retrieved": int
        }
    """
    relevant = set(relevant_ids)
    num_relevant = len(relevant)
    if num_relevant == 0:
        raise ValueError("relevant_ids 不能为空（无法定义检索指标）")

    ranked = list(ranked_ids)
    # 相关项在 ranked 中的 1-based 排名
    relevant_ranks = [i + 1 for i, cid in enumerate(ranked) if cid in relevant]

    out: dict = {}
    for k in ks:
        top_k = ranked[:k]
        hits = [cid for cid in top_k if cid in relevant]
        out[f"recall@{k}"] = round(len(hits) / num_relevant, 4)
        out[f"hit@{k}"] = 1.0 if hits else 0.0
        out[f"precision@{k}"] = round(len(hits) / max(len(top_k), 1), 4)
        dcg = _dcg(relevant_ranks, k)
        idcg = _idcg(k, num_relevant)
        out[f"ndcg@{k}"] = round(dcg / idcg, 4) if idcg > 0 else 0.0

    # MRR：第一个相关项的倒数排名（未命中记 0）
    out["mrr"] = round(1.0 / relevant_ranks[0], 4) if relevant_ranks else 0.0
    out["top1_hit"] = bool(relevant_ranks and relevant_ranks[0] == 1)
    out["num_relevant"] = num_relevant
    out["num_retrieved"] = len(ranked)
    return out


def aggregate(
    per_query_results: Sequence[dict],
    ks: Sequence[int] = SUPPORTED_KS,
) -> dict:
    """聚合多个 query 的结果（均值）。

    Returns:
        {"recall@{k}": mean, ..., "mrr": mean, "num_queries": n}
    """
    n = len(per_query_results)
    if n == 0:
        return {"num_queries": 0}

    agg: dict = {}
    for k in ks:
        for metric in (f"recall@{k}", f"hit@{k}", f"precision@{k}", f"ndcg@{k}"):
            vals = [r[metric] for r in per_query_results]
            agg[metric] = round(sum(vals) / n, 4)
    agg["mrr"] = round(sum(r["mrr"] for r in per_query_results) / n, 4)
    agg["top1_hit"] = round(sum(1.0 if r["top1_hit"] else 0.0 for r in per_query_results) / n, 4)
    agg["num_queries"] = n
    return agg
