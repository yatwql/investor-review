"""自检抽样（离线）——对采样到的模块产出跑一次模型层复核。

为什么放在离线评测而不是每份报告：自检输入是**全部模块正文**（单份报告里最大的
一遍调用），产物只是尾部清单；它的价值要靠跨多份报告统计检出率来证明，而不是
在每份报告里烧一次 token。离线产物同时给人读（中文名）与程序读（内部键），
故模块一律按「中文名（内部键）」双写，不做上屏用的中文名替换。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("invest")


def _run_self_review_sample(
    module_outputs: dict[str, str | None],
    holdings_details: list[dict] | None,
    penetrated_assets: list[dict] | None,
) -> str | None:
    """跑一次自检复核，返回双写形态的复核清单（失败/空产出返回 None）。

    Args:
        module_outputs: 本次采样到的模块产出（键为内部模块名）。
        holdings_details: 持仓明细（复核的数值真值来源）。
        penetrated_assets: 穿透资产列表。

    Returns:
        Markdown 复核清单（模块名保留内部键供程序解析），或无内容时 None。
    """
    from src.python.config import get_llm_config
    from src.python.llm.generators import generate_self_review
    from src.python.llm.self_review import module_dual_form

    try:
        content, _cached = generate_self_review(
            module_outputs,
            holdings_details,
            penetrated_assets,
            force=True,
            llm_config=get_llm_config(),
        )
    except Exception as exc:  # noqa: BLE001 — 抽样失败只影响该段，不中断评测
        logger.warning("自检抽样失败（不影响幻觉率统计）: %s", exc)
        return None
    if not content:
        return None
    return module_dual_form(content)


def _generate_self_review_section(samples: list[dict]) -> str:
    """把自检抽样结果拼成报告附录（Markdown）。

    Args:
        samples: ``[{"dataset": 名称, "content": 清单文本或 None, "error": 失败原因或 None}]``
    """
    lines = ["", "## 自检抽样（离线）", ""]
    lines.append(
        "> 该段由 `self_review` 模型层复核产出，模块名为「中文名（内部键）」双写："
        "中文给人读、内部键给解析脚本用。自检属辅助信号，不构成质量保证。"
    )
    lines.append("")
    for sample in samples:
        lines.append(f"### {sample.get('dataset', '?')}")
        lines.append("")
        content = sample.get("content")
        if content:
            lines.append(content.strip())
        else:
            lines.append(f"（未产出：{sample.get('error') or '空输出'}）")
        lines.append("")
    return "\n".join(lines)


def _build_self_review_dry_run_prompt(
    module_outputs: dict[str, str | None],
    holdings_details: list[dict] | None,
    penetrated_assets: list[dict] | None,
) -> str:
    """dry-run 用：只构建自检提示词（不调用 LLM，零花费）。"""
    from src.python.llm.prompts import _SYSTEM_SELF_REVIEW, _build_self_review_prompt

    prompt = _build_self_review_prompt(module_outputs, holdings_details, penetrated_assets)
    return f"### System\n\n{_SYSTEM_SELF_REVIEW}\n\n### User\n\n{prompt}"
