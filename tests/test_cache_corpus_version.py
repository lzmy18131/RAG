"""语义缓存 corpus_version 失效测试（audit P0-4 / §29-31）。"""

from __future__ import annotations

from src.api.routes import _corpus_version
from src.infra.semantic_cache import SemanticCache


class TestCorpusVersion:
    def test_corpus_version_derived_from_manifest(self, tmp_path, monkeypatch):
        manifests = tmp_path / "storage" / "manifests"
        manifests.mkdir(parents=True)
        f = manifests / "manifests.json"
        f.write_text("{}", encoding="utf-8")

        class _S:
            pass

        s = _S()
        monkeypatch.setattr("src.api.routes.PROJECT_ROOT", tmp_path)
        v1 = _corpus_version(s)
        assert v1 != "unknown"

        # 文档变化 → manifests.json 变化 → corpus_version 变化
        f.write_text('{"doc.pdf": {"file_hash": "abc"}}', encoding="utf-8")
        v2 = _corpus_version(s)
        assert v2 != v1


class TestCacheSaltIsolation:
    def test_cache_key_includes_salt(self, tmp_path):
        cache = SemanticCache(embedder=None, db_path=str(tmp_path / "c.db"), threshold=0.9)
        k1 = cache._key_text("如何开机", salt="manual.pdf|corpus:aaa")
        k2 = cache._key_text("如何开机", salt="manual.pdf|corpus:bbb")  # corpus 变化
        k3 = cache._key_text("如何开机", salt="manual2.pdf|corpus:aaa")  # doc 变化
        assert k1 != k2  # corpus_version 进入缓存 key
        assert k1 != k3  # doc_filter 进入缓存 key

    def test_normalize_keeps_salt(self):
        from src.infra.semantic_cache import _normalize_query_plus_salt

        a = _normalize_query_plus_salt("如何开机", salt="x|corpus:1")
        b = _normalize_query_plus_salt("如何开机", salt="x|corpus:2")
        assert a != b
