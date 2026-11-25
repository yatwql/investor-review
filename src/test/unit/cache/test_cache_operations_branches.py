"""缓存编排的边角分支（`cache/operations`）：分市场明细、清理与统计、新资产预热。

本层的统一口径是「统计/预热都是旁路」：目录不可读、单文件取大小失败、行情取不到，
都只让对应条目降级（pending / 0 / warn），不得把面板或报告打崩。
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.python.cache import operations as ops

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class _Holder:
    def __init__(self, code: str, name: str, account: str = "A") -> None:
        self.code = code
        self.name = name
        self.account = account


class _Reporter:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.oks: list[str] = []
        self.warns: list[str] = []

    def info(self, msg: str) -> None:
        self.infos.append(msg)

    def ok(self, msg: str) -> None:
        self.oks.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)


class TestMarketBreakdown:
    def test_no_holdings_returns_none(self):
        assert ops._market_breakdown([], [], "T") is None

    def test_detail_rows_are_deduped_by_code(self, monkeypatch):
        """同代码的重复明细只认第一条，空代码行直接跳过。"""
        monkeypatch.setattr("src.python.report.market_value.classify_holdings", lambda h: {"场内股票": h})
        monkeypatch.setattr("src.python.report.market_value._determine_price_type", lambda *a: "场内收盘价(T)")
        monkeypatch.setattr("src.python.report.market_value.price_update_status", lambda rows, day: [True])
        details = [
            {"code": "", "name": "", "price": 0},
            {"code": "600900", "name": "长江电力", "price": 28.0, "nav_date": "T"},
            {"code": "600900", "name": "重复", "price": 99.0, "nav_date": "T"},
        ]

        breakdown = ops._market_breakdown([_Holder("600900", "长江电力")], details, "T")

        assert breakdown[0]["total"] == 1
        assert breakdown[0]["latest"] == 1

    def test_holding_without_detail_lands_in_pending(self, monkeypatch):
        """持仓有但明细缺该代码 → 进 pending 并标「无有效行情」（不是静默丢行）。"""
        monkeypatch.setattr("src.python.report.market_value.classify_holdings", lambda h: {"场内股票": h})
        monkeypatch.setattr("src.python.report.market_value._determine_price_type", lambda *a: "场内收盘价(T)")
        monkeypatch.setattr("src.python.report.market_value.price_update_status", lambda rows, day: [True])

        breakdown = ops._market_breakdown([_Holder("000001", "平安银行")], [], "T")

        assert breakdown[0]["pending"] == [
            {"code": "000001", "name": "平安银行", "label": "无有效行情", "nav_date": ""}
        ]

    def test_pending_when_price_not_latest(self, monkeypatch):
        """价位未更新（盘中/滞后口径）→ 计入 pending 而不是 latest。"""
        monkeypatch.setattr("src.python.report.market_value.classify_holdings", lambda h: {"QDII": h})
        monkeypatch.setattr("src.python.report.market_value._determine_price_type", lambda *a: "官方净值(T-1)")
        monkeypatch.setattr("src.python.report.market_value.price_update_status", lambda rows, day: [False])
        details = [{"code": "000001", "name": "", "price": 1.5, "nav_date": "T-1"}]

        breakdown = ops._market_breakdown([_Holder("000001", "华夏全球")], details, "T")

        assert breakdown[0]["latest"] == 0
        assert breakdown[0]["pending"][0]["label"] == "官方净值(T-1)"
        assert breakdown[0]["labels"]["官方净值(T-1)"] == 1

    def test_groups_follow_fixed_order(self, monkeypatch):
        """分市场条目顺序固定（场内 → 国内场外 → QDII），与持仓输入顺序无关。"""
        monkeypatch.setattr(
            "src.python.report.market_value.classify_holdings",
            lambda h: {"QDII": [h[0]], "场内股票": [h[1]]},
        )
        monkeypatch.setattr("src.python.report.market_value._determine_price_type", lambda *a: "官方净值(T)")
        monkeypatch.setattr("src.python.report.market_value.price_update_status", lambda rows, day: [True])
        holdings = [_Holder("000001", "华夏全球"), _Holder("600900", "长江电力")]
        details = [
            {"code": "000001", "name": "", "price": 1.5, "nav_date": "T"},
            {"code": "600900", "name": "长江电力", "price": 28.0, "nav_date": "T"},
        ]

        breakdown = ops._market_breakdown(holdings, details, "T")

        assert [item["group"] for item in breakdown] == ["场内", "QDII"]


class TestJudgeAfterRefresh:
    def test_no_holdings_returns_empty_pair(self):
        assert ops._judge_after_refresh([], []) == ("", None)


class TestCleanupCache:
    def test_reports_removed_count(self):
        reporter = _Reporter()
        with (
            patch("src.python.cache.cleanup_expired", return_value=3),
            patch("src.python.cache.get_cache_dir", return_value="/tmp/cache"),
        ):
            assert ops.cleanup_cache(reporter) == 3

        assert any("已删除 3 个" in msg for msg in reporter.oks)

    def test_reports_nothing_to_clean(self):
        reporter = _Reporter()
        with (
            patch("src.python.cache.cleanup_expired", return_value=0),
            patch("src.python.cache.get_cache_dir", return_value="/tmp/cache"),
        ):
            assert ops.cleanup_cache(reporter) == 0

        assert any("无需清理" in msg for msg in reporter.infos)


class TestCacheStats:
    def test_hit_rate_reported_when_samples_exist(self):
        reporter = _Reporter()
        raw = {"total_files": 2, "total_size_bytes": 2048, "by_prefix": {}, "top_by_size": []}
        with (
            patch("src.python.cache.get_cache_stats", return_value=raw),
            patch("src.python.cache.get_cache_hit_rate", return_value={"total": 10, "rate": 0.42}),
            patch("src.python.cache.cleanup_expired", return_value=0),
        ):
            stats = ops.get_cache_stats(reporter)

        assert stats.hit_rate == pytest.approx(42.0)
        assert stats.hit_total == 10
        assert any("命中率: 42.0%" in msg for msg in reporter.infos)

    def test_no_samples_skips_hit_rate_line(self):
        reporter = _Reporter()
        raw = {"total_files": 0, "total_size_bytes": 0}
        with (
            patch("src.python.cache.get_cache_stats", return_value=raw),
            patch("src.python.cache.get_cache_hit_rate", return_value={"total": 0, "rate": 0.0}),
            patch("src.python.cache.cleanup_expired", return_value=0),
        ):
            stats = ops.get_cache_stats(reporter)

        assert stats.hit_total == 0
        assert not any("命中率" in msg for msg in reporter.infos)


class TestDirFileStats:
    def test_suffix_filter_applies(self, tmp_path):
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "b.txt").write_text("x", encoding="utf-8")

        files, size = ops._dir_file_stats(str(tmp_path), suffix=".json")

        assert files == 1
        assert size == 2

    def test_subdirectory_is_not_counted(self, tmp_path):
        (tmp_path / "sub").mkdir()

        assert ops._dir_file_stats(str(tmp_path)) == (0, 0)

    def test_size_lookup_failure_skips_file(self, tmp_path, monkeypatch):
        """单文件取大小失败（并发删除）→ 跳过该文件，其余照计。"""
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        real_getsize = os.path.getsize

        def _flaky(path):
            if path.endswith("a.json"):
                raise OSError("vanished")
            return real_getsize(path)

        monkeypatch.setattr(ops.os.path, "getsize", _flaky)

        assert ops._dir_file_stats(str(tmp_path)) == (0, 0)

    def test_missing_directory_returns_zero(self, tmp_path):
        assert ops._dir_file_stats(str(tmp_path / "absent")) == (0, 0)


class TestWarmNewAssetCaches:
    def _patches(self, *, fund: bool, price: float, rankings, holdings, industry):
        return (
            patch("src.python.cache.check_and_refresh_caches", return_value=["600900"]),
            patch("src.python.fetcher.price.fetch_market_data", return_value={"price": price}),
            patch("src.python.fetcher.fund.fetch_fund_rankings", return_value=rankings),
            patch("src.python.fetcher.fund.fetch_fund_holdings", return_value=holdings),
            patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value=industry),
            patch("src.python.core.code_utils.is_fund_holding", return_value=fund),
        )

    def test_all_fetch_failures_warn_without_raising(self):
        """行情/业绩/持仓/行业全无数据 → 逐项 warn，流程照走完。"""
        reporter = _Reporter()
        patches = self._patches(fund=True, price=0.0, rankings={}, holdings={}, industry={})
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            codes = ops.warm_new_asset_caches([_Holder("600900", "长江电力")], reporter)

        assert codes == ["600900"]
        assert any("行情 长江电力 获取失败" in w for w in reporter.warns)
        assert any("业绩排名 长江电力 获取失败" in w for w in reporter.warns)
        assert any("持仓明细 长江电力 无数据" in w for w in reporter.warns)
        assert any("行业 长江电力 无数据" in w for w in reporter.warns)

    def test_fund_path_success_messages(self):
        reporter = _Reporter()
        patches = self._patches(
            fund=True,
            price=28.0,
            rankings={"rank": 1},
            holdings={"holdings": [{"code": "600900"}]},
            industry={"600900": {"industry": "电力"}},
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            ops.warm_new_asset_caches([_Holder("600900", "长江电力")], reporter)

        assert any("行情 长江电力" in msg for msg in reporter.oks)
        assert any("业绩排名 长江电力" in msg for msg in reporter.oks)
        assert any("持仓明细 长江电力 1 条" in msg for msg in reporter.oks)
        assert any("行业 长江电力 电力" in msg for msg in reporter.oks)

    def test_unknown_industry_label_falls_back(self):
        reporter = _Reporter()
        patches = self._patches(fund=False, price=28.0, rankings={}, holdings={}, industry={"600900": {}})
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            ops.warm_new_asset_caches([_Holder("600900", "长江电力")], reporter)

        assert any("行业 长江电力 未知" in msg for msg in reporter.oks)

    def test_code_missing_from_holdings_uses_code_as_name(self):
        """预热代码不在持仓映射里 → 用代码当显示名（不让名称变空串）。"""
        reporter = _Reporter()
        patches = self._patches(fund=False, price=28.0, rankings={}, holdings={}, industry={})
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            ops.warm_new_asset_caches([], reporter)

        assert any("600900" in msg for msg in reporter.infos)

    def test_unexpected_error_keeps_processed_codes(self, monkeypatch):
        """预热中途异常 → 记警告并返回已处理的代码表（调用方据此继续生成报告）。"""
        reporter = _Reporter()
        monkeypatch.setattr("src.python.cache.check_and_refresh_caches", lambda h: ["600900"])
        monkeypatch.setattr(
            "src.python.fetcher.price.fetch_market_data",
            MagicMock(side_effect=RuntimeError("probe fault")),
        )

        assert ops.warm_new_asset_caches([_Holder("600900", "长江电力")], reporter) == ["600900"]


class TestUpdateBasicCacheSuccessBranches:
    """全成功分支：基金业绩/持仓/基准、行业资金流向、分红数据都计数成功。"""

    def test_all_domains_succeed(self):
        reporter = _Reporter()
        fund = _Holder("000001", "基金A")
        with (
            patch("src.python.cache.clear_by_group"),
            patch("src.python.core.code_utils.is_fund_holding", return_value=True),
            patch(
                "src.python.cache.operations._refresh_one_fund_cache",
                return_value=("", "000001", "基金A", True, True, 3, True),
            ),
            patch("src.python.cache.operations._refresh_profit_forecast_cache", return_value=("d", 5)),
            patch("src.python.cache.operations._refresh_sector_flow_cache", return_value=("d", 4)),
            patch("src.python.cache.operations._refresh_industry_cache", return_value=10),
            patch("src.python.cache.operations._refresh_dividend_cache", return_value=6),
            patch("src.python.cache.operations._refresh_extended_caches"),
        ):
            result = ops.update_basic_cache([fund], reporter)

        assert (result.perf_ok, result.hold_ok, result.bm_ok) == (1, 1, 1)
        assert result.sf_ok == 4
        assert result.div_ok == 6
        assert any("行业资金流向 (4 个行业)" in msg for msg in reporter.oks)
        assert any("分红数据 (6 只股票)" in msg for msg in reporter.oks)

    def test_empty_domains_warn(self):
        reporter = _Reporter()
        fund = _Holder("000001", "基金A")
        with (
            patch("src.python.cache.clear_by_group"),
            patch("src.python.core.code_utils.is_fund_holding", return_value=True),
            patch(
                "src.python.cache.operations._refresh_one_fund_cache",
                return_value=("", "000001", "基金A", False, False, 0, False),
            ),
            patch("src.python.cache.operations._refresh_profit_forecast_cache", return_value=("d", 0)),
            patch("src.python.cache.operations._refresh_sector_flow_cache", return_value=("d", 0)),
            patch("src.python.cache.operations._refresh_industry_cache", return_value=0),
            patch("src.python.cache.operations._refresh_dividend_cache", return_value=0),
            patch("src.python.cache.operations._refresh_extended_caches"),
        ):
            result = ops.update_basic_cache([fund], reporter)

        assert result.pf_ok == 0
        assert any("盈利预测 获取失败" in msg for msg in reporter.warns)
        assert any("分红数据 获取失败" in msg for msg in reporter.warns)
