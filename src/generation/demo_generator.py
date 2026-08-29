"""Demo Mode 确定性答案生成器（无 API key）。

与 src/generation/generator.py 的 generate_answer 同签名：
    demo_generate_answer(question, retrieved_chunks, temperature=0.0) -> dict

确定性规则：
- 无检索结果 → 拒答（与真实 generator 一致）。
- 有结果 → 用 Top-1 chunk 组织模板答案（引用「第X页」），带 DEMO 标记。
- 关键词触发「维护流程」类回答时拼接 Top-1~2 内容。
不调用任何真实模型；输出永远可复现。
"""

from __future__ import annotations

from src.infra.demo import DEMO_MARK


def demo_generate_answer(
    question: str,
    retrieved_chunks: list[dict],
    temperature: float = 0.0,
) -> dict:
    """Deterministic answer from the top retrieved chunk(s)."""
    if not retrieved_chunks:
        return {
            "answer": "根据现有说明书内容无法回答此问题。",
            "chunks_used": 0,
            "citations": [],
            "model": "demo",
            "usage": None,
        }

    top = retrieved_chunks[0]
    page = top.get("page_number", "?")
    content = str(top.get("content", "")).strip()

    if len(retrieved_chunks) >= 2 and any(
        kw in question for kw in ("怎么", "如何", "步骤", "处理", "维护", "清理")
    ):
        second = retrieved_chunks[1]
        answer = (
            f"{DEMO_MARK}\n\n"
            f"根据说明书第 {page} 页：{content}\n"
            f"补充（第 {second.get('page_number', '?')} 页）：{str(second.get('content', '')).strip()}"
        )
    else:
        answer = f"{DEMO_MARK}\n\n根据说明书第 {page} 页：{content}"

    citations = [
        {
            "chunk_id": c.get("chunk_id", ""),
            "source_file": c.get("source_file", ""),
            "page_number": c.get("page_number", 0),
            "retrieval_score": c.get("retrieval_score"),
            "rerank_score": c.get("rerank_score"),
        }
        for c in retrieved_chunks
    ]

    return {
        "answer": answer,
        "chunks_used": len(retrieved_chunks),
        "citations": citations,
        "model": "demo",
        "usage": None,
    }
