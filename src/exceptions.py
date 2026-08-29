"""领域异常层次（audit B2 / 任务书 §54-55）。

Core 层禁止抛 HTTPException；统一抛 LingYiError 子类，由 API 层转换为错误 envelope。
"""

from __future__ import annotations


class RAGError(Exception):
    """所有 -RAG- 领域异常的基类。"""

    def __init__(self, message: str = "", *, code: str = "RAG_ERROR", detail: str = ""):
        self.code = code
        self.message = message or detail
        self.detail = detail or message
        super().__init__(self.message)


class ConfigurationError(RAGError):
    def __init__(self, message: str = "", **kw):
        super().__init__(message, code="CONFIGURATION_ERROR", **kw)


class DocumentParseError(RAGError):
    def __init__(self, message: str = "", **kw):
        super().__init__(message, code="DOCUMENT_PARSE_ERROR", **kw)


class IndexingError(RAGError):
    def __init__(self, message: str = "", **kw):
        super().__init__(message, code="INDEXING_ERROR", **kw)


class RetrievalError(RAGError):
    def __init__(self, message: str = "", **kw):
        super().__init__(message, code="RETRIEVAL_ERROR", **kw)


class RerankError(RAGError):
    def __init__(self, message: str = "", **kw):
        super().__init__(message, code="RERANK_ERROR", **kw)


class ModelProviderError(RAGError):
    def __init__(self, message: str = "", *, provider: str = "", **kw):
        self.provider = provider
        super().__init__(message, code="MODEL_PROVIDER_ERROR", **kw)


class GroundingError(RAGError):
    def __init__(self, message: str = "", **kw):
        super().__init__(message, code="GROUNDING_ERROR", **kw)


class CacheError(RAGError):
    def __init__(self, message: str = "", **kw):
        super().__init__(message, code="CACHE_ERROR", **kw)
