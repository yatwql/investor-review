"""市值核算 — 今日盈亏来源分支与溢价占位单元测试。

从 `test_market_value_premium.py` 分出（按被测分支分片）：本文件覆盖腾讯恒真 /
非交易日东财 / 边界 / 溢价占位 / 外币市值各分支，其余（价格类型判定、明细生成、
溢价率）留在主分片。
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest

from src.python.core.models import Holding
from src.python.report.holdings_detail_sheet import (
    _detail_to_row_values,
)
from src.python.report.market_value import (
    _compute_detail_row,
    price_update_status,
)

from .test_market_value import (
    _mock_is_trading_day,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestTodayProfitTencentAlways(unittest.TestCase):
    """Tencent 场内资产始终计算 today_profit。"""

    def setUp(self) -> None:
        # _compute_detail_row → _determine_price_type → _is_trading_day（akshare 网络）
        # + is_market_open/is_midday_break（东方财富 push2 HTTP）。统一隔离。
        self._patch_td = patch("src.python.core.trading_calendar._is_trading_day", side_effect=_mock_is_trading_day)
        self._patch_open = patch("src.python.report.market_value.is_market_open", return_value=False)
        self._patch_midday = patch("src.python.report.market_value.is_midday_break", return_value=False)
        self._patch_td.start()
        self._patch_open.start()
        self._patch_midday.start()
        self.addCleanup(self._patch_td.stop)
        self.addCleanup(self._patch_open.stop)
        self.addCleanup(self._patch_midday.stop)

    @patch("src.python.report.market_value.get_last_trading_day")
    @patch("src.python.report.market_value.is_market_open", return_value=False)
    def test_tencent_always_calculates(self, mock_open, mock_td):
        """Tencent 无论 nav_date 是什么 → today_profit 始终计算。"""
        mock_td.return_value = "2026-06-30"
        h = Holding("证券", "长江电力", "600900", 200, 10.0)
        mkt = {
            "price": 28.5,
            "yesterday_close": 28.0,
            "price_date": "2026-06-25",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        detail = _compute_detail_row(h, mkt)
        expected = round((28.5 - 28.0) * 200, 2)
        self.assertEqual(detail.today_profit, expected)
        self.assertGreater(detail.today_profit, 0)

    @patch("src.python.report.market_value.get_last_trading_day")
    @patch("src.python.report.market_value.is_market_open", return_value=False)
    def test_tencent_empty_nav_date_calculates(self, mock_open, mock_td):
        """Tencent, nav_date 为空 → today_profit 仍计算。"""
        mock_td.return_value = "2026-06-30"
        h = Holding("证券", "长江电力", "600900", 100, 10.0)
        mkt = {
            "price": 25.5,
            "yesterday_close": 25.0,
            "price_date": "",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        detail = _compute_detail_row(h, mkt)
        expected = round((25.5 - 25.0) * 100, 2)
        self.assertEqual(detail.today_profit, expected)

    @patch("src.python.report.market_value.get_last_trading_day")
    def test_tencent_qdii_always_calculates(self, mock_td):
        """Tencent QDII ETF → today_profit 始终计算（场内逻辑）。"""
        mock_td.return_value = "2026-06-30"
        h = Holding("证券", "纳斯达克ETF", "513300", 300, 1.5)
        mkt = {
            "price": 1.8,
            "yesterday_close": 1.75,
            "price_date": "2026-06-27",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        detail = _compute_detail_row(h, mkt)
        expected = round((1.8 - 1.75) * 300, 2)
        self.assertEqual(detail.today_profit, expected)


class TestTodayProfitEdgeCases(unittest.TestCase):
    """today_profit 边界场景。"""

    def setUp(self) -> None:
        # _compute_detail_row → _determine_price_type → _is_trading_day → akshare 交易日历。
        self._patch_td = patch("src.python.core.trading_calendar._is_trading_day", side_effect=_mock_is_trading_day)
        self._patch_td.start()
        self.addCleanup(self._patch_td.stop)

    @patch("src.python.report.market_value.get_last_trading_day")
    @patch("src.python.report.market_value.is_market_open", return_value=False)
    def test_no_price_data(self, mock_open, mock_td):
        """获取行情失败（price=0）→ today_profit = 0。"""
        mock_td.return_value = "2026-06-30"
        h = Holding("支付宝", "易方达蓝筹", "005827", 100, 2.0)
        mkt = {
            "price": 0.0,
            "yesterday_close": 0.0,
            "price_date": "",
            "source": "--",
            "source_api": "",
        }
        detail = _compute_detail_row(h, mkt)
        self.assertEqual(detail.today_profit, 0.0)

    @patch("src.python.report.market_value.get_last_trading_day")
    @patch("src.python.report.market_value.is_market_open", return_value=False)
    def test_today_profit_negative(self, mock_open, mock_td):
        """本日下跌 → today_profit 为负值。"""
        mock_td.return_value = "2026-06-30"
        h = Holding("证券", "长江电力", "600900", 100, 10.0)
        mkt = {
            "price": 24.0,
            "yesterday_close": 25.0,
            "price_date": "2026-06-30",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        detail = _compute_detail_row(h, mkt)
        expected = round((24.0 - 25.0) * 100, 2)
        self.assertEqual(detail.today_profit, expected)
        self.assertLess(detail.today_profit, 0)


class TestPremiumInWriteSheet(unittest.TestCase):
    """验证 premium 在写入页签时的列值。"""

    def setUp(self) -> None:
        # _compute_detail_row → _determine_price_type → _is_trading_day → akshare 交易日历。
        self._patch_td = patch("src.python.core.trading_calendar._is_trading_day", side_effect=_mock_is_trading_day)
        self._patch_td.start()
        self.addCleanup(self._patch_td.stop)

    @patch("src.python.report.market_value.get_last_trading_day")
    @patch("src.python.report.market_value.is_market_open", return_value=False)
    def test_premium_in_excel_row(self, mock_open, mock_td):
        """写入 Excel 行时溢价率列为 '--'。"""
        mock_td.return_value = "2026-06-30"
        h = Holding("证券", "长江电力", "600900", 100, 10.0)
        mkt = {
            "price": 25.0,
            "yesterday_close": 24.5,
            "price_date": "2026-06-30",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        detail = _compute_detail_row(h, mkt)
        values = _detail_to_row_values(detail)
        self.assertEqual(values[7], "--")


class TestForeignDenominatedMarketValue(unittest.TestCase):
    """非人民币计价品种市值核算 — QDII/港股通份额按价格 × 份额直接计市值（不做汇率折算）。"""

    def setUp(self) -> None:
        # _compute_detail_row → _determine_price_type → _count_trading_days_back
        # → _is_trading_day → akshare 交易日历（真实网络）。这些用例已 mock
        # get_last_trading_day/is_market_open，但漏 _is_trading_day，补上以
        # 隔离 akshare 网络调用。
        self._patch_td = patch("src.python.core.trading_calendar._is_trading_day", side_effect=_mock_is_trading_day)
        self._patch_td.start()
        self.addCleanup(self._patch_td.stop)

    @patch("src.python.report.market_value.get_last_trading_day")
    @patch("src.python.report.market_value.is_market_open", return_value=False)
    def test_qdii_price_in_rmb_from_api(self, mock_open, mock_td):
        """QDII 价格来自 API（已为人民币计值），市值计算正确。"""
        mock_td.return_value = "2026-07-01"
        h = Holding("支付宝", "华夏纳斯达克100ETF(QDII)", "513300", 100, 2.0)
        mkt = {
            "price": 2.1,
            "yesterday_close": 2.0,
            "price_date": "2026-07-01",
            "source": "天天基金",
            "source_api": "eastmoney",
            "nav_date": "2026-07-01",
        }
        detail = _compute_detail_row(h, mkt)
        self.assertAlmostEqual(detail.market_value, 210.0, delta=0.01)
        self.assertAlmostEqual(detail.today_profit, 10.0, delta=0.01)

    @patch("src.python.report.market_value.get_last_trading_day")
    def test_qdii_today_profit_t1(self, mock_td):
        """QDII 净值日期=T-1 → today_profit=0（当前行为，待扩展）。"""
        mock_td.return_value = "2026-07-01"
        h = Holding("支付宝", "华夏纳斯达克100ETF(QDII)", "513300", 100, 2.0)
        mkt = {
            "price": 2.1,
            "yesterday_close": 2.0,
            "price_date": "2026-06-30",
            "source": "天天基金",
            "source_api": "eastmoney",
            "nav_date": "2026-06-30",
        }
        detail = _compute_detail_row(h, mkt)
        self.assertEqual(detail.today_profit, 0.0)

    @patch("src.python.report.market_value.get_last_trading_day")
    def test_price_update_status_qdii_t1_updated(self, mock_td):
        """price_update_status 正确识别 QDII T-1 为已更新。"""
        mock_td.return_value = "2026-07-01"
        h = Holding("支付宝", "华夏纳斯达克100ETF(QDII)", "513300", 100, 2.0)
        mkt = {
            "price": 2.1,
            "yesterday_close": 2.0,
            "price_date": "2026-06-30",
            "source": "天天基金",
            "source_api": "eastmoney",
            "nav_date": "2026-06-30",
        }
        detail = _compute_detail_row(h, mkt)
        updated, total, all_updated = price_update_status([detail], "2026-07-01")
        self.assertEqual(updated, 1)
        self.assertEqual(total, 1)
        self.assertTrue(all_updated)


if __name__ == "__main__":
    unittest.main()
