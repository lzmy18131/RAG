"""API v1 — documents 路由（上传 / 列表 / 删除）。

上传在 demo 模式下不启用（内置合成语料固定）；真实模式走 IncrementalIndexer。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.api.deps import PROJECT_ROOT, get_settings
from src.api.schemas import DocumentItem, DocumentListResponse

router = APIRouter(prefix="/api/v1/documents")


@router.get("", response_model=DocumentListResponse)
async def list_documents_v1():
    """列出 manifest 中跟踪的文档（demo 模式返回内置合成语料）。"""
    from src.infra.demo import DEMO_CORPUS
    from src.ingestion.manifest import ManifestStore

    settings = get_settings()
    if settings.demo_mode:
        chunks = DEMO_CORPUS
        return DocumentListResponse(
            documents=[
                DocumentItem(
                    document_id="demo-manual",
                    source_file="data/demo/x1-manual.pdf",
                    version="demo-v1",
                    num_chunks=len(chunks),
                    pages=max(c.get("page_number", 0) for c in chunks),
                    status="indexed",
                )
            ]
        )

    store = ManifestStore(PROJECT_ROOT / "storage" / "manifests")
    docs = []
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


@router.post("")
async def ingest_document_v1(file: UploadFile = File(...)):
    """上传 PDF 并增量索引（真实模式）。

    Demo 模式：返回 400（内置合成语料固定，不允许上传——诚实声明）。
    """
    settings = get_settings()
    if settings.demo_mode:
        raise HTTPException(400, "DEMO 模式使用内置合成语料，不支持上传；请关闭 DEMO_MODE 后使用真实索引")

    if not file.filename:
        raise HTTPException(400, "No filename provided")
    suffix = Path(file.filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(422, f"Unsupported file type: {suffix}. Only PDF accepted.")

    import uuid as _uuid

    raw_dir = PROJECT_ROOT / settings.data_dir / "raw_docs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    max_size = settings.max_upload_mb * 1024 * 1024
    dest = raw_dir / f"{_uuid.uuid4().hex}.pdf"
    size = 0
    with open(dest, "wb") as f:
        while chunk := file.file.read(1024 * 256):
            size += len(chunk)
            if size > max_size:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"PDF exceeds {settings.max_upload_mb}MB limit")
            f.write(chunk)

    try:
        import fitz

        doc = fitz.open(dest)
        total_pages = len(doc)
        doc.close()
        if total_pages == 0:
            dest.unlink(missing_ok=True)
            raise HTTPException(422, "PDF has no pages")
        if total_pages > settings.max_pdf_pages:
            dest.unlink(missing_ok=True)
            raise HTTPException(422, f"PDF exceeds {settings.max_pdf_pages} page limit")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"Invalid PDF file: {e}") from None

    from src.api.deps import get_bm25, get_incremental_indexer
    from src.ingestion.manifest import ManifestStore

    indexer = get_incremental_indexer()
    counts = indexer.process(str(raw_dir))
    get_bm25().save(PROJECT_ROOT / "storage" / "bm25")

    store = ManifestStore(PROJECT_ROOT / "storage" / "manifests")
    m = store.get(str(dest))
    return {
        "document_id": m.document_id if m else "unknown",
        "version": m.version if m else "unknown",
        "chunks": counts["embedded_chunks"] + counts["reused_chunks"],
        "status": "ingested",
        "added": counts["added"],
        "unchanged": counts["unchanged"],
        "modified": counts["modified"],
        "deleted": counts["deleted"],
    }


@router.delete("/{document_id}")
async def delete_document_v1(document_id: str):
    """删除文档（真实模式从 Milvus/BM25/manifest 移除；demo 模式拒绝）。"""
    settings = get_settings()
    if settings.demo_mode:
        raise HTTPException(400, "DEMO 模式语料固定，不支持删除")

    from src.api.deps import get_bm25, get_incremental_indexer
    from src.ingestion.manifest import ManifestStore

    store = ManifestStore(PROJECT_ROOT / "storage" / "manifests")
    target = None
    for f in store.all_files():
        m = store.get(f)
        if m and m.document_id == document_id:
            target = f
            break
    if target is None:
        raise HTTPException(404, f"Document not found: {document_id}")

    indexer = get_incremental_indexer()
    indexer.delete_document(target)
    get_bm25().save(PROJECT_ROOT / "storage" / "bm25")
    return {"status": "deleted", "document_id": document_id}
