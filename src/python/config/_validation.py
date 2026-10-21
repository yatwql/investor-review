"""配置校验模块 — config.json 配置校验函数集。

集中管理所有配置校验逻辑。
每个 _validate_* 函数接收 (config, issues) 并返回 issues 计数。
"""

from __future__ import annotations

from ._validation_common import (  # noqa: F401 — 共用原语
    _FETCH_MODES,
    _MISSING,
    _section,
)

import logging


logger = logging.getLogger("invest")

# ═══════════════════════════════════════════════════════════════════
# 配置校验常量
# ═══════════════════════════════════════════════════════════════════


# 需要绝对化的路径型配置键（不包含纯文件名 holdings_filename）


# ═══════════════════════════════════════════════════════════════════
# 校验辅助函数
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# 各配置段的校验函数
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# 配置校验入口
# ═══════════════════════════════════════════════════════════════════


from ._validation_llm import (  # noqa: E402, F401 — 兼容既有导入面
    _validate_enable_boards,
    _validate_enable_llm,
    _validate_llm_report_depth,
)

from ._validation_sections import (  # noqa: E402, F401 — 兼容既有导入面
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

from ._validation_scalars import (  # noqa: E402, F401 — 兼容既有导入面
    _KNOWN_NEWS_SOURCES,
    _KNOWN_PROVIDER_NAMES,
    _KNOWN_PROVIDER_TYPES,
    _PATH_CONFIG_KEYS,
    _STRING_CONFIG_KEYS,
    _absolutize_paths,
    _deabsolutize_paths,
    _is_abs,
    _validate_cache_ttl,
    _validate_holdings_start_date,
    _validate_market_hours,
    _validate_news_sources,
    _validate_news_top_count,
    _validate_preferred_provider,
    _validate_string_configs,
)


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
