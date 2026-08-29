"""
数据集版本化与切分（audit E1 / 任务书 §9-11）。

- golden/extended/adversarial 数据集带 dataset_version + hash。
- calibration/test 切分：防止在最终 test set 上反复调参（leakage 防护）。
- 数据量不足时使用小规模 calibration split 并明确记录局限。
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

_DATASETS_DIR = Path(__file__).resolve().parents[2] / "evals" / "datasets"

# 数据集版本登记（修改数据集必须递增版本）
DATASET_VERSIONS: dict[str, str] = {
    "golden_v1": "1.0.0",
    "extended_v1": "1.0.0",
    "adversarial_v1": "1.0.0",
}


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_dataset(name: str, base_dir: str | Path | None = None) -> list[dict]:
    """加载 evals/datasets/<name>.jsonl；返回记录列表。"""
    base = Path(base_dir) if base_dir else _DATASETS_DIR
    p = base / f"{name}.jsonl"
    if not p.exists():
        raise FileNotFoundError(f"数据集不存在: {p}（先运行 scripts/build_evals_datasets.py）")
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def dataset_hash_of(items: list[dict]) -> str:
    """对记录列表算内容哈希（顺序敏感）。"""
    h = hashlib.sha256()
    for it in items:
        h.update(json.dumps(it, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def split_calibration_test(
    items: list[dict],
    calibration_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """按 id 分层切分为 calibration / test。

    说明：用于 threshold/参数校准（calibration）与最终评估（test）分离，
    防止 leakage。数据量有限时为小规模校准集，局限见 docs/evaluation.md。
    """
    if not items:
        return [], []
    rng = random.Random(seed)
    shuffled = list(items)
    rng.shuffle(shuffled)
    n_cal = max(1, int(len(shuffled) * calibration_ratio))
    return shuffled[:n_cal], shuffled[n_cal:]


def validate_schema(item: dict, required: list[str]) -> list[str]:
    """校验单条记录是否含必需字段，返回缺失列表。"""
    return [f for f in required if f not in item]
