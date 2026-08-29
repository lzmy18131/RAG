"""构建版本化评测数据集（audit E1 / §9-10）。

读取 data/eval_dataset/*.json，规范化 schema 后写入 evals/datasets/*.jsonl，
并生成 dataset_version + dataset_hash + calibration/test split 元数据。

用法：python scripts/build_evals_datasets.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.eval.datasets import (  # noqa: E402
    DATASET_VERSIONS,
    dataset_hash_of,
    split_calibration_test,
)

# 规范化 schema（与 golden_100 一致；缺失字段补默认）
_REQUIRED = [
    "question",
    "question_type",
    "difficulty",
    "modality_required",
    "gold_pages",
    "reference_answer",
    "source_document",
]


def _normalize(item: dict) -> dict:
    return {
        "question": item.get("question", ""),
        "question_type": item.get("question_type", "unknown"),
        "difficulty": item.get("difficulty", "medium"),
        "modality_required": item.get("modality_required", "text"),
        "gold_pages": item.get("gold_pages", []),
        "reference_answer": item.get("reference_answer", item.get("reference_context", "")),
        "reference_contexts": item.get("reference_contexts", []),
        "source_document": item.get("source_document", ""),
        "review_status": item.get("review_status", "ai_annotated"),
        "answerable": item.get("answerable", True),
    }


def build(name: str, src: Path, out_dir: Path) -> dict:
    items = json.loads(src.read_text(encoding="utf-8"))
    norm = [_normalize(it) for it in items]
    version = DATASET_VERSIONS.get(name, "1.0.0")
    h = dataset_hash_of(norm)
    cal, test = split_calibration_test(norm, calibration_ratio=0.2, seed=42)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.jsonl").write_text(
        "\n".join(json.dumps(it, ensure_ascii=False) for it in norm) + "\n",
        encoding="utf-8",
    )
    meta = {
        "dataset_version": version,
        "dataset_hash": h,
        "total": len(norm),
        "calibration_size": len(cal),
        "test_size": len(test),
        "schema_fields": _REQUIRED,
        "note": "calibration/test split 用于阈值校准与最终评估分离（防 leakage）；小规模校准集为数据量限制下的折中，见 docs/evaluation.md",
    }
    (out_dir / f"{name}_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def main() -> int:
    out = PROJECT_ROOT / "evals" / "datasets"
    sources = {
        "golden_v1": PROJECT_ROOT / "data" / "eval_dataset" / "golden_100.json",
        "extended_v1": PROJECT_ROOT / "data" / "eval_dataset" / "golden_extended.json",
    }
    for name, src in sources.items():
        if not src.exists():
            print(f"SKIP {name}: 源文件不存在 {src}")
            continue
        meta = build(name, src, out)
        print(
            f"built {name}: {meta['total']} 条, hash={meta['dataset_hash']}, "
            f"cal={meta['calibration_size']}/test={meta['test_size']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
