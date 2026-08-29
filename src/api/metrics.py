"""
进程内指标（audit O2 / 任务书 §63）。

Prometheus 文本格式 /metrics；计数器/仪表；无外部依赖。
避免高基数 label（不使用 query/request_id/document_id 作为 label）。
"""

from __future__ import annotations

import threading
from collections import defaultdict


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def inc(self, name: str, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        key = (name, _label_tuple(labels))
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = (name, _label_tuple(labels))
        with self._lock:
            self._gauges[key] = value

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name}{_fmt_labels(labels)} {int(value)}")
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name}{_fmt_labels(labels)} {value}")
        return "\n".join(lines) + "\n"

    def snapshot_count(self, name: str, labels: dict[str, str] | None = None) -> float:
        """读取指定计数器当前值（测试/诊断用）。"""
        key = (name, _label_tuple(labels))
        with self._lock:
            return self._counters.get(key, 0.0)


def _label_tuple(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((labels or {}).items()))


def _fmt_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    return "{" + ",".join(f'{k}="{v}"' for k, v in labels) + "}"


metrics = MetricsCollector()


# ── 便捷计数器（命名约定）──


def inc_http_request(method: str, path: str, status: int) -> None:
    metrics.inc("http_requests_total", {"method": method, "path": path, "status": str(status)})


def inc_rag_request(status: str = "ok") -> None:
    metrics.inc("rag_requests_total", {"status": status})


def inc_cache_hit(kind: str = "exact") -> None:
    metrics.inc("cache_hits_total", {"kind": kind})


def inc_cache_miss() -> None:
    metrics.inc("cache_misses_total")


def inc_cache_false_hit() -> None:
    metrics.inc("cache_false_hits_total")


def inc_grounding_rejection() -> None:
    metrics.inc("grounding_rejections_total")


def inc_provider_failure(provider: str = "primary") -> None:
    metrics.inc("provider_failures_total", {"provider": provider})


def inc_ingestion(status: str = "ok") -> None:
    metrics.inc("ingestion_documents_total", {"status": status})
