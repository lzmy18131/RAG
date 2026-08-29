"""IncrementalIndexer: add/modify/delete documents in-place in Milvus + BM25.

Per-file failure tolerance (audit P0-2): a failing file is recorded in
``self.failures`` and skipped, so one bad PDF does not abort the whole batch.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.ingestion.chunker import chunk_document
from src.ingestion.manifest import DocManifest, ManifestStore, file_hash
from src.ingestion.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)


class IncrementalIndexer:
    """Manages in-place incremental updates to Milvus + BM25 indexes."""

    def __init__(
        self,
        milvus_client,
        collection_name: str,
        bm25,
        manifest_store: ManifestStore,
        embedder,
    ):
        self.client = milvus_client
        self.collection = collection_name
        self.bm25 = bm25
        self.store = manifest_store
        self.embedder = embedder
        self.embed_call_count = 0
        self.failures: list[dict] = []

    # ── Public API ──

    def process(self, docs_dir: str | Path) -> dict:
        """Run incremental update on all PDFs in docs_dir."""
        docs_dir = Path(docs_dir)
        current_files = {}
        for p in sorted(docs_dir.glob("*.pdf")):
            current_files[str(p)] = file_hash(str(p))

        classified = self.store.classify(current_files)
        counts: dict[str, Any] = {
            "added": 0,
            "unchanged": 0,
            "modified": 0,
            "deleted": 0,
            "reprocessed_pages": 0,
            "reused_chunks": 0,
            "embedded_chunks": 0,
            "removed_chunks": 0,
        }

        for path in classified["deleted"]:
            m = self.store.get(path)
            if m:
                self._delete_document(path)
                counts["deleted"] += 1
                counts["removed_chunks"] += m.num_chunks

        for path in classified["added"]:
            counts["added"] += 1
            try:
                c = self._add_document(path)
                counts["embedded_chunks"] += c["embedded"]
                counts["reprocessed_pages"] += c["pages"]
            except Exception as e:  # noqa: BLE001 - per-file 容错，坏文件不中断整批
                self.failures.append({"path": path, "action": "added", "error": str(e)[:300]})
                logger.warning("增量摄取失败(added): %s: %s", path, e)

        for path in classified["modified"]:
            counts["modified"] += 1
            try:
                c = self._modify_document(path)
                counts["embedded_chunks"] += c["embedded"]
                counts["removed_chunks"] += c["removed"]
                counts["reprocessed_pages"] += c["pages"]
            except Exception as e:  # noqa: BLE001
                self.failures.append({"path": path, "action": "modified", "error": str(e)[:300]})
                logger.warning("增量摄取失败(modified): %s: %s", path, e)

        for path in classified["unchanged"]:
            m = self.store.get(path)
            if m:
                counts["unchanged"] += 1
                counts["reused_chunks"] += m.num_chunks

        self.store.save()
        counts["failures"] = list(self.failures)
        return counts  # type: ignore[return-value]  # counts 键为混合类型（int/list）

    # ── Internal ──

    def _add_document(self, path: str) -> dict:
        doc = parse_pdf(path)
        chunks = chunk_document(doc, 500, 50)
        texts = [c.content for c in chunks]
        vectors = self.embedder.encode_batch(texts)
        self.embed_call_count += 1

        data = []
        for chunk, vec in zip(chunks, vectors, strict=False):
            data.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number,
                    "content": chunk.content,
                    "content_type": chunk.content_type,
                    "source_file": chunk.source_file,
                    "document_version": chunk.document_version,
                    "vector": vec,
                }
            )
        self.client.insert(collection_name=self.collection, data=data)

        # Update BM25
        bm25_chunks = [
            {
                "chunk_id": c.chunk_id,
                "page_number": c.page_number,
                "content_type": c.content_type,
                "source_file": c.source_file,
                "content": c.content,
            }
            for c in chunks
        ]
        self.bm25.add_chunks(bm25_chunks)

        manifest = DocManifest(
            source_file=path,
            document_id=doc.document_id,
            file_hash=file_hash(path),
            file_size=Path(path).stat().st_size,
            total_pages=doc.metadata["total_pages"],
            text_pages=len(doc.pages),
            num_chunks=len(chunks),
        )
        self.store.upsert(manifest)
        return {"embedded": len(chunks), "pages": doc.metadata["total_pages"]}

    def _modify_document(self, path: str) -> dict:
        old = self.store.get(path)
        removed = old.num_chunks if old else 0
        self._delete_document(path)
        result = self._add_document(path)
        result["removed"] = removed
        return result

    def _delete_document(self, path: str) -> None:
        # Delete from Milvus — escape backslashes for Milvus filter
        escaped = str(path).replace("\\", "\\\\")
        self.client.delete(
            collection_name=self.collection,
            filter=f'source_file == "{escaped}"',
        )
        # Delete from BM25
        self.bm25.remove_by_source(str(path))
        # Remove from manifest
        self.store.remove(str(path))
