"""LLM answer generator with citation support."""

from __future__ import annotations

from src.infra.llm_client import LLMClient


def _build_context(chunks: list[dict]) -> str:
    """Build context string from retrieved chunks（内容包装为不可信，audit R8）。"""
    from src.prompts import wrap_untrusted

    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        source = c.get("source_file", "unknown")
        page = c.get("page_number", "?")
        content = c.get("content", "")
        parts.append(f"[{i}] 来源: {source}, 第{page}页\n{wrap_untrusted(content)}")
    return "\n\n".join(parts)


def generate_answer(
    question: str,
    retrieved_chunks: list[dict],
    temperature: float = 0.0,
) -> dict:
    """Generate an answer with citations from retrieved chunks.

    Returns:
        {answer, chunks_used, citations, model, usage}
    """
    if not retrieved_chunks:
        return {
            "answer": "根据现有说明书内容无法回答此问题。",
            "chunks_used": 0,
            "citations": [],
            "model": None,
            "usage": None,
        }

    context = _build_context(retrieved_chunks)
    user_message = f"上下文：\n\n{context}\n\n问题：{question}"

    from src.prompts import registry

    client = LLMClient()
    response_text, raw = client.chat(
        messages=[
            {"role": "system", "content": registry.render("generation")},
            {"role": "user", "content": user_message},
        ],
    )

    # Extract citations from chunks used
    citations: list[dict] = []
    for c in retrieved_chunks:
        citations.append(
            {
                "chunk_id": c.get("chunk_id", ""),
                "source_file": c.get("source_file", ""),
                "page_number": c.get("page_number", 0),
                "retrieval_score": c.get("retrieval_score"),
            }
        )

    return {
        "answer": response_text,
        "chunks_used": len(retrieved_chunks),
        "citations": citations,
        "model": raw.get("model"),
        "usage": raw.get("usage"),
    }
