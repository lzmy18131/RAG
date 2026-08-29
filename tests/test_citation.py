"""确定性引用校验测试（audit E5 / §14）。"""

from __future__ import annotations

import pytest

from src.eval.citation import SUPPORTED, UNCONFIRMED, UNMATCHED, CitationValidator


def _validator(**kw):
    defaults = dict(
        document_pages={"manual.pdf": 27, "manual2.pdf": 30},
        retrieved_sources={"manual.pdf"},
        retrieved_chunk_ids={"c1", "c2"},
    )
    defaults.update(kw)
    return CitationValidator(**defaults)


class TestCitationValidator:
    def test_supported_citation(self):
        v = _validator()
        cc = v.check("[来源: manual.pdf, 第5页]")
        assert cc.status == SUPPORTED

    def test_page_out_of_range(self):
        v = _validator()
        cc = v.check("[来源: manual.pdf, 第99页]")
        assert cc.status == UNMATCHED
        assert "超出" in cc.reason

    def test_unknown_source(self):
        v = _validator()
        cc = v.check("[来源: other.pdf, 第1页]")
        assert cc.status == UNMATCHED

    def test_source_not_retrieved(self):
        v = _validator()
        cc = v.check("[来源: manual2.pdf, 第1页]")  # manual2 未在检索结果
        assert cc.status == UNCONFIRMED

    def test_unparseable(self):
        v = _validator()
        cc = v.check("没有引用格式")
        assert cc.status == UNMATCHED

    def test_evidence_insufficient(self):
        v = _validator(
            retrieved_sources={"manual.pdf"},
            grounding_map={"manual.pdf": 0.1},
            grounding_threshold=0.3,
        )
        cc = v.check("[来源: manual.pdf, 第5页]")
        assert cc.status == UNMATCHED
        assert "支撑不足" in cc.reason

    def test_evidence_sufficient(self):
        v = _validator(
            retrieved_sources={"manual.pdf"},
            grounding_map={"manual.pdf": 0.8},
            grounding_threshold=0.3,
        )
        cc = v.check("[来源: manual.pdf, 第5页]")
        assert cc.status == SUPPORTED

    def test_summarize_accuracy(self):
        v = _validator()
        checks = [
            v.check("[来源: manual.pdf, 第5页]"),  # supported
            v.check("[来源: manual.pdf, 第99页]"),  # unmatched
            v.check("[来源: manual2.pdf, 第1页]"),  # unconfirmed
        ]
        s = v.summarize(checks)
        assert s["total_citations"] == 3
        assert s[SUPPORTED] == 1
        assert s[UNMATCHED] == 1
        assert s[UNCONFIRMED] == 1
        assert s["citation_accuracy"] == pytest.approx(1 / 3, rel=1e-3)
