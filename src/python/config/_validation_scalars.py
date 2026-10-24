"""标量/路径/时长类配置校验（路径、字符串、数值上限、缓存 TTL、市场时段、新闻源）。"""

from __future__ import annotations

from ._validation_common import (  # noqa: F401 — 域内复用
    _MISSING,
    _section,
)

import logging
import os

from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")


_KNOWN_NEWS_SOURCES: set[str] = {"sina", "eastmoney", "cls", "wallstreetcn", "akshare"}


_KNOWN_PROVIDER_TYPES: set[str] = {
    "price",
    "fund_rank",
    "fund_hold",
    "industry",
    "financial_report",
    "financial_indicator",
}


_KNOWN_PROVIDER_NAMES: set[str] = {
    "tencent",
    "eastmoney",
    "sina",
    "tiantian",
    "eastmoney_industry",
    "eastmoney_industry_rest",
    "datasink",
    "datasink_indicator",
    "akshare_financial",
    "hithink",
}


_STRING_CONFIG_KEYS: set[str] = {
    "holdings_dir",
    "holdings_filename",
    "output_dir",
    "llm_key_file",
    "llm_settings_file",
    "llm_providers_file",
    "data_key_file",
}


_PATH_CONFIG_KEYS: set[str] = {
    "holdings_dir",
    "output_dir",
    "llm_key_file",
    "llm_settings_file",
    "llm_providers_file",
    "data_key_file",
}


def _is_abs(path: str) -> bool:
    """增强的绝对路径判断，兼容 Windows 下 Unix 风格 /path 的识别。"""
    return os.path.isabs(path) or (len(path) > 0 and path[0] in ("/", "\\"))


def _absolutize_paths(config: dict) -> dict:
    """将配置中路径型键转为绝对路径（若为相对路径则拼接 PROJECT_ROOT）。

    使用户 config.json 中可继续使用友好的相对路径，运行时所有消费者
    拿到的均为绝对路径，彻底消除 CWD 依赖。
    """
    for key in _PATH_CONFIG_KEYS:
        val = config.get(key)
        if isinstance(val, str) and not _is_abs(val):
            config[key] = os.path.join(PROJECT_ROOT, val)
    return config


def _deabsolutize_paths(config: dict) -> dict:
    """将配置中位于项目根目录下的绝对路径键还原为相对路径（写盘前调用）。

    与 _absolutize_paths 相对：运行时内存中使用绝对路径，落盘时还原为
    相对路径，避免把本机绝对路径写入 config.json 导致跨机器不可移植。
    仅处理 PROJECT_ROOT 之下的路径；外部绝对路径（不同盘符/项目外目录）
    无法相对化或相对化会越出根目录，保持原样不变。

    Args:
        config: 待写盘的配置字典（就地修改路径型键）

    Returns:
        传入的同一 dict（便于链式调用）
    """
    for key in _PATH_CONFIG_KEYS:
        val = config.get(key)
        if not isinstance(val, str) or not _is_abs(val):
            continue
        try:
            rel = os.path.relpath(val, PROJECT_ROOT)
        except ValueError:
            # 不同盘符（Windows）无法计算相对路径，保持绝对路径
            continue
        # 位于 PROJECT_ROOT 之外（relpath 越出根目录），保持绝对路径
        if not rel or rel.startswith(".."):
            continue
        config[key] = rel.replace(os.sep, "/")
    return config


def _validate_string_configs(config: dict, issues: int) -> int:
    for key in _STRING_CONFIG_KEYS:
        val = config.get(key)
        if val is not None and not isinstance(val, str):
            logger.warning("config.json %s = %r 不是字符串类型，可能导致运行时 TypeError", key, val)
            issues += 1
    fn = config.get("holdings_filename")
    if isinstance(fn, str) and fn.strip() == "":
        logger.warning("config.json holdings_filename 为空字符串，将使用默认文件名")
        issues += 1
    return issues


def _validate_news_top_count(config: dict, issues: int) -> int:
    ntc = config.get("news_top_count")
    if ntc is None:
        return issues
    try:
        n_int = int(ntc)
        if n_int <= 0:
            logger.warning("config.json news_top_count = %r 不是正数，将使用默认值 300", ntc)
            issues += 1
    except (ValueError, TypeError):
        logger.warning("config.json news_top_count = %r 不是有效整数，将使用默认值 300", ntc)
        issues += 1
    return issues


def _validate_cache_ttl(config: dict, issues: int) -> int:
    cache_ttl, issues = _section(config, "cache_ttl", dict, "所有缓存 TTL 将使用默认值", issues)
    if cache_ttl is _MISSING:
        return issues
    for k, v in cache_ttl.items():
        try:
            val = float(v)
            if val <= 0:
                logger.warning("config.json cache_ttl.%s = %s 不是正数，将使用默认值", k, v)
                issues += 1
        except (ValueError, TypeError):
            logger.warning("config.json cache_ttl.%s = %s 不是有效数字，将使用默认值", k, v)
            issues += 1
    return issues


def _validate_news_sources(config: dict, issues: int) -> int:
    news_src, issues = _section(config, "news_sources", dict, "所有源将使用默认开关状态", issues)
    if news_src is _MISSING:
        return issues
    for key, val in news_src.items():
        if key not in _KNOWN_NEWS_SOURCES:
            logger.warning("config.json news_sources 中存在未知的源 %r，将被忽略", key)
            issues += 1
        if not isinstance(val, bool):
            logger.warning("config.json news_sources.%s = %r 不是布尔值，非空字符串/数字会被当作 True 处理", key, val)
            issues += 1
    return issues


def _validate_preferred_provider(config: dict, issues: int) -> int:
    pref, issues = _section(config, "preferred_provider", dict, "配置无效", issues)
    if pref is _MISSING:
        return issues
    for data_type, provider in pref.items():
        if data_type not in _KNOWN_PROVIDER_TYPES:
            logger.warning(
                "config.json preferred_provider 中存在未知的数据类型 %r，有效值: %s",
                data_type,
                ", ".join(sorted(_KNOWN_PROVIDER_TYPES)),
            )
            issues += 1
        if provider not in _KNOWN_PROVIDER_NAMES:
            logger.warning(
                "config.json preferred_provider.%s = %r 不是已知的 provider，有效值: %s",
                data_type,
                provider,
                ", ".join(sorted(_KNOWN_PROVIDER_NAMES)),
            )
            issues += 1
    return issues


def _validate_market_hours(config: dict, issues: int) -> int:
    mha = config.get("market_hour_aware")
    if mha is not None and (not isinstance(mha, list) or not all(isinstance(x, str) for x in mha)):
        logger.warning("config.json market_hour_aware = %r 不是字符串列表", mha)
        issues += 1
    mht = config.get("market_hour_ttl")
    if mht is not None:
        try:
            mht_int = int(mht)
            if mht_int < 30:
                logger.warning("config.json market_hour_ttl = %s 小于 30 秒，将被钳制到 30 秒", mht)
                issues += 1
        except (ValueError, TypeError):
            logger.warning("config.json market_hour_ttl = %r 不是有效整数，将使用默认值 30", mht)
            issues += 1
    mh = config.get("market_hours")
    if mh is not None:
        if not isinstance(mh, dict):
            logger.warning("config.json market_hours = %r 不是对象(dict)，将使用内置默认时段", mh)
            issues += 1
        else:
            for time_key in ("start", "end"):
                tv = mh.get(time_key)
                if tv is not None and not isinstance(tv, str):
                    logger.warning("config.json market_hours.%s = %r 不是字符串", time_key, tv)
                    issues += 1
    return issues


def _validate_holdings_start_date(config: dict, issues: int) -> int:
    """验证 holdings_start_date 配置（组合建仓日期，YYYY-MM-DD，可选）。

    空字符串/缺失视为未配置（近似年化不计算）；非空且格式非法时告警。
    该日期仅用于成本流水子模块的快照近似（单笔建仓假设）。
    """
    raw = config.get("holdings_start_date")
    if raw is None:
        return issues
    if not isinstance(raw, str):
        logger.warning("config.json holdings_start_date = %r 应为字符串（YYYY-MM-DD），将忽略", raw)
        return issues + 1
    text = raw.strip()
    if not text:
        return issues  # 空字符串 = 未配置，正常
    from datetime import date

    try:
        date.fromisoformat(text)
    except ValueError:
        logger.warning("config.json holdings_start_date = %r 不是有效日期（应为 YYYY-MM-DD），将忽略", text)
        issues += 1
    return issues
