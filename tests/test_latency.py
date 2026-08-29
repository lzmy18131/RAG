"""分阶段延迟测试（audit E9 / §21）。"""

from __future__ import annotations

import time

import pytest

from src.eval.latency import LatencyRecorder, StageTimer, percentiles


class TestPercentiles:
    def test_basic(self):
        r = percentiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], ps=(50, 90))
        assert r["p50"] == 5.0
        assert r["p90"] == 9.0
        assert r["max"] == 10.0
        assert r["count"] == 10

    def test_empty(self):
        assert percentiles([]) == {}

    def test_single(self):
        r = percentiles([7.5])
        assert r["p50"] == 7.5
        assert r["max"] == 7.5


class TestStageTimer:
    def test_measures_stage(self):
        timer = StageTimer()
        with timer.stage("dense"):
            time.sleep(0.01)
        assert timer.stage_ms("dense") >= 5.0

    def test_multiple_stages_snapshot(self):
        timer = StageTimer()
        with timer.stage("dense"):
            time.sleep(0.005)
        with timer.stage("rerank"):
            time.sleep(0.005)
        snap = timer.snapshot()
        assert "dense_ms" in snap
        assert "rerank_ms" in snap
        assert "total_ms" in snap
        assert snap["total_ms"] == pytest.approx(snap["dense_ms"] + snap["rerank_ms"], rel=1e-3)

    def test_average_across_runs(self):
        timer = StageTimer()
        for _ in range(3):
            with timer.stage("gen"):
                time.sleep(0.002)
        snap = timer.snapshot()
        assert snap["gen_ms"] >= 1.0  # 平均而非累计


class TestLatencyRecorder:
    def test_record_and_snapshot(self):
        rec = LatencyRecorder()
        rec.record("dense", 10)
        rec.record("dense", 20)
        rec.record("dense", 30)
        snap = rec.snapshot()
        assert snap["dense"]["p50"] == 20.0
        assert snap["dense"]["p90"] == 30.0
        assert snap["dense"]["max"] == 30.0
