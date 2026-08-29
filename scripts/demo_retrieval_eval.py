"""Demo Mode 检索评估（离线、无 API key / GPU / 模型下载）。

在合成硬件手册语料上运行**真实** Hybrid(BGE-like→BM25→RRF)→Rerank 管线，
用统一指标模块（src/eval/retrieval_metrics）计算 Recall@K / MRR / nDCG，
并通过 Experiment Registry（runs/demo_retrieval_v1/）注册 run。

用途：
- CI 的确定性离线回归（PR 不调用真实 LLM / 模型）。
- Demo Mode 的可复现基准（README 可追溯 run_id）。
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DEMO_MODE", "true")

from src.eval.registry import ExperimentRun  # noqa: E402
from src.eval.retrieval_metrics import aggregate, evaluate_query  # noqa: E402

# ── Golden demo queries：query → 期望 chunk_ids（人工核验自合成语料） ──
GOLDEN_QUERIES: list[dict] = [
    {"query": "故障码 E01 是什么意思", "expected": ["demo-0003", "demo-0004"]},
    {"query": "E07 尘盒未安装怎么办", "expected": ["demo-0006", "demo-0004"]},
    {"query": "边刷缠绕了怎么办", "expected": ["demo-0005", "demo-0017"]},
    {"query": "PTC 过热保护怎么处理", "expected": ["demo-0007"]},
    {"query": "机器人会不会从楼梯摔下去", "expected": ["demo-0013", "demo-0012"]},
    {"query": "如何清理边刷", "expected": ["demo-0017", "demo-0005"]},
    {"query": "电池容量和续航时间", "expected": ["demo-0009"]},
    {"query": "怎么进入配网模式", "expected": ["demo-0019", "demo-0011"]},
    {"query": "HEPA 滤网怎么更换", "expected": ["demo-0018"]},
    {"query": "如何给机器人充电", "expected": ["demo-0010", "demo-0001"]},
    {"query": "悬崖传感器防跌落", "expected": ["demo-0013", "demo-0012"]},
    {"query": "强力模式续航多久", "expected": ["demo-0015"]},
]

RUN_ID = "demo_retrieval_v1"


def main() -> int:
    from src.api.deps import get_bm25, get_reranker
    from src.infra.demo import (
        DEMO_COLLECTION,
        DEMO_CORPUS,
        FakeEmbedder,
        FakeMilvusClient,
    )

    # demo 模式：强制内存组件（脚本独立于 app env）
    embedder = FakeEmbedder()
    milvus: FakeMilvusClient = FakeMilvusClient()
    milvus.seed(DEMO_COLLECTION, DEMO_CORPUS, embedder)
    bm25 = get_bm25()
    reranker = get_reranker()

    from src.retrieval.reranked_retriever import RerankedRetriever

    retriever = RerankedRetriever(
        collection_name=DEMO_COLLECTION,
        reranker=reranker,
        embedder=embedder,
        bm25=bm25,
        client=milvus,
    )

    # ── 检索评估 ──
    per_query: list[dict] = []
    for item in GOLDEN_QUERIES:
        results = retriever.search(item["query"], top_k=5, mode="reranked")
        ranked_ids = [c.get("chunk_id", "") for c in results]
        metrics = evaluate_query(ranked_ids, item["expected"])
        per_query.append(
            {
                "query": item["query"],
                "ranked_ids": ranked_ids,
                "expected": item["expected"],
                **metrics,
            }
        )

    agg = aggregate(per_query)  # 每行来自 evaluate_query，键一致

    # ── 语义缓存 benchmark（重复/近似查询命中率 + 假阳性） ──
    from src.infra.semantic_cache import SemanticCache

    cache = SemanticCache(embedder=embedder, db_path=str(PROJECT_ROOT / "storage" / "demo_cache.db"), threshold=0.9)
    exact_hits, semantic_hits, misses = 0, 0, 0
    for item in GOLDEN_QUERIES:
        cache.put(item["query"], {"answer": "demo", "status": "answered"})
    for item in GOLDEN_QUERIES:
        hit = cache.get(item["query"])
        if hit:
            exact_hits += 1
    paraphrase = "故障码 E01 是什么意思？"
    hit = cache.get(paraphrase)
    if hit:
        semantic_hits += 1
    unrelated = cache.get("如何登录火星")
    false_hit = 1 if unrelated is not None else 0
    misses = len(GOLDEN_QUERIES) - exact_hits

    metrics = {
        "retrieval": agg,
        "n_queries": len(GOLDEN_QUERIES),
        "cache": {
            "exact_hits": exact_hits,
            "semantic_hits": semantic_hits,
            "misses": misses,
            "false_hit_rate": round(false_hit / len(GOLDEN_QUERIES), 4),
        },
    }

    # ── Experiment Registry ──
    run = ExperimentRun(
        run_id=RUN_ID,
        timestamp=datetime.now(UTC).isoformat(),
        git_commit=_git_commit(),
        dataset_version="demo_golden_v1",
        dataset_hash=_hash_queries(GOLDEN_QUERIES),
        corpus_version="demo-corpus-v1",
        config={
            "pipeline": "hybrid(bge-like+bm25+rrf)+rerank",
            "corpus": "data/demo synthetic manual (20 chunks)",
            "reranker": "demo-lexical-overlap",
            "embedder": "demo-hash-bow-64d",
            "top_k": 5,
        },
        metrics=metrics,
        notes="Demo Mode 确定性检索基准（CI 离线回归；非真实模型 benchmark）",
    )
    run.save()

    report = _render_report(agg, metrics)
    (run.dir / "report.md").write_text(report, encoding="utf-8")

    print(f"run registered: {run.dir}")
    print(f"Recall@5={agg.get('recall@5')} MRR={agg.get('mrr')} nDCG@5={agg.get('ndcg@5')} "
          f"cache_exact={exact_hits} false_hit_rate={metrics['cache']['false_hit_rate']}")
    return 0


def _git_commit() -> str:
    import subprocess

    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "no-git"
    except Exception:  # noqa: BLE001
        return "no-git"


def _hash_queries(queries: list[dict]) -> str:
    import hashlib
    import json

    raw = json.dumps(queries, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _render_report(agg: dict, metrics: dict) -> str:
    lines = [
        f"# Demo Retrieval Eval ({RUN_ID})",
        "",
        "> Demo Mode 确定性基准：合成硬件手册语料（20 chunks）+ Hybrid(RRF) + Rerank。",
        "> CI 离线回归用；不是真实模型 benchmark。",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for k in ("recall@1", "recall@3", "recall@5", "hit@5", "mrr", "ndcg@5"):
        lines.append(f"| {k} | {agg.get(k)} |")
    cache = metrics["cache"]
    lines += [
        "",
        "## Cache benchmark",
        f"- exact hits: {cache['exact_hits']} / {metrics['n_queries']}",
        f"- semantic hits: {cache['semantic_hits']}",
        f"- false hit rate: {cache['false_hit_rate']}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
