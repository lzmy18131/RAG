"""
分阶段延迟测量（audit E9 / 任务书 §21）。

回答"V3 为什么从 3s 变 20s"：pipeline 各阶段（parse/embedding/dense/bm25/fusion/
rerank/generation/grounding/total）独立计时，支持 p50/p90/p95/max 分位数。

用法：
    timer = StageTimer()
    with timer.stage("dense"):
        ...
    timer.snapshot() -> {"dense_ms": 12.3, ...}
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterator
from contextlib import contextmanager


def percentiles(values: list[float], ps: tuple[float, ...] = (50, 90, 95)) -> dict:
    """计算分位数（nearest-rank 方法，NaN 安全）。"""
    vals = sorted(v for v in values if v == v)
    if not vals:
        return {}
    n = len(vals)
    out = {}
    for p in ps:
        rank = max(1, math.ceil(p / 100 * n))
        out[f"p{int(p)}"] = round(vals[rank - 1], 1)
    out["max"] = round(vals[-1], 1)
    out["count"] = n
    return out


class StageTimer:
    """分阶段计时器：累计各阶段耗时（多次执行取平均）。"""

    def __init__(self) -> None:
        self._totals: dict[str, float] = {}
        self._counts: dict[str, int] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self._totals[name] = self._totals.get(name, 0.0) + (time.perf_counter() - t0) * 1000
            self._counts[name] = self._counts.get(name, 0) + 1

    def stage_ms(self, name: str) -> float:
        """某阶段累计毫秒。"""
        return round(self._totals.get(name, 0.0), 1)

    def snapshot(self) -> dict:
        """各阶段平均耗时（ms）+ total。"""
        out = {}
        total = 0.0
        for name, ms in sorted(self._totals.items()):
            avg = ms / self._counts.get(name, 1)
            out[f"{name}_ms"] = round(avg, 1)
            total += avg
        out["total_ms"] = round(total, 1)
        return out

    def reset(self) -> None:
        self._totals.clear()
        self._counts.clear()


class LatencyRecorder:
    """跨 query 的延迟记录：按阶段累计，供 p50/p95 统计。"""

    def __init__(self) -> None:
        self._by_stage: dict[str, list[float]] = {}

    def record(self, stage: str, ms: float) -> None:
        self._by_stage.setdefault(stage, []).append(ms)

    def snapshot(self) -> dict:
        return {stage: percentiles(vals) for stage, vals in self._by_stage.items()}
