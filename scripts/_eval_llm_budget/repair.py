"""缺结构补写（评测期实验）：结构缺失时追加一次**极短**调用，只补齐缺失块。

用途：验证设计文档里「失败自动补写」这条兜底是否真能把丢掉的交付物补回来，
以及代价多少（输入/输出 token、墙钟）。**只在评测里用**，不改生产链路——生产侧
接缝属于实施阶段。

接口设计：
  - ``missing_blocks`` 纯函数，判定缺什么（当前只判「操作建议表」）；
  - ``repair_text`` 接受可注入的调用器（默认走 ``call_llm``），便于单测零网络。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from . import measure

logger = logging.getLogger(__name__)

_SYSTEM = "你是报告结构修复器。只输出被要求的结构块，不写解释、不复述已有正文，输出 Markdown。"


def missing_blocks(text: str, *, mode: str = "standard") -> list[str]:
    """返回缺失的结构块名列表。

    Args:
        text: 已生成的报告文本。
        mode: 评测模式；标准模式要求「操作建议表」。

    Returns:
        缺失块名列表（空列表表示结构齐全）。
    """
    missing: list[str] = []
    if mode.startswith("standard") and measure.count_action_rows(text)["rows"] < 1:
        missing.append("操作建议表")
    return missing


def _build_user_prompt(text: str, block: str, codes: list[str]) -> str:
    tail = text[-800:]
    code_hint = "、".join(codes[:12]) if codes else "报告中出现的品种"
    return (
        f"下面这段报告缺少「{block}」。请**只输出该表**，不要输出任何其他内容。\n"
        "表头固定为：| 优先级 | 品种 | 建议操作 | 理由 |\n"
        f"要求：≤8 行；覆盖以下品种中的至少 3 个：{code_hint}；理由一行一句。\n\n"
        f"报告结尾片段：\n{tail}"
    )


def repair_text(
    text: str,
    *,
    block: str,
    codes: list[str],
    caller: Callable[[str, str], tuple[str | None, dict | None]],
) -> tuple[str, dict[str, Any]]:
    """调用一次短补写并把结果拼到原文末尾。

    Args:
        text: 原文。
        block: 缺失块名（用于提示词）。
        codes: 报告中出现的品种代码（约束覆盖范围）。
        caller: ``(system, user) -> (content, usage)``；测试注入假实现。

    Returns:
        ``(new_text, info)``；``info`` 含 ``repaired`` / ``usage``；调用失败时原样返回
        ``repaired=False``（补写绝不阻断主流程）。
    """
    content, usage = caller(_SYSTEM, _build_user_prompt(text, block, codes))
    if not content:
        logger.warning("[eval] 补写失败（%s），保留原文", block)
        return text, {"repaired": False, "usage": usage or {}}
    merged = text.rstrip() + "\n\n" + content.strip() + "\n"
    return merged, {"repaired": True, "usage": usage or {}}
