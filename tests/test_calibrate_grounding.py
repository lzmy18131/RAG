"""Grounding 阈值校准测试（audit R4 / §16）。"""

from __future__ import annotations

import pytest

from scripts.calibrate_grounding import pick_best, sweep_thresholds


@pytest.fixture()
def samples():
    # 10 个真实支撑（score 高）+ 10 个真实不支撑（score 低）
    return [{"score": 0.8 + i * 0.01, "supported": True} for i in range(10)] + [
        {"score": 0.3 - i * 0.01, "supported": False} for i in range(10)
    ]


class TestSweepThresholds:
    def test_low_threshold_high_coverage_low_precision(self, samples):
        rows = sweep_thresholds(samples, [0.05])
        r = rows[0]
        assert r["coverage"] == 1.0  # 全预测 supported
        assert r["precision"] == pytest.approx(0.5)  # 10 TP / 20

    def test_high_threshold_high_precision(self, samples):
        rows = sweep_thresholds(samples, [0.75])
        r = rows[0]
        assert r["precision"] == 1.0  # 无 FP
        assert r["recall"] == 1.0
        assert r["abstain_rate"] == 0.5  # 10 个低分 abstain

    def test_mid_threshold_reasonable(self, samples):
        rows = sweep_thresholds(samples, [0.5])
        r = rows[0]
        assert r["precision"] == 1.0
        assert r["recall"] == 1.0
        assert r["f1"] == 1.0

    def test_thresholds_monotonic_precision(self, samples):
        rows = sweep_thresholds(samples, [0.2, 0.4, 0.6, 0.8])
        precisions = [r["precision"] for r in rows]
        assert precisions == sorted(precisions)  # 阈值越高 precision 不降


class TestPickBest:
    def test_picks_f1_max(self, samples):
        rows = sweep_thresholds(samples, [0.2, 0.5, 0.8])
        best = pick_best(rows)
        assert best["f1"] == max(r["f1"] for r in rows)
