"""缓存刷新编排（operations / _cache_refresh）的分支补齐测试。

覆盖点：
  - 两个结果对象的 `exit_code` 三档退出码
  - `update_basic_cache`：无基金路径、有基金并行聚合（含失败与 Future 异常）
  - `_refresh_common_caches` / `_refresh_extended_caches`：成功、零结果、Future 异常
  - `_fetch_prices_and_indices`：取价失败、异常按文案归类为网络/解析/其它
  - `sector_flow_hint` 全档文案、`_get_news_top_count` 配置异常降级

线程池一律替换为**同步内联**替身（`submit` 当场执行 + 落 Future），
避免测试对线程调度与真实耗时的依赖。
"""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass

import pytest

from src.python.cache import _cache_refresh as cr
from src.python.cache import operations as ops

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class _InlinePool:
    """同步执行的线程池替身：`submit` 立即执行并把结果/异常装进 Future。"""

    def submit(self, fn, *args, **kwargs) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 — 替身要复现池的「异常封进 Future」语义
            future.set_exception(exc)
        return future


class _Reporter:
    """记录 reporter.* 调用（消息 + 级别）的替身。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def ok(self, msg: str) -> None:
        self.calls.append(("ok", msg))

    def info(self, msg: str) -> None:
        self.calls.append(("info", msg))

    def warn(self, msg: str) -> None:
        self.calls.append(("warn", msg))

    def error(self, msg: str) -> None:
        self.calls.append(("error", msg))

    def levels(self, level: str) -> list[str]:
        return [msg for lvl, msg in self.calls if lvl == level]


@dataclass
class _Holding:
    code: str
    name: str
    account: str = ""


# ── 结果对象退出码 ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, 2),
        ({"total_funds": 1}, 0),
        ({"pf_ok": 3}, 0),
        ({"total_funds": 1, "errors": ["boom"]}, 1),
        ({"ext_ok": 2, "errors": ["boom"]}, 1),
    ],
)
def test_cache_update_result_exit_code(kwargs: dict, expected: int) -> None:
    assert ops.CacheUpdateResult(**kwargs).exit_code == expected


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, 2),
        ({"total": 3}, 0),
        ({"total": 3, "errors": ["x"]}, 1),
    ],
)
def test_position_cache_result_exit_code(kwargs: dict, expected: int) -> None:
    assert ops.PositionCacheResult(**kwargs).exit_code == expected


# ── update_basic_cache ─────────────────────────────────────────


def test_update_basic_cache_without_funds_skips_fund_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """无基金持仓 → 只刷公共 + 扩展缓存，不提交基金任务。"""
    reporter = _Reporter()
    monkeypatch.setattr(ops, "_get_pool", _InlinePool)
    monkeypatch.setattr(ops, "_refresh_common_caches", lambda holdings, rep: (1, 2, 3, 4))
    seen: list[list] = []
    monkeypatch.setattr(ops, "_refresh_extended_caches", lambda holdings, funds, result, rep: seen.append(funds))

    result = ops.update_basic_cache([_Holding("600519", "贵州茅台")], reporter)

    assert (result.total_funds, result.pf_ok, result.sf_ok, result.ind_ok, result.div_ok) == (0, 1, 2, 3, 4)
    assert seen == [[]]
    assert result.exit_code == 0


def test_update_basic_cache_aggregates_fund_and_public_results(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = _Reporter()
    monkeypatch.setattr(ops, "_get_pool", _InlinePool)
    monkeypatch.setattr(
        ops,
        "_refresh_one_fund_cache",
        lambda fund: ("fund", fund.code, fund.name, True, True, 7, False),
    )
    monkeypatch.setattr(ops, "_refresh_profit_forecast_cache", lambda: ("profit_forecast", 0))
    monkeypatch.setattr(ops, "_refresh_sector_flow_cache", lambda: ("sector_flow", 0))
    monkeypatch.setattr(ops, "_refresh_industry_cache", lambda holdings: 0)
    monkeypatch.setattr(ops, "_refresh_dividend_cache", lambda holdings: 0)
    monkeypatch.setattr(ops, "_refresh_extended_caches", lambda *a: None)

    result = ops.update_basic_cache([_Holding("011506", "华夏成长")], reporter)

    assert (result.perf_ok, result.hold_ok, result.bm_ok) == (1, 1, 0)
    assert (result.pf_ok, result.sf_ok, result.ind_ok, result.div_ok) == (0, 0, 0, 0)
    assert any("华夏成长 (011506) — 业绩=OK | 持仓=7条 | 基准=未找到" == m for m in reporter.levels("ok"))
    assert "盈利预测 获取失败" in reporter.levels("warn")
    assert any(msg.startswith("行业资金流向 ") for msg in reporter.levels("warn"))
    assert "行业分类 获取失败" in reporter.levels("warn")
    assert "分红数据 获取失败" in reporter.levels("warn")


def test_update_basic_cache_records_future_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """单个任务抛异常 → 计入 errors 并告警，其余任务结果不受影响。"""
    reporter = _Reporter()
    monkeypatch.setattr(ops, "_get_pool", _InlinePool)

    def _boom(fund):
        raise RuntimeError("pool down")

    monkeypatch.setattr(ops, "_refresh_one_fund_cache", _boom)
    monkeypatch.setattr(ops, "_refresh_profit_forecast_cache", lambda: ("profit_forecast", 5))
    monkeypatch.setattr(ops, "_refresh_sector_flow_cache", lambda: ("sector_flow", 9))
    monkeypatch.setattr(ops, "_refresh_extended_caches", lambda *a: None)

    result = ops.update_basic_cache([_Holding("011506", "华夏成长")], reporter)

    assert result.errors == ["缓存刷新异常: pool down"]
    assert "基金刷新异常" in reporter.levels("warn")
    assert (result.pf_ok, result.sf_ok) == (5, 9)
    assert result.exit_code == 1


# ── _refresh_common_caches ─────────────────────────────────────


def test_common_caches_reports_success_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = _Reporter()
    monkeypatch.setattr(cr, "_get_pool", _InlinePool)
    monkeypatch.setattr(cr, "_refresh_profit_forecast_cache", lambda: ("profit_forecast", 12))
    monkeypatch.setattr(cr, "_refresh_sector_flow_cache", lambda: ("sector_flow", 30))
    monkeypatch.setattr(cr, "_refresh_industry_cache", lambda holdings: 5)
    monkeypatch.setattr(cr, "_refresh_dividend_cache", lambda holdings: 6)

    counts = cr._refresh_common_caches([_Holding("600519", "贵州茅台")], reporter)

    assert counts == (12, 30, 5, 6)
    assert reporter.levels("ok") == [
        "盈利预测 (12 只股票)",
        "行业资金流向 (30 个行业)",
        "行业分类 (5 只证券)",
        "分红数据 (6 只股票)",
    ]


def test_common_caches_warns_on_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = _Reporter()
    monkeypatch.setattr(cr, "_get_pool", _InlinePool)
    monkeypatch.setattr(cr, "_refresh_profit_forecast_cache", lambda: ("profit_forecast", 0))
    monkeypatch.setattr(cr, "_refresh_sector_flow_cache", lambda: ("sector_flow", 0))
    monkeypatch.setattr(cr, "_refresh_industry_cache", lambda holdings: 0)
    monkeypatch.setattr(cr, "_refresh_dividend_cache", lambda holdings: 0)
    monkeypatch.setattr(cr, "sector_flow_hint", lambda: "暂无数据")

    assert cr._refresh_common_caches([_Holding("600519", "贵州茅台")], reporter) == (0, 0, 0, 0)
    assert reporter.levels("warn") == [
        "盈利预测 获取失败",
        "行业资金流向 暂无数据",
        "行业分类 获取失败",
        "分红数据 获取失败",
    ]
    assert reporter.levels("ok") == []


def test_common_caches_skip_holding_scoped_tasks_without_holdings(monkeypatch: pytest.MonkeyPatch) -> None:
    """无持仓 → 只提交盈利预测与行业资金流向两项。"""
    reporter = _Reporter()
    submitted: list[str] = []
    monkeypatch.setattr(cr, "_get_pool", _InlinePool)

    def _spy(name, ret):
        def _run(*args):
            submitted.append(name)
            return ret

        return _run

    monkeypatch.setattr(cr, "_refresh_profit_forecast_cache", _spy("pf", ("profit_forecast", 1)))
    monkeypatch.setattr(cr, "_refresh_sector_flow_cache", _spy("sf", ("sector_flow", 1)))
    monkeypatch.setattr(cr, "_refresh_industry_cache", _spy("industry", 1))
    monkeypatch.setattr(cr, "_refresh_dividend_cache", _spy("dividend", 1))

    assert cr._refresh_common_caches(None, reporter) == (1, 1, 0, 0)
    assert submitted == ["pf", "sf"]


def test_common_caches_warns_on_future_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = _Reporter()
    monkeypatch.setattr(cr, "_get_pool", _InlinePool)

    def _boom():
        raise OSError("disk gone")

    monkeypatch.setattr(cr, "_refresh_profit_forecast_cache", _boom)
    monkeypatch.setattr(cr, "_refresh_sector_flow_cache", lambda: ("sector_flow", 2))

    assert cr._refresh_common_caches(None, reporter) == (0, 2, 0, 0)
    assert "盈利预测 获取失败" in reporter.levels("warn")


# ── _refresh_extended_caches ──────────────────────────────────


def test_extended_caches_reports_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = _Reporter()
    result = ops.CacheUpdateResult()
    monkeypatch.setattr(cr, "_get_pool", _InlinePool)
    monkeypatch.setattr(cr, "_refresh_news_cache", lambda holdings: 8)
    monkeypatch.setattr(cr, "_refresh_fund_manager_cache", lambda funds: 2)
    monkeypatch.setattr(cr, "_refresh_extended_cache", lambda holdings: 4)

    cr._refresh_extended_caches([_Holding("600519", "贵州茅台")], [_Holding("011506", "华夏成长")], result, reporter)

    assert (result.news_ok, result.manager_ok, result.ext_ok) == (8, 2, 4)
    assert reporter.levels("ok") == ["新闻 (8 条)", "基金经理 (2 只基金)", "风格扩展 (4 只证券)"]


def test_extended_caches_warns_when_empty_and_notes_future_error(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = _Reporter()
    result = ops.CacheUpdateResult()
    monkeypatch.setattr(cr, "_get_pool", _InlinePool)
    monkeypatch.setattr(cr, "_refresh_news_cache", lambda holdings: 0)

    def _boom(funds):
        raise RuntimeError("manager source down")

    monkeypatch.setattr(cr, "_refresh_fund_manager_cache", _boom)
    monkeypatch.setattr(cr, "_refresh_extended_cache", lambda holdings: 0)

    cr._refresh_extended_caches([_Holding("600519", "贵州茅台")], [_Holding("011506", "华夏成长")], result, reporter)

    assert (result.news_ok, result.manager_ok, result.ext_ok) == (0, 0, 0)
    assert reporter.levels("warn") == ["新闻 获取失败", "manager 刷新异常", "风格扩展 获取失败"]
    assert result.errors == ["扩展缓存刷新异常: manager source down"]


def test_extended_caches_without_holdings_skips_news_and_style(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter = _Reporter()
    result = ops.CacheUpdateResult()
    monkeypatch.setattr(cr, "_get_pool", _InlinePool)
    monkeypatch.setattr(cr, "_refresh_fund_manager_cache", lambda funds: 1)

    cr._refresh_extended_caches([], [_Holding("011506", "华夏成长")], result, reporter)

    assert (result.news_ok, result.manager_ok, result.ext_ok) == (0, 1, 0)
    assert reporter.levels("ok") == ["基金经理 (1 只基金)"]


# ── 提示文案 / 配置降级 ────────────────────────────────────────


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("connection", "连接失败"),
        ("stale", "使用上次成功数据（源不可达）"),
        ("empty", "暂无数据"),
        ("", "获取失败"),
    ],
)
def test_sector_flow_hint_maps_failure_state(monkeypatch: pytest.MonkeyPatch, failure: str, expected: str) -> None:
    import src.python.fetcher.akshare as akshare_fetcher

    monkeypatch.setattr(akshare_fetcher, "sector_flow_failure", lambda: failure)
    assert cr.sector_flow_hint() == expected


def test_news_top_count_falls_back_to_default_on_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.python.config as config_pkg

    def _boom():
        raise RuntimeError("config broken")

    monkeypatch.setattr(config_pkg, "get_config", _boom)
    assert cr._get_news_top_count() == 300


# ── 行情类缓存（价格 + 指数）──────────────────────────────────


def _patch_price_sources(monkeypatch: pytest.MonkeyPatch, *, price_side_effect=None, price_return=None) -> None:
    import src.python.fetcher.index as index_fetcher
    import src.python.fetcher.price as price_fetcher

    monkeypatch.setattr(index_fetcher, "fetch_indices", lambda: {"sh000001": 3000.0})
    monkeypatch.setattr(index_fetcher, "fetch_us_indices", lambda: {})
    if price_side_effect is not None:
        monkeypatch.setattr(price_fetcher, "fetch_market_data", price_side_effect)
    else:
        monkeypatch.setattr(price_fetcher, "fetch_market_data", lambda code, name: price_return)


def test_fetch_prices_reports_zero_price_as_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """取价返回空/零价 → 告警且不计入 price_ok。"""
    reporter = _Reporter()
    monkeypatch.setattr(ops, "_get_pool", _InlinePool)
    _patch_price_sources(monkeypatch, price_return={})

    result, details = ops._fetch_prices_and_indices([_Holding("600519", "贵州茅台")], reporter)

    assert (result.total, result.price_ok, result.a_index_count, result.us_index_count) == (1, 0, 1, 0)
    assert details == []
    assert "贵州茅台 (600519) → 失败" in reporter.levels("warn")
    assert "A 股指数: 1 个" in reporter.levels("ok")


@pytest.mark.parametrize(
    ("message", "hint"),
    [
        ("connect timed out", "网络异常"),
        ("network unreachable", "网络异常"),
        ("json parse error", "数据解析失败"),
        ("decode failed", "数据解析失败"),
        ("unexpected boom", "获取失败"),
    ],
)
def test_fetch_prices_classifies_error_hint(monkeypatch: pytest.MonkeyPatch, message: str, hint: str) -> None:
    """单品种取数异常按文案归类提示，并计入 errors。"""
    reporter = _Reporter()
    monkeypatch.setattr(ops, "_get_pool", _InlinePool)

    def _raise(code, name):
        raise RuntimeError(message)

    _patch_price_sources(monkeypatch, price_side_effect=_raise)

    result, _ = ops._fetch_prices_and_indices([_Holding("600519", "贵州茅台")], reporter)

    assert result.errors == [f"贵州茅台: {hint}"]
    assert reporter.levels("error") == [f"贵州茅台 (600519) → {hint}"]
