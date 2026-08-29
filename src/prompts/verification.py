"""Verification 提示词注册（audit R7；V4 LLM-as-judge verifier 的 prompt）。"""

from __future__ import annotations

from src.prompts import PromptSpec, registry

registry.register(
    PromptSpec(
        name="verification",
        version="v1",
        description="V4 LLM-as-judge 验证：判断答案是否基于检索上下文",
        template=(
            "你是一个严谨的验证者。判断以下答案是否完全基于提供的上下文。\n\n"
            "上下文：\n{context}\n\n"
            "问题：{question}\n\n"
            "答案：{answer}\n\n"
            '输出 JSON：{{"supported": true/false, "confidence": 0-1, '
            '"unsupported_claims": [...], "reason": "..."}}\n'
            "只要答案包含上下文中没有的细节，supported 即为 false。"
        ),
        required_vars=("context", "question", "answer"),
    )
)
