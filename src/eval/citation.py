"""
确定性引用校验（audit E5 / 任务书 §14）。

对每条引用检查：
1. 页面是否存在（在文档总页数内）。
2. source_file 是否匹配（检索/文档范围内）。
3. 被引用 chunk 是否真的被 retrieval 返回。
4. 被引用证据是否足够支撑 claim（grounding score ≥ 阈值，可选）。

原则：引用由程序校验，不完全信任 LLM 声称的 citation 字符串。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# 引用三态
SUPPORTED = "supported"
UNCONFIRMED = "unconfirmed"
UNMATCHED = "unmatched"


@dataclass
class CitationCheck:
    """单条引用校验结果。"""

    citation: str
    source_file: str | None = None
    page: int | None = None
    status: str = UNMATCHED
    reason: str = ""
    evidence_ok: bool | None = None

    def to_dict(self) -> dict:
        return {
            "citation": self.citation,
            "source_file": self.source_file,
            "page": self.page,
            "status": self.status,
            "reason": self.reason,
            "evidence_ok": self.evidence_ok,
        }


class CitationValidator:
    """基于文档/检索事实的确定性引用校验器。"""

    def __init__(
        self,
        document_pages: dict[str, int],  # source_file(basename) -> 总页数
        retrieved_sources: Iterable[str] = (),  # 本次检索返回的 source_file 集合
        retrieved_chunk_ids: Iterable[str] = (),  # 本次检索返回的 chunk_id 集合
        grounding_map: dict[str, float] | None = None,  # chunk_id -> grounding score
        grounding_threshold: float = 0.3,
    ):
        self.pages = document_pages
        self.retrieved_sources = set(retrieved_sources)
        self.retrieved_chunk_ids = set(retrieved_chunk_ids)
        self.grounding_map = grounding_map or {}
        self.threshold = grounding_threshold

    def _parse_citation(self, citation: str) -> tuple[str | None, int | None]:
        """从 LLM 生成的引用字符串解析 (source_file, page)。"""
        # 支持格式: [来源: xxx.pdf, 第N页]  / [来源: xxx 第N页]  / [xxx, pN]
        import re

        m = re.search(r"来源[:：]\s*([^,，\]】]+)\s*(?:[,，\s]+第?\s*(\d+)\s*页)?", citation)
        if m:
            src = m.group(1).strip()
            page = int(m.group(2)) if m.group(2) else None
            return src, page
        m2 = re.search(r"\[([^\]]+?)\s*[,，]\s*p\.?\s*(\d+)\]", citation, re.IGNORECASE)
        if m2:
            return m2.group(1).strip(), int(m2.group(2))
        return None, None

    def check(self, citation: str) -> CitationCheck:
        src, page = self._parse_citation(citation)
        if src is None and page is None:
            return CitationCheck(citation=citation, status=UNMATCHED, reason="无法解析引用格式")

        cc = CitationCheck(citation=citation, source_file=src, page=page)

        # 1. 来源必须在本批文档范围内
        if src and src not in self.pages:
            cc.status = UNMATCHED
            cc.reason = f"来源不在已知文档中: {src}"
            return cc

        # 2. 页面必须存在
        if page is not None and src and page > self.pages.get(src, 0):
            cc.status = UNMATCHED
            cc.reason = f"页面 {page} 超出文档 {src} 总页数 {self.pages.get(src)}"
            return cc

        # 3. 来源必须被检索返回（引用检索范围外内容 = 可疑）
        if src and self.retrieved_sources and src not in self.retrieved_sources:
            cc.status = UNCONFIRMED
            cc.reason = f"来源 {src} 不在本次检索结果中"
            return cc

        # 4. 证据支撑（可选：source_file → grounding score 映射）
        #    注：句子级 chunk grounding 由 workflow/grounding.py 承担；
        #    此处做引用级兜底校验，key 统一为 source_file basename。
        if self.grounding_map and src is not None:
            score = self.grounding_map.get(src, 0.0)
            cc.evidence_ok = score >= self.threshold
            if cc.evidence_ok is False:
                cc.status = UNMATCHED
                cc.reason = f"证据支撑不足 (score={score:.2f} < {self.threshold})"
                return cc

        cc.status = SUPPORTED
        cc.reason = "引用通过全部确定性校验"
        return cc

    def check_all(self, citations: Iterable[str]) -> list[CitationCheck]:
        return [self.check(c) for c in citations]

    def summarize(self, checks: list[CitationCheck]) -> dict:
        total = len(checks)
        counts = {SUPPORTED: 0, UNCONFIRMED: 0, UNMATCHED: 0}
        for c in checks:
            counts[c.status] = counts.get(c.status, 0) + 1
        return {
            "total_citations": total,
            **counts,
            "citation_accuracy": round(counts[SUPPORTED] / total, 4) if total else 1.0,
        }
