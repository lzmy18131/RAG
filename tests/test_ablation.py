"""Ablation 汇总与数据集构建集成测试。"""

from __future__ import annotations

import json

import pytest

from scripts.ablation import _summarize_run, render_markdown


@pytest.fixture()
def fake_run_dir(tmp_path):
    d = tmp_path / "v3_rerank"
    d.mkdir()
    lines = []
    for i, relevant_pos in enumerate([0, 1, 3]):
        ranked = [f"c{i}_{j}" for j in range(5)]
        ranked.insert(relevant_pos, "GOLD")
        ranked.pop()
        lines.append(
            json.dumps(
                {
                    "query": f"q{i}",
                    "ranked_ids": ranked,
                    "relevant_ids": ["GOLD"],
                    "faithfulness": 0.9,
                    "citation_accuracy": 0.8,
                    "total_latency_ms": 3000.0,
                },
                ensure_ascii=False,
            )
        )
    (d / "retrieval_results.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


def test_summarize_run_with_artifacts(fake_run_dir):
    s = _summarize_run(fake_run_dir)
    assert s["status"] == "OK"
    assert s["queries"] == 3
    assert s["mrr"] == pytest.approx((1.0 + 0.5 + 0.25) / 3, rel=1e-2)  # rank1, rank2, rank4
    assert s["recall@5"] == 1.0
    assert s["faithfulness"] == pytest.approx(0.9)
    assert s["latency_p50"] == 3000.0


def test_summarize_run_no_artifacts(tmp_path):
    s = _summarize_run(tmp_path / "empty_run")
    assert s["status"] == "NOT_RUN_NO_ARTIFACTS"


def test_render_markdown(fake_run_dir):
    s = [_summarize_run(fake_run_dir)]
    md = render_markdown(s)
    assert "# Ablation Report" in md
    assert "| v3_rerank |" in md
    assert "0.9" in md  # faithfulness
