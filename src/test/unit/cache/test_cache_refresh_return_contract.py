"""单类缓存刷新函数的返回值契约测试（`_cache_refresh` 逐个刷新入口）。

编排层（`_refresh_common_caches` / `_refresh_extended_caches`）的用例把这些函数整体替换成
返回固定值的桩，故「按数据类型刷新」的函数自身返回什么从未被断言——返回 `None` 也
照样绿。本文件逐个直连取数函数，断言：

  - 基金：返回 `("fund", code, name, perf_ok, hold_ok, hold_count, bm_ok)` 七元组，
    空持仓 / `"--"` 基准 / 持仓字段缺失各自落到对应的 False 与计数 0
  - 行业 / 分红：返回条数（无 A 股标的时是整数 0 且不发起取数）
  - 盈利预测 / 行业资金流：返回带标签的 `(tag, 条数)` 二元组，空数据计 0
  - 新闻：无持仓或无关键词返回 0，有关联新闻返回条数
  - 基金经理：只计成功取到的基金数，单只异常不中断整批

取数函数都在被测函数的函数体内 import，故一律 patch **调用点所在模块**（`fetcher.*` /
`report.news_correlation`）的属性。
"""

from __future__ import annotations

import pytest

from src.python.cache._cache_refresh import (
    _refresh_dividend_cache,
    _refresh_fund_manager_cache,
    _refresh_industry_cache,
    _refresh_news_cache,
    _refresh_one_fund_cache,
    _refresh_profit_forecast_cache,
    _refresh_sector_flow_cache,
)
from src.python.core.models import Holding

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_STOCK = Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)
_OTC_FUND = Holding(
    account="支付宝-场外基金账户", name="广发多因子灵活配置混合", code="002943", shares=2000, cost_price=3.6
)
_HOLDINGS = [_STOCK, _OTC_FUND]
_FUND = Holding(account="证券", name="华夏成长", code="011506", shares=1000, cost_price=1.5)


# ── 基金：七元组逐位语义 ──────────────────────────────────────


def test_fund_cache_flags_complete_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """排名/持仓/基准三项都取到 → 三个 True，持仓条数为实际条数。"""
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_rankings", lambda code: [{"rank": 1}])
    monkeypatch.setattr(
        "src.python.fetcher.fund.fetch_fund_holdings",
        lambda code: {"holdings": [{"code": "600519"}, {"code": "000858"}]},
    )
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_benchmark", lambda code: "沪深300")

    assert _refresh_one_fund_cache(_FUND) == ("fund", "011506", "华夏成长", True, True, 2, True)


def test_fund_cache_flags_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """空排名 / 空持仓列表 / 基准占位 `"--"` → 三个 False，持仓条数 0。"""
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_rankings", lambda code: {})
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_holdings", lambda code: {"holdings": []})
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_benchmark", lambda code: "--")

    assert _refresh_one_fund_cache(_FUND) == ("fund", "011506", "华夏成长", False, False, 0, False)


def test_fund_cache_tolerates_missing_holdings_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """持仓取数整包为 None（源不可达）→ 仍返回七元组，持仓位为 False/0。"""
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_rankings", lambda code: [{"rank": 3}])
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_holdings", lambda code: None)
    monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_benchmark", lambda code: None)

    assert _refresh_one_fund_cache(_FUND) == ("fund", "011506", "华夏成长", True, False, 0, False)


# ── 行业 / 分红：条数返回值 ──────────────────────────────────


def test_industry_cache_returns_fetched_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """行业分类取到 2 条 → 返回 2（而非取数结果本身或 None）。"""
    monkeypatch.setattr(
        "src.python.fetcher.industry.batch_fetch_industry_data",
        lambda codes: {"600900": "电力", "600519": "白酒"},
    )

    assert _refresh_industry_cache(_HOLDINGS) == 2


def test_industry_cache_returns_zero_without_a_share_stocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """只有场外基金 → 返回整数 0，且不发起取数。"""
    calls: list[list[str]] = []

    def _record(codes: list[str]) -> dict:
        calls.append(codes)
        return {}

    monkeypatch.setattr("src.python.fetcher.industry.batch_fetch_industry_data", _record)

    assert _refresh_industry_cache([_OTC_FUND]) == 0
    assert calls == []


def test_dividend_cache_returns_fetched_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """历史分红取到 2 条 → 返回 2。"""
    monkeypatch.setattr(
        "src.python.fetcher.akshare.get_dividend_data",
        lambda codes: {"600900": [{"year": 2024}], "600519": [{"year": 2023}, {"year": 2024}]},
    )

    assert _refresh_dividend_cache(_HOLDINGS) == 2


def test_dividend_cache_returns_zero_without_a_share_stocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """只有场外基金 → 返回整数 0，且不发起取数。"""
    calls: list[list[str]] = []

    def _record(codes: list[str]) -> dict:
        calls.append(codes)
        return {}

    monkeypatch.setattr("src.python.fetcher.akshare.get_dividend_data", _record)

    assert _refresh_dividend_cache([_OTC_FUND]) == 0
    assert calls == []


# ── 盈利预测 / 行业资金流：带标签的二元组 ─────────────────────


def test_profit_forecast_cache_returns_tagged_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """取到 2 只股票的预测 → ("profit_forecast", 2)。"""
    monkeypatch.setattr(
        "src.python.fetcher.akshare.get_profit_forecast",
        lambda: {"600900": [{"year": 2025}], "600519": [{"year": 2025}]},
    )

    assert _refresh_profit_forecast_cache() == ("profit_forecast", 2)


def test_profit_forecast_cache_tags_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """取数为 None → ("profit_forecast", 0)（标签仍在，调用方按 tag 分派）。"""
    monkeypatch.setattr("src.python.fetcher.akshare.get_profit_forecast", lambda: None)

    assert _refresh_profit_forecast_cache() == ("profit_forecast", 0)


def test_sector_flow_cache_returns_tagged_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """取到 2 个行业 → ("sector_flow", 2)。"""
    monkeypatch.setattr(
        "src.python.fetcher.akshare.get_sector_fund_flow",
        lambda: {"电力": {"net": 1.0}, "白酒": {"net": -1.0}},
    )

    assert _refresh_sector_flow_cache() == ("sector_flow", 2)


def test_sector_flow_cache_tags_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """取数为空 dict → ("sector_flow", 0)。"""
    monkeypatch.setattr("src.python.fetcher.akshare.get_sector_fund_flow", lambda: {})

    assert _refresh_sector_flow_cache() == ("sector_flow", 0)


# ── 新闻：条数返回值 ─────────────────────────────────────────


def _patch_news_pipeline(monkeypatch: pytest.MonkeyPatch, *, keywords: dict, news_items: list) -> None:
    monkeypatch.setattr(
        "src.python.fetcher.news.build_holding_keywords",
        lambda holdings, penetrated_assets=None: keywords,
    )
    monkeypatch.setattr(
        "src.python.fetcher.news.expand_industry_keywords",
        lambda holdings, industry, kw: (kw, None, []),
    )
    monkeypatch.setattr("src.python.fetcher.news.news_fetch_limits", lambda top: (10, 2))
    monkeypatch.setattr(
        "src.python.fetcher.news.aggregate_news",
        lambda kw, **kwargs: list(news_items),
    )


def test_news_cache_returns_aggregated_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """有关联新闻 → 返回条数（不是 None，也不是 0 的固定路径）。"""
    _patch_news_pipeline(
        monkeypatch,
        keywords={"长江电力": ["长江电力"]},
        news_items=[{"title": "a"}, {"title": "b"}],
    )

    assert _refresh_news_cache(_HOLDINGS) == 2


def test_news_cache_returns_zero_without_holdings() -> None:
    """无持仓 → 返回 0（不进入关键词管线）。"""
    assert _refresh_news_cache([]) == 0


def test_news_cache_returns_zero_without_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    """持仓存在但抽不出关键词 → 返回 0，即使新闻源能返回条目。"""
    _patch_news_pipeline(monkeypatch, keywords={}, news_items=[{"title": f"n{i}"} for i in range(5)])

    assert _refresh_news_cache(_HOLDINGS) == 0


# ── 基金经理：成功计数 ───────────────────────────────────────


def test_fund_manager_cache_counts_only_successful_fetches(monkeypatch: pytest.MonkeyPatch) -> None:
    """3 只基金（命中 / 空结果 / 抛异常）→ 只计 1，异常不中断整批。"""

    def _fetch(code: str) -> bool:
        if code == "000001":
            raise RuntimeError("源异常")
        return code == "011506"

    monkeypatch.setattr("src.python.fetcher.fund_manager.fetch_fund_manager", _fetch)
    funds = [
        Holding(account="证券", name="华夏成长", code="011506", shares=1000, cost_price=1.5),
        Holding(account="证券", name="华夏蓝筹", code="000002", shares=500, cost_price=2.0),
        Holding(account="证券", name="华夏回报", code="000001", shares=500, cost_price=1.0),
    ]

    assert _refresh_fund_manager_cache(funds) == 1
