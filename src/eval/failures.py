"""
RAG 失败分类（audit E6 / 任务书 §18）。

评测失败自动归因到可操作的类别，输出 failures.jsonl 与汇总表。
分类器为确定性规则，基于一次评测记录的字段（retrieval/generation/grounding/citation/cache/provider）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 失败类别枚举（全项目统一）
FAILURE_CATEGORIES = {
    "RETRIEVAL_MISS": "检索未返回任何相关 chunk",
    "RANKING_ERROR": "相关 chunk 被排到不相关之后",
    "RERANKER_REGRESSION": "Reranker 使原本靠前的相关 chunk 掉出 top-k",
    "CONTEXT_TRUNCATION": "上下文被截断导致证据丢失",
    "GENERATION_HALLUCINATION": "生成内容无证据支撑",
    "CITATION_ERROR": "引用指向不存在的页面/来源，或证据不足",
    "OVER_REFUSAL": "本可回答却拒答",
    "UNDER_REFUSAL": "应拒答却作答",
    "PARSER_ERROR": "文档解析失败",
    "IMAGE_UNDERSTANDING_ERROR": "图片理解失败",
    "CACHE_FALSE_HIT": "语义缓存错命中返回陈旧/错误答案",
    "MODEL_PROVIDER_ERROR": "LLM/VLM provider 不可用",
    "UNKNOWN": "无法归因",
}

# 判定优先级（返回第一个命中的类别；UNKNOWN 兜底）
from collections.abc import Callable

_CLASSIFIERS: list[tuple[str, Callable[[dict], str]]] = []


def _register(category: str):
    def deco(fn):
        _CLASSIFIERS.append((category, fn))
        return fn

    return deco


@_register("PARSER_ERROR")
def _parser_error(rec: dict) -> bool:
    return bool(rec.get("parser_error") or rec.get("error_type") == "PARSER_ERROR")


@_register("MODEL_PROVIDER_ERROR")
def _provider_error(rec: dict) -> bool:
    return bool(rec.get("provider_error") or rec.get("error_type") == "MODEL_PROVIDER_ERROR")


@_register("CACHE_FALSE_HIT")
def _cache_false_hit(rec: dict) -> bool:
    return bool(rec.get("cache_hit") and rec.get("cache_correct") is False)


@_register("RETRIEVAL_MISS")
def _retrieval_miss(rec: dict) -> bool:
    return rec.get("num_relevant_retrieved", 0) == 0 and bool(rec.get("relevant_ids"))


@_register("CITATION_ERROR")
def _citation_error(rec: dict) -> bool:
    return rec.get("citation_correct") is False or rec.get("citation_error_count", 0) > 0


@_register("GENERATION_HALLUCINATION")
def _hallucination(rec: dict) -> bool:
    return rec.get("support_ratio", 1.0) < (rec.get("support_threshold", 0.7))


@_register("UNDER_REFUSAL")
def _under_refusal(rec: dict) -> bool:
    return rec.get("expected_status") == "refused" and rec.get("final_status") == "answered"


@_register("OVER_REFUSAL")
def _over_refusal(rec: dict) -> bool:
    return rec.get("expected_status") == "answered" and rec.get("final_status") == "refused"


@_register("RERANKER_REGRESSION")
def _reranker_regression(rec: dict) -> bool:
    return bool(rec.get("reranker_regressed_ids"))


@_register("RANKING_ERROR")
def _ranking_error(rec: dict) -> bool:
    # 有相关 chunk 被检索到但排位过低（MRR 低且非 miss）
    mrr = rec.get("mrr", 1.0)
    num_rel = rec.get("num_relevant_retrieved", 1)
    return num_rel > 0 and mrr < (rec.get("mrr_threshold", 0.5))


@dataclass
class FailureRecord:
    """单条失败记录（写入 failures.jsonl）。"""

    query: str
    category: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "category": self.category,
            "detail": self.detail,
            **self.metadata,
        }


def classify(record: dict) -> str:
    """按优先级判定失败类别。"""
    for category, fn in _CLASSIFIERS:
        try:
            if fn(record):
                return category
        except Exception:  # noqa: BLE001 - 分类器绝不允许抛错
            continue
    return "UNKNOWN"


def summarize(failures: list[dict]) -> dict:
    """失败汇总表：类别 -> 计数。"""
    counts: dict[str, int] = {c: 0 for c in FAILURE_CATEGORIES}
    for f in failures:
        counts[f["category"]] = counts.get(f["category"], 0) + 1
    total = len(failures)
    return {
        "total_failures": total,
        "by_category": {k: v for k, v in sorted(counts.items(), key=lambda x: -x[1]) if v},
        "failure_rate": round(total / max(total, 1), 4),
    }
