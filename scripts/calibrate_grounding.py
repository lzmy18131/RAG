"""
Grounding 阈值校准（audit R4 / 任务书 §16）。

对带标签的样本（句级 grounding_score + 是否真实可支撑）扫描阈值，
输出 threshold → precision / recall / F1 / abstain_rate / coverage，
并用 calibration split 选取最终阈值（不得在 test set 上调参）。

输入格式（JSONL）：{"score": 0.72, "supported": true|false}
用法：
    python scripts/calibrate_grounding.py --data evals/datasets/grounding_calibration.jsonl
    python scripts/calibrate_grounding.py --data ... --thresholds 0.1 0.3 0.5 0.7 0.9
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def sweep_thresholds(
    samples: list[dict],
    thresholds: list[float],
) -> list[dict]:
    """扫描阈值：预测 = score >= threshold（supported），否则 abstain。

    标签解释：
    - 真阳性 TP：预测 supported 且真实 supported
    - 假阳性 FP：预测 supported 但真实 unsupported（幻觉漏网）
    - 真阴性 TN：预测 abstain 且真实 unsupported（正确拒答）
    - 假阴性 FN：预测 abstain 但真实 supported（过度拒答）
    """
    rows = []
    for thr in thresholds:
        tp = fp = tn = fn = 0
        for s in samples:
            pred = s["score"] >= thr
            truth = bool(s["supported"])
            if pred and truth:
                tp += 1
            elif pred and not truth:
                fp += 1
            elif not pred and not truth:
                tn += 1
            else:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        total = tp + fp + tn + fn
        rows.append(
            {
                "threshold": round(thr, 2),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "abstain_rate": round((tn + fn) / total, 4) if total else 0.0,
                "coverage": round((tp + fp) / total, 4) if total else 0.0,
                "tp": tp,
                "fp": fp,
                "tn": tn,
                "fn": fn,
            }
        )
    return rows


def pick_best(rows: list[dict], prefer: str = "f1") -> dict:
    """选择最优阈值（默认按 F1；可换 precision 或 coverage）。"""
    return max(rows, key=lambda r: r.get(prefer, 0.0))


def main() -> int:
    parser = argparse.ArgumentParser(description="Grounding threshold calibration")
    parser.add_argument("--data", required=True, help="标签样本 JSONL 路径")
    parser.add_argument(
        "--thresholds", nargs="*", type=float, default=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    )
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    samples = [
        json.loads(line)
        for line in Path(args.data).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not samples:
        print(f"样本为空: {args.data}")
        return 1

    rows = sweep_thresholds(samples, args.thresholds)
    print(f"{'threshold':>10}{'precision':>10}{'recall':>8}{'f1':>8}{'abstain':>9}{'coverage':>9}")
    for r in rows:
        print(
            f"{r['threshold']:>10.2f}{r['precision']:>10.4f}{r['recall']:>8.4f}"
            f"{r['f1']:>8.4f}{r['abstain_rate']:>9.4f}{r['coverage']:>9.4f}"
        )
    best = pick_best(rows)
    print(
        f"\n最优（按 F1）: threshold={best['threshold']} f1={best['f1']} "
        f"precision={best['precision']} recall={best['recall']} abstain={best['abstain_rate']}"
    )

    if args.out:
        Path(args.out).write_text(
            json.dumps(
                {"samples": len(samples), "sweep": rows, "best": best}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        print(f"报告已写入: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
