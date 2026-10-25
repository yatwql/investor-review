"""LLM 模块调用（HTTP 客户端工厂 / 模块映射 / prompt 构建与真实调用）。

持仓侧派生（品种分类 / 组合核心数值 / 数据集加载）不在本模块实现——唯一实现是
``holdings.py``，本模块直接复用：两份副本曾随 ``fact_checker`` 内部结构调整各自失效
（其中一份引用了已搬走的 ``fact_checker._calc_portfolio_values`` 而静默不可用）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("hallucination_sampler")

# ── 晚导入（sys.path 就绪后） ───────────────────────────────────
_HTTP_CLIENT: Any = None


def _get_http_client():
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        from src.python.core.http_client import make_http_client

        _HTTP_CLIENT = make_http_client(timeout=120.0, http2=False)
    return _HTTP_CLIENT


# ── LLM 模块调用映射 ─────────────────────────────────────────────

_MODULE_FNS: dict[str, str] = {
    "expert_review": "generate_expert_review",
    "global_macro": "generate_global_macro",
    "health_check": "generate_health_check",
    "penetration_deep": "generate_penetration_deep_analysis",
}


def _call_llm_module(
    module_name: str,
    holdings_details: list[dict],
    values: dict[str, float],
    categories: dict[str, int],
    dry_run: bool = False,
    force: bool = False,
) -> tuple[str | None, dict | None]:
    """调用指定 LLM 模块生成分析文本。

    Args:
        module_name: LLM 模块名。
        holdings_details: 持仓明细。
        values: 组合核心数值（total_mv 等）。
        categories: 品种分类计数。
        dry_run: 仅构建 prompt 不调用 LLM。
        force: 跳过缓存强制重新生成。

    Returns:
        (llm_output_text, usage_or_prompt_dict)
        — 正常调用返回 (content, usage)；dry_run 返回 (prompt_str, {"dry_run": True})
    """
    from src.python.config import get_llm_config
    from src.python.llm.generators import (
        generate_expert_review,
        generate_global_macro,
        generate_health_check,
        generate_penetration_deep_analysis,
    )

    fn_name = _MODULE_FNS.get(module_name)
    if not fn_name:
        logger.error("未知模块: %s，可选: %s", module_name, ", ".join(_MODULE_FNS))
        return None, None

    llm_config = get_llm_config()
    if not llm_config and not dry_run:
        logger.warning("LLM 配置不存在，可使用 --dry-run 仅验证 prompt 构建")
        return None, None

    total_mv = values["total_mv"]
    total_cost = values["total_cost"]
    total_profit = values["total_profit"]
    total_today_profit = values["total_today_profit"]
    holdings_count = len(holdings_details)

    if dry_run:
        # 仅构建 prompt 不调用 API
        if module_name == "expert_review":
            from src.python.llm.prompts import _build_expert_review_prompt, _SYSTEM_EXPERT_REVIEW

            prompt = _build_expert_review_prompt(
                total_mv,
                total_cost,
                total_profit,
                total_today_profit,
                holdings_count,
                categories,
                holdings_details=holdings_details,
            )
            return f"[SYSTEM]\n{_SYSTEM_EXPERT_REVIEW}\n\n[USER]\n{prompt}", {"dry_run": True}
        elif module_name == "global_macro":
            from src.python.llm.prompts import _build_global_macro_prompt, _SYSTEM_GLOBAL_MACRO

            prompt = _build_global_macro_prompt(
                {},
                {},
                total_mv,
                total_profit,
                categories,
            )
            return f"[SYSTEM]\n{_SYSTEM_GLOBAL_MACRO}\n\n[USER]\n{prompt}", {"dry_run": True}
        elif module_name == "health_check":
            from src.python.llm.prompts import _build_health_check_prompt, _SYSTEM_HEALTH_CHECK

            prompt = _build_health_check_prompt(
                total_mv,
                total_cost,
                total_profit,
                total_today_profit,
                holdings_count,
                categories,
                holdings_details=holdings_details,
            )
            return f"[SYSTEM]\n{_SYSTEM_HEALTH_CHECK}\n\n[USER]\n{prompt}", {"dry_run": True}
        elif module_name == "penetration_deep":
            from src.python.llm.prompts import _build_penetration_deep_prompt, _SYSTEM_PENETRATION_DEEP

            prompt = _build_penetration_deep_prompt(
                total_mv,
                total_cost,
                total_profit,
                holdings_count,
                categories,
                holdings_details=holdings_details,
            )
            return f"[SYSTEM]\n{_SYSTEM_PENETRATION_DEEP}\n\n[USER]\n{prompt}", {"dry_run": True}
        return None, None

    # ── 真实 LLM 调用 ──
    http_client = _get_http_client()
    try:
        if module_name == "expert_review":
            content, cached = generate_expert_review(
                total_mv,
                total_cost,
                total_profit,
                total_today_profit,
                holdings_count,
                categories,
                holdings_details=holdings_details,
                force=force,
                http_client=http_client,
                llm_config=llm_config,
            )
        elif module_name == "global_macro":
            a_indices = {}
            us_indices = {}
            content, cached = generate_global_macro(
                a_indices,
                us_indices,
                total_mv,
                total_profit,
                categories,
                force=force,
                http_client=http_client,
                llm_config=llm_config,
            )
        elif module_name == "health_check":
            content, cached = generate_health_check(
                total_mv,
                total_cost,
                total_profit,
                total_today_profit,
                holdings_count,
                categories,
                holdings_details=holdings_details,
                force=force,
                http_client=http_client,
                llm_config=llm_config,
            )
        elif module_name == "penetration_deep":
            content, cached = generate_penetration_deep_analysis(
                total_mv,
                total_cost,
                total_profit,
                total_today_profit,
                holdings_count,
                categories,
                holdings_details=holdings_details,
                force=force,
                http_client=http_client,
                llm_config=llm_config,
            )
        else:
            content = None
        return content, {"cached": cached if content else False}
    except Exception as e:
        logger.error("模块 %s 调用失败: %s", module_name, e)
        return None, {"error": str(e)}
