"""配置校验入口 — 组合各域校验函数并统计问题数。

具体校验实现按域拆在 `_validation_llm` / `_validation_sections` / `_validation_scalars`；
本模块只保留入口，不复制实现、不转出私有校验函数。
"""

from __future__ import annotations

import logging

from ._validation_llm import (
    _validate_enable_boards,
    _validate_enable_llm,
    _validate_llm_report_depth,
)
from ._validation_scalars import (
    _validate_cache_ttl,
    _validate_holdings_start_date,
    _validate_market_hours,
    _validate_news_sources,
    _validate_news_top_count,
    _validate_preferred_provider,
    _validate_string_configs,
)
from ._validation_sections import (
    _validate_benchmark_indices,
    _validate_comparison_candidates,
    _validate_comparison_indices,
    _validate_discipline_config,
    _validate_fund_fee_fallback,
    _validate_history_fetch_mode,
    _validate_history_lookback_days,
    _validate_rebalance_config,
    _validate_report_section_order,
    _validate_user_fund_benchmarks,
    _validate_whatif_benchmark_index,
)

logger = logging.getLogger("invest")


def validate_config(config: dict | None = None) -> int:
    """校验 config.json 中的常见配置错误，输出 WARNING 日志。

    Args:
        config: 已合并的配置字典。为 None 时自动调用 get_config()。

    Returns:
        发现的问题数量（方便测试断言）。
    """
    if config is None:
        from src.python.config._core import get_config

        config = get_config()
    issues = 0
    issues = _validate_string_configs(config, issues)
    issues = _validate_news_top_count(config, issues)
    issues = _validate_llm_report_depth(config, issues)
    issues = _validate_cache_ttl(config, issues)
    issues = _validate_news_sources(config, issues)
    issues = _validate_preferred_provider(config, issues)
    issues = _validate_user_fund_benchmarks(config, issues)
    issues = _validate_fund_fee_fallback(config, issues)
    issues = _validate_whatif_benchmark_index(config, issues)
    issues = _validate_enable_boards(config, issues)
    issues = _validate_market_hours(config, issues)
    issues = _validate_report_section_order(config, issues)
    issues = _validate_benchmark_indices(config, issues)
    issues = _validate_history_fetch_mode(config, issues)
    issues = _validate_history_lookback_days(config, issues)
    issues = _validate_comparison_indices(config, issues)
    issues = _validate_comparison_candidates(config, issues)
    issues = _validate_rebalance_config(config, issues)
    issues = _validate_discipline_config(config, issues)
    issues = _validate_holdings_start_date(config, issues)
    issues = _validate_enable_llm(issues)
    if issues:
        logger.warning("config.json 共检测到 %d 个配置问题，请检查上述警告项", issues)
    return issues
