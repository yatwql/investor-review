"""缓存刷新族：公共缓存（盈利预测/行业资金流/行业/分红）、新闻、基金经理、扩展缓存。

从 :mod:`cache.operations` 拆出——「按数据类型刷新缓存」这一族集中在此；
更新编排（basic/position/all）、清理、统计与预热留在原模块（单向依赖：编排 → 刷新）。
"""

from __future__ import annotations

# CacheUpdateResult 定义在入口（数据类与编排同处），此处延迟导入避免模块级环
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.python.cache.operations import CacheUpdateResult

import logging

from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("invest")


_POOL: ThreadPoolExecutor | None = None


def _get_pool() -> ThreadPoolExecutor:
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cache_ops")
    return _POOL


def _refresh_one_fund_cache(fund) -> tuple:
    """刷新单只基金的排名、持仓和基准缓存。"""
    from src.python.fetcher.fund import fetch_fund_benchmark, fetch_fund_holdings, fetch_fund_rankings

    perf_result = fetch_fund_rankings(fund.code)
    perf_ok = bool(perf_result)
    hold_data = fetch_fund_holdings(fund.code)
    hold_ok = bool(hold_data and hold_data.get("holdings"))
    hold_count = len(hold_data["holdings"]) if hold_data and hold_data.get("holdings") else 0
    bm = fetch_fund_benchmark(fund.code)
    bm_ok = bool(bm and bm != "--")
    return ("fund", fund.code, fund.name, perf_ok, hold_ok, hold_count, bm_ok)


def _refresh_industry_cache(holdings: list) -> int:
    """刷新行业分类缓存（按「A 股个股」过滤，排除 00 重叠区场外基金）。"""
    from src.python.core.code_utils import is_a_share_stock
    from src.python.fetcher.industry import batch_fetch_industry_data

    codes = [h.code.strip() for h in holdings if h.code and h.code.strip() and is_a_share_stock(h.name, h.code.strip())]
    if not codes:
        return 0
    result = batch_fetch_industry_data(codes)
    return len(result)


def _refresh_dividend_cache(holdings: list) -> int:
    """刷新股票历史分红缓存（按「A 股个股」过滤，排除 00 重叠区场外基金）。"""
    from src.python.core.code_utils import is_a_share_stock
    from src.python.fetcher.akshare import get_dividend_data

    codes = [h.code.strip() for h in holdings if h.code and h.code.strip() and is_a_share_stock(h.name, h.code.strip())]
    if not codes:
        return 0
    result = get_dividend_data(codes)
    return len(result)


def _refresh_profit_forecast_cache() -> tuple[str, int]:
    """刷新盈利预测缓存。"""
    from src.python.fetcher.akshare import get_profit_forecast

    data = get_profit_forecast()
    return ("profit_forecast", len(data) if data else 0)


def _refresh_sector_flow_cache() -> tuple[str, int]:
    """刷新行业资金流向缓存。"""
    from src.python.fetcher.akshare import get_sector_fund_flow

    data = get_sector_fund_flow()
    return ("sector_flow", len(data) if data else 0)


def _sector_flow_hint() -> str:
    """根据最近一次行业资金流向失败类型返回提示文案。"""
    from src.python.fetcher.akshare import get_sector_fund_flow  # noqa: F401  # 保持 fetcher 层活跃引用
    from src.python.providers.akshare_extras import _SECTOR_FLOW_FAILURE

    if _SECTOR_FLOW_FAILURE == "connection":
        return "连接失败"
    if _SECTOR_FLOW_FAILURE == "empty":
        return "暂无数据"
    return "获取失败"


def _refresh_common_caches(
    holdings: list | None,
    reporter,
) -> tuple[int, int, int, int]:
    """刷新不依赖基金持仓的公共缓存，通过 reporter.* 输出进度。

    Args:
        holdings: 可选持仓列表，提供时额外刷新行业和分红。
        reporter: 进度报告接口。

    Returns:
        (pf_ok, sf_ok, ind_ok, div_ok)
    """
    pf_ok = sf_ok = ind_ok = div_ok = 0
    pool = _get_pool()

    f1 = pool.submit(_refresh_profit_forecast_cache)
    f2 = pool.submit(_refresh_sector_flow_cache)
    futs: list[tuple[ThreadPoolExecutor, str, str]] = [
        (f1, "profit_forecast", "盈利预测"),
        (f2, "sector_flow", "行业资金流向"),
    ]
    if holdings:
        f3 = pool.submit(_refresh_industry_cache, holdings)
        f4 = pool.submit(_refresh_dividend_cache, holdings)
        futs.extend(
            [
                (f3, "industry", "行业分类"),
                (f4, "dividend", "分红数据"),
            ]
        )

    for fut, tag, label in futs:
        try:
            if tag == "profit_forecast":
                _, pf_ok = fut.result()
                if pf_ok:
                    reporter.ok(f"盈利预测 ({pf_ok} 只股票)")
                else:
                    reporter.warn("盈利预测 获取失败")
            elif tag == "sector_flow":
                sf_ok = fut.result()[1]
                if sf_ok:
                    reporter.ok(f"行业资金流向 ({sf_ok} 个行业)")
                else:
                    reporter.warn(f"行业资金流向 {_sector_flow_hint()}")
            elif tag == "industry":
                ind_ok = fut.result()
                if ind_ok:
                    reporter.ok(f"行业分类 ({ind_ok} 只证券)")
                else:
                    reporter.warn("行业分类 获取失败")
            elif tag == "dividend":
                div_ok = fut.result()
                if div_ok:
                    reporter.ok(f"分红数据 ({div_ok} 只股票)")
                else:
                    reporter.warn("分红数据 获取失败")
        except Exception as e:
            logger.debug("%s Future 异常: %s", tag, e)
            reporter.warn(f"{label} 获取失败")

    return pf_ok, sf_ok, ind_ok, div_ok


def _get_news_top_count() -> int:
    """读取新闻最大返回条数配置（默认 300）。"""
    from src.python.config import get_config

    try:
        value = get_config().get("news_top_count", 300)
        return int(value) if value else 300
    except Exception:
        return 300


def _refresh_news_cache(holdings: list) -> int:
    """刷新财经新闻缓存：持仓关键词 → 聚合新闻（写入 news_ 前缀缓存）。

    与报告生成共用 build_holding_keywords + _expand_industry_keywords 管线，
    保证缓存键一致、后续报告生成命中缓存。

    Returns:
        成功关联的新闻条数；无持仓或关键词为空时返回 0。
    """
    from src.python.fetcher.news import aggregate_news, build_holding_keywords, news_fetch_limits
    from src.python.report.news_correlation import _expand_industry_keywords

    if not holdings:
        return 0
    keywords = build_holding_keywords(holdings, penetrated_assets=None)
    if not keywords:
        return 0
    keywords, _industry_data, lightweight_kw = _expand_industry_keywords(holdings, None, keywords)
    top_n, per_source = news_fetch_limits(_get_news_top_count())  # 抓取预算单源算式
    news_items = aggregate_news(
        keywords,
        top_n=top_n,
        per_source=per_source,
        lightweight_keywords=lightweight_kw,
    )
    return len(news_items) if news_items else 0


def _refresh_fund_manager_cache(funds: list) -> int:
    """刷新基金经理缓存：逐基金 fetch_fund_manager（写入 fund_manager_{code} 前缀缓存）。

    Returns:
        成功获取基金经理的基金数。
    """
    from src.python.fetcher.fund_manager import fetch_fund_manager

    ok = 0
    for f in funds:
        try:
            if fetch_fund_manager(f.code):
                ok += 1
        except Exception:
            logger.debug("基金经理刷新异常 [%s]: %s", getattr(f, "code", "?"), getattr(f, "name", ""))
    return ok


def _refresh_extended_cache(holdings: list) -> int:
    """刷新风格扩展数据：A 股股票扩展数据预取到 registry session_cache。

    Returns:
        需预取的 A 股去重代码数（预取本身为填充 session_cache 的尽力而为操作）。
    """
    from src.python.core.code_utils import is_a_share_stock
    from src.python.core.provider_registry import get_registry
    from src.python.report.fund_style_classify import _prefetch_extended_data

    a_share_codes = [
        h.code.strip() for h in holdings if h.code and h.code.strip() and is_a_share_stock(h.name, h.code.strip())
    ]
    unique = list(dict.fromkeys(a_share_codes))
    if not unique:
        return 0
    holdings_dicts = [{"code": h.code, "name": h.name} for h in holdings]
    _prefetch_extended_data(holdings_dicts, get_registry())
    return len(unique)


def _refresh_extended_caches(
    holdings: list,
    funds: list,
    result: CacheUpdateResult,
    reporter,
) -> None:
    """刷新扩展缓存：新闻 / 基金经理 / 风格扩展，并行执行。

    Args:
        holdings: 持仓列表（新闻/风格扩展数据源）
        funds: 基金子集（基金经理数据源；无基金时跳过）
        result: 结果对象，写入 news_ok/manager_ok/ext_ok
        reporter: 进度报告接口
    """
    pool = _get_pool()
    futs: list[tuple] = []
    if holdings:
        futs.append((pool.submit(_refresh_news_cache, holdings), "news"))
    if funds:
        futs.append((pool.submit(_refresh_fund_manager_cache, funds), "manager"))
    if holdings:
        futs.append((pool.submit(_refresh_extended_cache, holdings), "ext"))

    for fut, tag in futs:
        try:
            count = fut.result()
            if tag == "news":
                result.news_ok = count
                if count:
                    reporter.ok(f"新闻 ({count} 条)")
                else:
                    reporter.warn("新闻 获取失败")
            elif tag == "manager":
                result.manager_ok = count
                if count:
                    reporter.ok(f"基金经理 ({count} 只基金)")
                else:
                    reporter.warn("基金经理 获取失败")
            elif tag == "ext":
                result.ext_ok = count
                if count:
                    reporter.ok(f"风格扩展 ({count} 只证券)")
                else:
                    reporter.warn("风格扩展 获取失败")
        except Exception as e:
            logger.debug("%s 扩展缓存刷新异常: %s", tag, e)
            result.errors.append(f"扩展缓存刷新异常: {e}")
            reporter.warn(f"{tag} 刷新异常")
