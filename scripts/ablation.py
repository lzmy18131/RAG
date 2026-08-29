"""Ablation 汇总（audit E8 / §20）。

从各实验 run 的 artifacts 汇总 V0→V4 消融表：
    Recall@5 / MRR / nDCG / Faithfulness / Citation Accuracy / Latency p50/p95 / Cost

运行方式：
    make eval-ablation        # 离线：读取 runs/*/metrics.json 汇总
    python scripts/ablation.py --runs runs/v0_baseline runs/v3_rerank ...

说明：完整 pipeline 消融需要本地 BGE 模型 + Milvus 集合 + 真实 API（本环境 NOT RUN）；
      本脚本负责"统一指标计算与报告生成"，输入为各 run 的 per-query 结果。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.eval.retrieval_metrics import aggregate, evaluate_query  # noqa: E402

METRIC_ORDER = [
    "recall@5",
    "mrr",
    "ndcg@5",
    "top1_hit",
    "faithfulness",
    "citation_accuracy",
    "latency_p50",
    "latency_p95",
    "llm_calls",
    "estimated_cost_usd",
]


def _load_run_queries(run_dir: Path) -> list[dict]:
    """从 run 目录加载 per-query 结果（retrieval_results.jsonl 或 metrics.json 内嵌）。"""
    f = run_dir / "retrieval_results.jsonl"
    if f.exists():
        return [
            json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()
        ]
    m = run_dir / "metrics.json"
    if m.exists():
        data = json.loads(m.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "per_query" in data:
            return data["per_query"]
    return []


def _summarize_run(run_dir: Path) -> dict:
    """计算单 run 的统一指标表。"""
    queries = _load_run_queries(run_dir)
    summary: dict = {"run": run_dir.name, "queries": len(queries)}
    if not queries:
        summary["status"] = "NOT_RUN_NO_ARTIFACTS"
        return summary

    # 检索指标（若 per-query 有 ranked_ids + relevant_ids）
    evals = []
    for q in queries:
        if "ranked_ids" in q and "relevant_ids" in q:
            try:
                evals.append(evaluate_query(q["ranked_ids"], q["relevant_ids"]))
            except ValueError:
                continue
    if evals:
        agg = aggregate(evals)
        for k in ("recall@5", "mrr", "ndcg@5", "top1_hit"):
            summary[k] = agg.get(k)

    # 生成/引用指标（若存在）
    for key in ("faithfulness", "citation_accuracy"):
        vals = [q[key] for q in queries if key in q]
        if vals:
            summary[key] = round(sum(vals) / len(vals), 4)

    # 延迟分位（若 per-query 有 total_latency_ms）
    lat = sorted(q.get("total_latency_ms", 0.0) for q in queries if q.get("total_latency_ms"))
    if lat:
        summary["latency_p50"] = round(lat[len(lat) // 2], 1)
        summary["latency_p95"] = round(lat[int(len(lat) * 0.95) - 1], 1)

    summary["status"] = "OK"
    return summary


def render_markdown(runs_summary: list[dict]) -> str:
    lines = [
        "# Ablation Report\n",
        "| run | status | queries | recall@5 | mrr | ndcg@5 | faithfulness | citation | p50 | p95 |",
    ]
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for s in runs_summary:
        lines.append(
            f"| {s['run']} | {s.get('status')} | {s.get('queries', '-')} | "
            f"{s.get('recall@5', '-')} | {s.get('mrr', '-')} | {s.get('ndcg@5', '-')} | "
            f"{s.get('faithfulness', '-')} | {s.get('citation_accuracy', '-')} | "
            f"{s.get('latency_p50', '-')} | {s.get('latency_p95', '-')} |"
        )
    lines.append(
        "\n> 注：本表由 scripts/ablation.py 从各 run artifacts 汇总；"
        "完整 pipeline 消融需本地模型+API（见 README Running Evals）。"
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ablation summary")
    parser.add_argument(
        "--runs", nargs="*", default=[], help="run 目录列表；默认扫描 runs/ 下全部目录"
    )
    parser.add_argument("--out", default=str(PROJECT_ROOT / "reports" / "ablation.md"))
    args = parser.parse_args()

    runs_root = PROJECT_ROOT / "runs"
    run_dirs = [Path(r) for r in args.runs] if args.runs else sorted(runs_root.glob("*"))
    if not run_dirs:
        print("未找到任何 run 目录。运行完整评测（需模型）后重试；本环境离线 NOT RUN。")
        return 0

    summaries = [_summarize_run(d) for d in run_dirs if d.is_dir()]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(summaries), encoding="utf-8")
    print(render_markdown(summaries))
    print(f"\n报告已写入: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
