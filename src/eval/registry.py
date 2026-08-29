"""
Experiment Registry（audit E2 / 任务书 §8）。

每次实验在 runs/ 下生成独立目录：
    runs/<run_id>/
        config.yaml        # 实验配置快照
        metadata.json      # run_id/timestamp/git_commit/dataset_version/hash/模型/参数
        metrics.json       # 量化指标（retrieval/generation/latency/cost）
        failures.jsonl     # 失败记录（见 failures.py）
        report.md          # 人工/自动摘要

保证：README 中每张性能表都能追溯到一个 run_id。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RUNS_ROOT = Path(__file__).resolve().parents[2] / "runs"


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "no-git"
    except Exception:  # noqa: BLE001
        return "no-git"


@dataclass
class ExperimentRun:
    """一次实验的注册信息。"""

    run_id: str
    timestamp: str
    git_commit: str
    dataset_version: str
    dataset_hash: str
    corpus_version: str
    config: dict[str, Any]
    metrics: dict[str, Any] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)
    notes: str = ""

    @property
    def dir(self) -> Path:
        return _RUNS_ROOT / self.run_id

    def save(self) -> Path:
        d = self.dir
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.yaml").write_text(
            json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (d / "metadata.json").write_text(
            json.dumps(
                {
                    "run_id": self.run_id,
                    "timestamp": self.timestamp,
                    "git_commit": self.git_commit,
                    "dataset_version": self.dataset_version,
                    "dataset_hash": self.dataset_hash,
                    "corpus_version": self.corpus_version,
                    "notes": self.notes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (d / "metrics.json").write_text(
            json.dumps(self.metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if self.failures:
            (d / "failures.jsonl").write_text(
                "\n".join(json.dumps(f, ensure_ascii=False) for f in self.failures),
                encoding="utf-8",
            )
        return d


def dataset_hash(paths: list[str | Path]) -> str:
    """数据集内容哈希（dataset 版本校验）。"""
    h = hashlib.sha256()
    for p in paths:
        pp = Path(p)
        if not pp.exists():
            h.update(f"missing:{pp.name}".encode())
            continue
        h.update(f"file:{pp.name}:".encode())
        h.update(pp.read_bytes())
    return h.hexdigest()[:16]


def start_run(
    dataset_version: str,
    dataset_hash_val: str,
    corpus_version: str,
    config: dict[str, Any],
    notes: str = "",
) -> ExperimentRun:
    """创建新实验 run。"""
    ts = datetime.now(UTC).isoformat(timespec="seconds")
    run_id = (
        ts.replace("-", "").replace(":", "").replace("+", "")[:14]
        + "_"
        + (config.get("pipeline", "run"))
    )
    return ExperimentRun(
        run_id=run_id,
        timestamp=ts,
        git_commit=_git_commit(),
        dataset_version=dataset_version,
        dataset_hash=dataset_hash_val,
        corpus_version=corpus_version,
        config=config,
        notes=notes,
    )
