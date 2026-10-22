"""LLM 相关配置校验（开关、报告深度、模块/线路、缓存 TTL 之外的 LLM 语义）。"""

from __future__ import annotations

import logging

from src.python.core.registry import get_known_enabled_llm_keys

logger = logging.getLogger("invest")


def _validate_llm_report_depth(config: dict, issues: int) -> int:
    """校验报告深度档位取值（非法时运行时按 standard 档回落并告警，此处仅登记问题）。"""
    raw = config.get("llm_report_depth")
    if raw is None:
        return issues
    from src.python.llm.depth_profile import REPORT_DEPTH_DEFAULT, REPORT_DEPTH_LEVELS

    valid = isinstance(raw, str) and raw.strip().lower() in REPORT_DEPTH_LEVELS
    if not valid:
        logger.warning(
            "config.json llm_report_depth = %r 不是合法档位（可选 %s），将按 %s 档处理",
            raw,
            " / ".join(REPORT_DEPTH_LEVELS),
            REPORT_DEPTH_DEFAULT,
        )
        issues += 1
    return issues


def _validate_enable_boards(config: dict, issues: int) -> int:
    """验证章节可见性配置（enable_fund_deep_analysis / enable_news / enable_history /
    enable_portfolio_evolution / enable_action）。

    enable_action（行动建议独立章）默认开，缺失视为 True（沿用默认值），
    类型校验逻辑与其余 enable_xxx 一致。
    """
    for key in (
        "enable_fund_deep_analysis",
        "enable_news",
        "enable_history",
        "enable_portfolio_evolution",
        "enable_action",
    ):
        val = config.get(key)
        if val is None:
            continue  # 缺失视为默认值（各章节可见性开关默认 True）
        if not isinstance(val, bool):
            logger.warning("config.json %s = %r 不是布尔值，将使用默认值", key, val)
            issues += 1
    return issues


def _validate_enable_llm(issues: int) -> int:
    """验证 llm_settings.json 中 enabled_llm 字典的子键。

    仅检查格式/拼写错误，不判断业务语义（全关正常——可能是用户主动关闭
    所有 LLM 报告模块但仍需 news_correlation）。缺失视为正常（默认启用）。
    """
    from src.python.config._llm_settings import get_llm_config

    llm_config = get_llm_config()
    if not llm_config:
        return issues
    enabled_map = llm_config.get("enabled_llm")
    if enabled_map is None:
        return issues  # 缺失正常
    if not isinstance(enabled_map, dict):
        logger.warning("llm_settings.json enabled_llm = %r 不是字典", enabled_map)
        return issues + 1

    known_keys = get_known_enabled_llm_keys()
    unknown = [k for k in enabled_map if k not in known_keys]
    if unknown:
        logger.warning("llm_settings.json enabled_llm 中存在未知模块 %s，请检查拼写", unknown)
        issues += 1
    return issues
