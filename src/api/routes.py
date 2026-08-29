"""FastAPI routes for the RAG demo."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.api.deps import (
    PROJECT_ROOT,
    get_bm25,
    get_incremental_indexer,
    get_latest_v1_collection,
    get_semantic_cache,
    get_settings,
    get_vqa,
)

router = APIRouter()


def _find_run_dir(run_id: str) -> Path | None:
    """统一实验产物目录（任务书 §46）：runs/ 优先，storage/runs/ 仅作 legacy 回退。

    runs/ → evaluation artifacts（Experiment Registry 写入目录）
    storage/ → runtime state（旧 artifact 只读回退）
    """
    primary = PROJECT_ROOT / "runs" / run_id
    if primary.exists():
        return primary
    legacy = PROJECT_ROOT / "storage" / "runs" / run_id
    if legacy.exists():
        return legacy
    return None


# ═══════════════════ Models ═══════════════════


class QueryRequest(BaseModel):
    question: str
    experiment: str = "v4"
    source_document: str | None = None  # friendly name, e.g. "Roborock G10S" (V8)


class QueryResponse(BaseModel):
    question: str
    answer: str
    final_status: str
    experiment: str
    sources: list[dict]
    evidence_chunk_ids: list[str]
    verification: dict
    timing_s: float
    cache_hit: bool = False
    cache_source: str | None = None  # "exact" | "semantic" | None
    doc_filter: str | None = None  # resolved source_file scope (V8)


class IngestResponse(BaseModel):
    document_id: str
    version: str
    chunks: int
    pages: int
    status: str
    added: int = 0
    unchanged: int = 0
    modified: int = 0
    deleted: int = 0
    reprocessed_pages: int = 0
    reused_chunks: int = 0
    embedded_chunks: int = 0
    removed_chunks: int = 0


class DocumentItem(BaseModel):
    document_id: str
    source_file: str
    version: str
    num_chunks: int
    status: str = "indexed"


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


class EvaluateRequest(BaseModel):
    experiment: str = "v0_naive"
    dataset: str = "v0_questions"
    max_questions: int = 10


# ═══════════════════ Routes ═══════════════════


@router.get("/health")
async def health():
    settings = get_settings()
    final_eval_exists = (
        PROJECT_ROOT / "storage" / "runs" / "final_eval" / "final_metrics.json"
    ).exists()
    from src.api.app import _app_version

    return {
        "status": "ok",
        "version": _app_version(),
        "pipeline_version": "rag-v9",
        "collection": get_latest_v1_collection(),
        "milvus": settings.milvus_uri,
        "bm25_docs": get_bm25().num_docs,
        "final_eval": final_eval_exists,
        "models": {
            "embedding": settings.embedding_model,
            "reranker": settings.reranker_model,
            "llm": settings.llm_model,
        },
    }


@router.post("/documents/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    """Upload a PDF, save, parse, embed via IncrementalIndexer."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    # Validate file extension
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf",):
        raise HTTPException(422, f"Unsupported file type: {suffix}. Only PDF accepted.")

    # 安全加固（audit P0-1）：大小上限 + 文件名消毒（uuid 保存，杜绝路径穿越）
    import uuid as _uuid

    settings = get_settings()
    raw_dir = PROJECT_ROOT / settings.data_dir / "raw_docs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    max_size = 50 * 1024 * 1024  # 50MB 上限
    size = 0
    dest = raw_dir / f"{_uuid.uuid4().hex}.pdf"
    with open(dest, "wb") as f:
        while chunk := file.file.read(1024 * 256):
            size += len(chunk)
            if size > max_size:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "PDF exceeds 50MB limit")
            f.write(chunk)

    # Validate PDF can be opened
    try:
        import fitz

        doc = fitz.open(dest)
        total_pages = len(doc)
        doc.close()
        if total_pages == 0:
            dest.unlink(missing_ok=True)
            raise HTTPException(422, "PDF has no pages")
    except HTTPException:
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"Invalid PDF file: {e}") from None

    # Use IncrementalIndexer
    indexer = get_incremental_indexer()
    counts = indexer.process(str(raw_dir))
    bm = get_bm25()
    bm.save(PROJECT_ROOT / "storage" / "bm25")

    # Find the manifest for this file
    from src.ingestion.manifest import ManifestStore

    store = ManifestStore(PROJECT_ROOT / "storage" / "manifests")
    m = store.get(str(dest))

    return IngestResponse(
        document_id=m.document_id if m else "unknown",
        version=m.version if m else "unknown",
        chunks=counts["embedded_chunks"] + counts["reused_chunks"],
        pages=counts["reprocessed_pages"],
        status="ingested",
        added=counts["added"],
        unchanged=counts["unchanged"],
        modified=counts["modified"],
        deleted=counts["deleted"],
        reprocessed_pages=counts["reprocessed_pages"],
        reused_chunks=counts["reused_chunks"],
        embedded_chunks=counts["embedded_chunks"],
        removed_chunks=counts["removed_chunks"],
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """Return all tracked documents from the manifest store（demo 模式返回内置合成语料）。"""
    settings = get_settings()
    if settings.demo_mode:
        from src.infra.demo import DEMO_CORPUS

        return DocumentListResponse(
            documents=[
                DocumentItem(
                    document_id="demo-manual",
                    source_file="x1-manual.pdf",
                    version="demo-v1",
                    num_chunks=len(DEMO_CORPUS),
                    status="indexed",
                )
            ]
        )
    from src.ingestion.manifest import ManifestStore

    store = ManifestStore(PROJECT_ROOT / "storage" / "manifests")
    docs: list[DocumentItem] = []
    for source_file in sorted(store.all_files()):
        m = store.get(source_file)
        if m:
            docs.append(
                DocumentItem(
                    document_id=m.document_id,
                    source_file=Path(m.source_file).name,
                    version=m.version,
                    num_chunks=m.num_chunks,
                    status="indexed",
                )
            )
    return DocumentListResponse(documents=docs)


def _corpus_version(settings) -> str:
    """corpus_version：由 manifests.json 内容派生。

    任一文档增/删/改 → manifest 变化 → corpus_version 变化 → 语义缓存 key 变化，
    避免知识库更新后缓存返回陈旧答案（audit P0-4）。
    """
    import hashlib

    p = PROJECT_ROOT / "storage" / "manifests" / "manifests.json"
    try:
        if p.exists():
            return hashlib.sha256(p.read_bytes()).hexdigest()[:12]
        return "empty"
    except Exception:  # noqa: BLE001
        return "unknown"


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """Answer via the LangGraph pipeline (V4→V6), with optional doc_filter
    scope (V8) and the V9 semantic-cache fast-path. The cache is salted with
    the doc_filter AND the corpus_version so answers scoped to different
    manuals never collide, and knowledge-base updates invalidate stale
    cache entries (audit P0-4)."""
    t0 = time.perf_counter()
    settings = get_settings()

    from src.eval.doc_registry import resolve_doc_filter

    doc_filter = resolve_doc_filter(req.source_document) if req.source_document else None
    salt = f"{doc_filter or ''}|corpus:{_corpus_version(settings)}"

    # ── V9 semantic cache: exact (SHA256) then semantic (BGE-M3 cosine) ──
    cache = None
    if settings.cache_enabled:
        cache = get_semantic_cache()
        cached = cache.get(req.question, salt=salt)
        if cached is not None:
            resp, source = cached
            resp["cache_hit"] = True
            resp["cache_source"] = source
            resp["timing_s"] = round(time.perf_counter() - t0, 2)
            return QueryResponse(**resp)

    vqa = get_vqa()
    state = vqa.run(req.question, doc_filter=doc_filter)

    sources = []
    for c in state.get("retrieved_chunks", []):
        sources.append(
            {
                "chunk_id": c.get("chunk_id", ""),
                "source_file": Path(c.get("source_file", "")).name if c.get("source_file") else "",
                "page_number": c.get("page_number", 0),
                "content_type": c.get("content_type", "text"),
                "rerank_score": c.get("rerank_score"),
            }
        )

    vr = state.get("verification_result", {})
    resp = QueryResponse(
        question=req.question,
        answer=state.get("answer", ""),
        final_status=state.get("final_status", "refused"),
        experiment=req.experiment,
        sources=sources,
        evidence_chunk_ids=[str(x) for x in vr.get("evidence_chunk_ids", [])],
        verification={
            "supported": vr.get("supported", False),
            "confidence": vr.get("confidence", 0.0),
            "reason": vr.get("reason", ""),
            "unsupported_claims": vr.get("unsupported_claims", []),
            "grounding_meta": vr.get("grounding_meta"),
            "sentence_evidence": vr.get("sentence_evidence"),
        },
        timing_s=round(time.perf_counter() - t0, 2),
        doc_filter=doc_filter,
    )
    if cache is not None:
        cache.put(req.question, resp.model_dump(), salt=salt)
    return resp


@router.get("/system")
async def system_status():
    """Live system state: LLM gateway circuit breakers (V7), semantic cache
    stats (V9), and grounding verifier config (V6)."""
    settings = get_settings()
    from src.infra.gateway import get_gateway

    gateway = get_gateway()
    cache = get_semantic_cache() if settings.cache_enabled else None
    return {
        "version": "V9",
        "gateway": gateway.state_dump(),
        "cache": cache.stats() if cache else None,
        "grounding": {
            "verifier_mode": settings.verifier_mode,
            "scorer": settings.grounding_scorer,
            "scorer_floor": settings.grounding_scorer_floor,
            "min_support_ratio": settings.grounding_min_support_ratio,
        },
    }


@router.get("/versions")
async def version_highlights():
    """V6/V8/V9 评估亮点——只返回**真实 run artifact**（任务书 §5）。

    无 artifact → ``{"available": false, "source": "none", "run_id": null, "metrics": null}``。
    历史 benchmark 只保留在 docs（README / EXPERIMENT_LOG），API 不做历史数字 fallback，
    避免把重构前的旧结果伪装成当前状态。
    """
    settings = get_settings()

    def _no_run() -> dict:
        return {"available": False, "source": "none", "run_id": None, "metrics": None}

    def _load_metrics(path: Path) -> dict | None:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return None

    # ── V6 deterministic grounding（真实 artifact：storage/runs/v6_grounding/） ──
    v6_dir = PROJECT_ROOT / "storage" / "runs" / "v6_grounding"
    v6_meta = _load_metrics(v6_dir / "metadata.json")
    v6_poison = _load_metrics(v6_dir / "poison_test.json")
    if v6_meta is None and v6_poison is None:
        v6: dict[str, Any] = _no_run()
    else:
        # 历史 artifact：本 refactor 后未重跑 → 明确标注
        v6 = {
            "available": True,
            "source": "historical",
            "run_id": "v6_grounding",
            "verified_after_refactor": False,
        }
        v6["metrics"] = {
            "total": v6_meta.get("total_cases", 100) if v6_meta else None,
            "answered": v6_meta.get("fixed_answered") if v6_meta else None,
            "avg_support_ratio": v6_meta.get("avg_support_ratio") if v6_meta else None,
            "retries_used": v6_meta.get("retries_used") if v6_meta else None,
        }
        if isinstance(v6_poison, list) and v6_poison:
            flagged = sum(1 for r in v6_poison if r.get("poison_flagged_unsupported"))
            v6["metrics"]["poison_flagged"] = flagged
            v6["metrics"]["poison_total"] = len(v6_poison)
            v6["metrics"]["poison_rate"] = round(flagged / len(v6_poison), 4)

    # ── V7 LLM gateway（实时配置，始终真实） ──
    from src.infra.gateway import get_gateway

    gw = get_gateway()
    v7 = {
        "available": True,
        "source": "live-config",
        "metrics": {
            "timeout_s": settings.llm_timeout,
            "max_retries": settings.llm_max_retries,
            "circuit_threshold": settings.llm_circuit_threshold,
            "cooldown_s": settings.llm_circuit_cooldown,
            "configured_providers": len(gw.state_dump().get("providers", [])),
        },
    }

    # ── V8 multi-doc（真实 artifact：storage/runs/final_eval_extended_full/） ──
    v8_path = PROJECT_ROOT / "storage" / "runs" / "final_eval_extended_full" / "final_metrics.json"
    v8_data = _load_metrics(v8_path)
    if v8_data is None:
        v8: dict[str, Any] = _no_run()
    else:
        rm = (v8_data.get("versions") or {}).get("V3", {}).get("retrieval_metrics", {})
        v8 = {
            "available": True,
            "source": "historical",
            "run_id": "final_eval_extended_full",
            "verified_after_refactor": False,
            "metrics": {
                "questions": v8_data.get("total_questions"),
                "hit_at_5": rm.get("hit_at_5"),
                "mrr": rm.get("mrr"),
                "top1_hit_rate": rm.get("top1_hit_rate"),
            },
        }

    # ── V9 semantic cache（真实 artifact：storage/runs/v9_cache/） ──
    v9_path = PROJECT_ROOT / "storage" / "runs" / "v9_cache" / "cache_eval.json"
    v9_data = _load_metrics(v9_path)
    if v9_data is None:
        v9: dict[str, Any] = _no_run()
    else:
        v9 = {
            "available": True,
            "source": "historical",
            "run_id": "v9_cache",
            "verified_after_refactor": False,
            "metrics": {
                "warmed": v9_data.get("warmed"),
                "exact_hits": v9_data.get("exact_hits"),
                "semantic_hits": v9_data.get("semantic_hits"),
                "overall_hit_rate": v9_data.get("overall_hit_rate"),
                "avg_cached_s": v9_data.get("avg_cached_s"),
                "avg_uncached_s": v9_data.get("avg_uncached_s"),
                "llm_calls_saved": v9_data.get("llm_calls_saved"),
            },
        }

    return {
        "version": "rag-v9",
        "v6_grounding": v6,
        "v7_gateway": v7,
        "v8_multidoc": v8,
        "v9_cache": v9,
    }


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest):
    """Return existing cached metrics for the given experiment."""
    runs_dir = _find_run_dir(req.experiment)
    if runs_dir is None:
        raise HTTPException(404, f"Experiment not found: {req.experiment}")

    # Gather all metrics from JSON files
    metrics: dict[str, Any] = {}
    for f in sorted(runs_dir.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for k in (
                    "metrics",
                    "summary",
                    "retrieval_metrics",
                    "ragas_metrics",
                    "hit_rate",
                    "recall_at_5",
                    "mrr",
                    "top5_hit_rate",
                    "faithfulness",
                    "context_precision",
                    "context_recall",
                    "answer_relevancy",
                ):
                    if k in data and data[k] is not None:
                        metrics[k] = data[k]
        except Exception:
            pass

    return {
        "run_id": req.experiment,
        "dataset": req.dataset,
        "metrics": metrics,
        "files": [f.name for f in sorted(runs_dir.iterdir()) if f.suffix == ".json"],
    }


@router.get("/final_eval")
async def get_final_eval():
    """Return the final evaluation metrics (V0-V4 with RAGAS)."""
    final_path = None
    for base in (PROJECT_ROOT / "runs", PROJECT_ROOT / "storage" / "runs"):
        p = base / "final_eval" / "final_metrics.json"
        if p.exists():
            final_path = p
            break
    if final_path is None:
        raise HTTPException(404, "Final evaluation not found")
    with open(final_path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/experiments")
async def list_experiments():
    """Return all available experiment versions."""
    runs_dir = _find_run_dir("") or PROJECT_ROOT / "runs"
    if not runs_dir.exists():
        runs_dir = PROJECT_ROOT / "storage" / "runs"
    # Also check root-level files for V1/V2
    root_files = {f.name for f in runs_dir.iterdir() if f.is_file() and f.suffix == ".json"}
    exp_defs: list[dict[str, Any]] = [
        {
            "id": "v0_baseline",
            "name": "V0 Baseline",
            "description": "文本 + Dense Retrieval",
            "key_metric": "recall_at_5",
        },
        {
            "id": "v1_multimodal",
            "name": "V1 Multimodal",
            "description": "+ 图片 VLM 描述 + 表格",
            "key_metric": "image_chunks",
            "root_file": "v0_v1_comparison.json",
        },
        {
            "id": "v2_comparison",
            "name": "V2 Hybrid Retrieval",
            "description": "+ BM25 + Dense RRF 融合",
            "key_metric": "hybrid_hit_rate",
            "root_file": "v2_comparison.json",
        },
        {
            "id": "v3_rerank",
            "name": "V3 Reranker",
            "description": "+ BGE-Reranker-v2-m3 精排",
            "key_metric": "mrr",
        },
        {
            "id": "v4_verified",
            "name": "V4 LangGraph Verify",
            "description": "+ 验证节点 + 重试 + 拒答",
            "key_metric": "verified",
        },
        {
            "id": "v5_incremental",
            "name": "V5 Incremental Update",
            "description": "+ SHA256 Hash 增量更新",
            "key_metric": "reused_chunks",
        },
        {
            "id": "v6_grounding",
            "name": "V6 Deterministic Grounding",
            "description": "+ 句级相似度接地验证(确定性,非 LLM 自查)",
            "key_metric": "support_ratio",
        },
    ]
    result = []
    for exp in exp_defs:
        exp_dir = runs_dir / exp["id"]
        has_dir = exp_dir.exists()
        has_root_file = exp.get("root_file", "") in root_files
        exp["available"] = has_dir or has_root_file
        files = []
        if has_dir:
            files = [f.name for f in sorted(exp_dir.iterdir()) if f.suffix == ".json"]
        if has_root_file:
            files.append(exp["root_file"])
        exp["files"] = files
        result.append(exp)
    return {"experiments": result}


def _extract_metrics(data: dict, prefix: str = "") -> dict:
    """Recursively flatten nested metrics into a single dict."""
    result = {}
    known_metrics = {
        "hit_rate",
        "recall_at_5",
        "mrr",
        "faithfulness",
        "context_precision",
        "context_recall",
        "answer_relevancy",
        "top5_hit_rate",
        "top1_hit_rate",
        "top5_hit_count",
        "added_count",
        "unchanged_count",
        "modified_count",
        "deleted_count",
        "reprocessed_pages",
        "reused_chunks",
        "embedded_chunks",
        "removed_chunks",
        "v1_hit_rate",
        "v0_hit_rate",  # V1 comparison
    }
    # Map version-prefixed keys to generic metric names
    key_aliases = {
        "v1_hit_rate": "hit_rate",
        "v0_hit_rate": "hit_rate",
    }
    for key, val in data.items():
        if key in known_metrics and isinstance(val, (int, float)):
            result[key] = val
            # Also emit alias
            if key in key_aliases:
                result[key_aliases[key]] = val
        elif isinstance(val, dict):
            sub = _extract_metrics(val, f"{prefix}{key}.")
            result.update(sub)
    return result


@router.get("/experiments/{exp_id}")
async def get_experiment(exp_id: str):
    """Read existing experiment metadata and metrics."""
    found = _find_run_dir(exp_id)
    runs_dir = found if found is not None else PROJECT_ROOT / "storage" / "runs" / exp_id
    root_runs = _find_run_dir("") or PROJECT_ROOT / "storage" / "runs"

    # Map V1/V2 to their root-level files
    root_file_map = {
        "v1_multimodal": ["v0_v1_comparison.json", "v1_ingest/metadata.json"],
        "v2_comparison": ["v2_comparison.json"],
    }

    if not runs_dir.exists() and exp_id not in root_file_map:
        raise HTTPException(404, f"Experiment not found: {exp_id}")

    info: dict[str, Any] = {"id": exp_id, "files": [], "metrics": {}}
    all_metrics: dict[str, float] = {}

    # Read from subdirectory if exists
    sources: list[str] = []
    if runs_dir.exists():
        sources.extend(str(f) for f in sorted(runs_dir.iterdir()) if f.suffix == ".json")
    # Also read root-level files for V1/V2
    for rf in root_file_map.get(exp_id, []):
        p = root_runs / rf
        if p.exists():
            sources.append(str(p))

    for src in sources:
        f = Path(src)
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                flat = _extract_metrics(data)
                # Prefer first occurrence (phase2 > retrieval_metrics)
                for k, v in flat.items():
                    if k not in all_metrics:
                        all_metrics[k] = v
                for k in ("experiment", "version", "timestamp", "total_questions"):
                    if k in data:
                        info.setdefault("metadata", {})[k] = data[k]
        except Exception:
            pass
        info["files"].append(f.name)

    # Unified flat metrics output: null for missing, real value for present
    metric_keys = [
        "hit_rate",
        "recall_at_5",
        "mrr",
        "faithfulness",
        "context_precision",
        "context_recall",
        "answer_relevancy",
        "top5_hit_rate",
        "top1_hit_rate",
    ]
    for mk in metric_keys:
        v = all_metrics.get(mk)
        info["metrics"][mk] = round(float(v), 4) if v is not None else None

    # Incremental metrics (V5)
    inc_keys = [
        "added_count",
        "unchanged_count",
        "modified_count",
        "deleted_count",
        "reprocessed_pages",
        "reused_chunks",
        "embedded_chunks",
        "removed_chunks",
    ]
    for ik in inc_keys:
        v = all_metrics.get(ik)
        if v is not None:
            info.setdefault("incremental_metrics", {})[ik] = int(v)

    return info
