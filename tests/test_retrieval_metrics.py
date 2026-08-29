"""统一检索指标测试（audit E3 / §12）。"""

from __future__ import annotations

import pytest

from src.eval.retrieval_metrics import aggregate, evaluate_query


class TestEvaluateQuery:
    def test_perfect_retrieval(self):
        r = evaluate_query(["a", "b", "c", "d", "e"], ["a"])
        assert r["recall@1"] == 1.0
        assert r["recall@5"] == 1.0
        assert r["hit@1"] == 1.0
        assert r["mrr"] == 1.0
        assert r["top1_hit"] is True
        assert r["ndcg@5"] == 1.0

    def test_second_rank_relevant(self):
        r = evaluate_query(["x", "a", "b", "c", "d"], ["a"])
        assert r["recall@1"] == 0.0
        assert r["recall@3"] == 1.0
        assert r["hit@3"] == 1.0
        assert r["mrr"] == pytest.approx(0.5)
        assert r["top1_hit"] is False
        # 唯一相关项在 rank2 → DCG = 1/log2(3); IDCG(1 相关) = 1
        assert r["ndcg@3"] == pytest.approx(1 / math_log2(3), rel=1e-3)

    def test_miss(self):
        r = evaluate_query(["x", "y", "z"], ["a"])
        assert r["recall@5"] == 0.0
        assert r["mrr"] == 0.0
        assert r["hit@5"] == 0.0

    def test_multiple_relevant_ndcg(self):
        # 相关项 a(rank1) c(rank3)：DCG = 1 + 1/log2(4) = 1.5; IDCG(2 相关) = 1 + 1/log2(3)
        r = evaluate_query(["a", "x", "c", "y"], ["a", "c"])
        assert r["recall@5"] == 1.0
        assert r["ndcg@5"] == pytest.approx(
            (1 + 1 / math_log2(4)) / (1 + 1 / math_log2(3)), rel=1e-3
        )

    def test_precision(self):
        r = evaluate_query(["a", "x", "c", "y", "z"], ["a", "c"])
        assert r["precision@5"] == pytest.approx(0.4)
        assert r["precision@1"] == 1.0

    def test_empty_ranked(self):
        r = evaluate_query([], ["a"])
        assert r["mrr"] == 0.0
        assert r["recall@5"] == 0.0
        assert r["num_retrieved"] == 0

    def test_empty_relevant_raises(self):
        with pytest.raises(ValueError):
            evaluate_query(["a"], [])

    def test_k_values_supported(self):
        r = evaluate_query(list("abcde"), ["b"])
        for k in (1, 3, 5, 10, 20):
            assert f"recall@{k}" in r
            assert f"ndcg@{k}" in r


class TestAggregate:
    def test_mean_aggregation(self):
        q1 = evaluate_query(["a", "b"], ["a"])
        q2 = evaluate_query(["x", "b"], ["a"])
        agg = aggregate([q1, q2])
        assert agg["num_queries"] == 2
        assert agg["mrr"] == pytest.approx(0.5)  # (1.0 + 0.0) / 2
        assert agg["hit@1"] == pytest.approx(0.5)
        assert agg["top1_hit"] == pytest.approx(0.5)

    def test_empty_input(self):
        assert aggregate([])["num_queries"] == 0


def math_log2(x):
    import math

    return math.log2(x)
