"""Eval foundation 测试：failures / stats / registry / datasets。"""

from __future__ import annotations

from src.eval.datasets import (
    content_hash,
    dataset_hash_of,
    split_calibration_test,
    validate_schema,
)
from src.eval.failures import classify, summarize
from src.eval.registry import dataset_hash, start_run
from src.eval.stats import bootstrap_ci, mcnemar_test


class TestFailures:
    def test_retrieval_miss(self):
        rec = {"num_relevant_retrieved": 0, "relevant_ids": ["x"]}
        assert classify(rec) == "RETRIEVAL_MISS"

    def test_hallucination(self):
        rec = {"support_ratio": 0.5, "support_threshold": 0.7}
        assert classify(rec) == "GENERATION_HALLUCINATION"

    def test_over_refusal(self):
        rec = {"expected_status": "answered", "final_status": "refused"}
        assert classify(rec) == "OVER_REFUSAL"

    def test_under_refusal(self):
        rec = {"expected_status": "refused", "final_status": "answered"}
        assert classify(rec) == "UNDER_REFUSAL"

    def test_citation_error(self):
        assert classify({"citation_correct": False}) == "CITATION_ERROR"

    def test_cache_false_hit(self):
        assert classify({"cache_hit": True, "cache_correct": False}) == "CACHE_FALSE_HIT"

    def test_priority_parser_over_generic(self):
        rec = {"parser_error": "bad pdf", "support_ratio": 0.2}
        assert classify(rec) == "PARSER_ERROR"

    def test_unknown_fallback(self):
        assert classify({"foo": 1}) == "UNKNOWN"

    def test_summarize(self):
        fails = [
            {"query": "q1", "category": "RETRIEVAL_MISS", "detail": ""},
            {"query": "q2", "category": "RETRIEVAL_MISS", "detail": ""},
            {"query": "q3", "category": "OVER_REFUSAL", "detail": ""},
        ]
        s = summarize(fails)
        assert s["total_failures"] == 3
        assert s["by_category"]["RETRIEVAL_MISS"] == 2


class TestStats:
    def test_bootstrap_ci_contains_mean(self):
        values = [0.8, 0.9, 0.7, 0.85, 0.95, 0.75, 0.88, 0.92, 0.78, 0.9]
        ci = bootstrap_ci(values, n_boot=200, seed=1)
        assert ci["ci_low"] <= ci["mean"] <= ci["ci_high"]

    def test_bootstrap_reproducible(self):
        values = [0.1, 0.2, 0.3, 0.4, 0.5]
        a = bootstrap_ci(values, n_boot=100, seed=7)
        b = bootstrap_ci(values, n_boot=100, seed=7)
        assert a == b

    def test_mcnemar_significant(self):
        # A 错 B 对 = 8；A 对 B 错 = 0 → B 显著更好
        pairs = [(True, True)] * 10 + [(False, True)] * 8 + [(True, False)] * 0
        r = mcnemar_test(pairs)
        assert r["better"] == "b"
        assert r["significant"] is True

    def test_mcnemar_tie(self):
        r = mcnemar_test([(True, True)] * 10)
        assert r["better"] == "tie"
        assert r["significant"] is False


class TestRegistry:
    def test_start_run_creates_metadata(self, tmp_path, monkeypatch):
        from src.eval import registry

        monkeypatch.setattr(registry, "_RUNS_ROOT", tmp_path / "runs")
        run = start_run(
            dataset_version="golden_v1",
            dataset_hash_val="abc123",
            corpus_version="corpus-v1",
            config={"pipeline": "v3_rerank", "top_k": 5},
            notes="unit test",
        )
        d = run.save()
        assert (d / "metadata.json").exists()
        assert (d / "config.yaml").exists()
        assert (d / "metrics.json").exists()

    def test_dataset_hash_deterministic(self, tmp_path):
        f1 = tmp_path / "a.jsonl"
        f1.write_text("line1\nline2\n", encoding="utf-8")
        h1 = dataset_hash([f1])
        assert h1 == dataset_hash([f1])  # 确定性
        f1.write_text("line1\nline2\nCHANGED\n", encoding="utf-8")
        assert h1 != dataset_hash([f1])  # 内容变化哈希变化


class TestDatasets:
    def test_content_hash(self):
        assert content_hash("abc") == content_hash("abc")
        assert content_hash("abc") != content_hash("abd")

    def test_split_preserves_all(self):
        items = [{"id": i} for i in range(20)]
        cal, test = split_calibration_test(items, calibration_ratio=0.2, seed=1)
        assert len(cal) == 4
        assert len(test) == 16
        assert len(cal) + len(test) == 20

    def test_split_no_overlap(self):
        items = [{"id": i} for i in range(30)]
        cal, test = split_calibration_test(items, seed=3)
        cal_ids = {x["id"] for x in cal}
        test_ids = {x["id"] for x in test}
        assert cal_ids.isdisjoint(test_ids)

    def test_validate_schema(self):
        item = {"question": "q", "answer": "a"}
        missing = validate_schema(item, ["question", "answer", "gold_pages"])
        assert missing == ["gold_pages"]

    def test_dataset_hash_of(self):
        items = [{"q": "1"}, {"q": "2"}]
        assert dataset_hash_of(items) == dataset_hash_of(items)
