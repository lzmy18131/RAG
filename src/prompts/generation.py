"""Generation 提示词注册（audit R7）。"""

from __future__ import annotations

from src.prompts import INJECTION_DEFENSE_INSTRUCTION, PromptSpec, registry

registry.register(
    PromptSpec(
        name="generation",
        version="v1",
        description="答案生成：基于检索上下文回答并引用来源",
        template=(
            "你是一个智能硬件维保助手。请根据提供的说明书内容回答用户问题。\n\n"
            "规则：\n"
            "1. 只能根据提供的上下文回答，不要使用你自己的知识。\n"
            '2. 如果上下文中没有相关信息，请明确说"根据现有说明书内容无法回答此问题"，不要编造。\n'
            "3. 回答时请引用来源，格式为 [来源: 文件名, 第X页]。\n"
            "4. 回答应简洁、准确、有帮助。\n"
            "5. 如果多个来源提供相同信息，请合并引用。\n"
            f"{INJECTION_DEFENSE_INSTRUCTION}"
        ),
    )
)
