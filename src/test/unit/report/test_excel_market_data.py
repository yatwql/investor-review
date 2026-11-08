"""excel_market_data 成本流水组装层单元测试。

测试目标：
  - _build_flow_data — 成本流水子模块开关门控 + 无流水 available=False 占位契约
  - resolve_market_data — fund_flow_data 注入 data 字典（汇总/持仓明细与分类页签渲染数据源）

功能开关 `cost_lots` 对应 _build_flow_data 的 enable_cost_lots：
False → None（汇总/持仓明细与分类页签保持既有输出）；True → 计算 fund_flow_data 契约。
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.python.report.excel_market_data import (
    _build_flow_data,
    _resolve_holdings_start_date,
    resolve_market_data,
)
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestBuildFlowData(unittest.TestCase):
    """_build_flow_data 开关门控与快照近似/真实流水契约。"""

    def test_none_when_switch_disabled(self):
        """开关关闭（enable_cost_lots=False）→ 返回 None，不调用成本流水计算。"""
        with patch("src.python.analysis.cost_flow.build_fund_flow_data") as mock_bffd:
            result = _build_flow_data(False, [MagicMock()], [], [], [])
        self.assertIsNone(result)
        mock_bffd.assert_not_called()

    def test_approximate_contract_when_no_flows(self):
        """开关开启但无流水 → 返回快照近似契约（approximate=True，成本分档仍可用）。"""
        holdings = [MagicMock()]
        with patch(
            "src.python.analysis.cost_flow.build_approximate_fund_flow_data",
            return_value={"available": False, "approximate": True},
        ) as mock_bap:
            result = _build_flow_data(True, None, None, holdings, [])
        self.assertEqual(result, {"available": False, "approximate": True})
        args, kwargs = mock_bap.call_args
        self.assertEqual(args[0], holdings)  # 位置参数 0：holdings
        self.assertEqual(args[1], {})  # 位置参数 1：current_prices（无行情明细）
        self.assertIsNone(kwargs.get("start_date"))  # 默认未配置建仓日期

    def test_passes_current_prices_when_flows_present(self):
        """开关开启且有流水 → 以行情明细构建代码→市价映射传入真实成本流水计算。"""
        holdings = [MagicMock()]
        detail = MagicMock()
        detail.code = "600519"
        detail.price = 1500.0
        with patch("src.python.analysis.cost_flow.build_fund_flow_data", return_value={"available": True}) as mock_bffd:
            result = _build_flow_data(True, [MagicMock()], [MagicMock()], holdings, [detail])
        self.assertEqual(result, {"available": True})
        args, _ = mock_bffd.call_args
        # 位置参数：transactions, dividends, holdings, current_prices
        self.assertEqual(args[3], {"600519": 1500.0})

    def test_approximate_path_runs_without_flows(self):
        """开关开 + 无流水：近似分支真实跑通（不 mock 下游）。

        该分支长期只被 mock 覆盖（只看「传了什么参数」），真实行为没被跑过——
        一次「开关开 + 无流水」的编排用例就因非数值市价在 ``final_value > 0``
        抛 ``TypeError``，把整份 HTML 坐连失败。本用例走真实现，锁三件事：
        返回近似契约（``approximate=True``）、成本分档能算出、不抛异常。
        """
        from src.python.core.models import Holding

        holdings = [Holding(account="A", name="长江电力", code="600900", shares=100.0, cost_price=20.0)]
        detail = MagicMock()
        detail.code = "600900"
        detail.price = 30.0

        with patch("src.python.report.excel_market_data._resolve_holdings_start_date", return_value=None):
            result = _build_flow_data(True, None, None, holdings, [detail])

        assert result is not None
        self.assertTrue(result["approximate"])
        self.assertIsInstance(result, dict)

    def test_non_numeric_price_is_filtered_not_crashing(self):
        """非数值/非正市价被过滤，不把成本流水段（及其页签）连坐。

        市价可能来自旧缓存或残缺明细，一旦是 ``None`` / 字符串 / 其它对象，
        下游乘法与比较（``final_value > 0``）就抛 ``TypeError``。
        """
        from src.python.core.models import Holding

        holdings = [Holding(account="A", name="长江电力", code="600900", shares=100.0, cost_price=20.0)]
        bad_detail = MagicMock()
        bad_detail.code = "600900"
        bad_detail.price = MagicMock()  # 非数值
        str_detail = MagicMock()
        str_detail.code = "600901"
        str_detail.price = "30.5"  # 字符串（旧缓存形态）

        with patch("src.python.report.excel_market_data._resolve_holdings_start_date", return_value=None):
            result = _build_flow_data(True, None, None, holdings, [bad_detail, str_detail])

        assert result is not None
        self.assertTrue(result["approximate"])


class TestResolveHoldingsStartDate(unittest.TestCase):
    """_resolve_holdings_start_date 建仓日期解析。"""

    def test_parses_valid_iso_date(self):
        """合法 YYYY-MM-DD → 返回 date。"""
        from datetime import date

        with patch("src.python.config.get_config", return_value={"holdings_start_date": "2024-01-15"}):
            self.assertEqual(_resolve_holdings_start_date(), date(2024, 1, 15))

    def test_empty_or_missing_returns_none(self):
        """空字符串/缺失键 → None（不计算近似年化）。"""
        with patch("src.python.config.get_config", return_value={"holdings_start_date": ""}):
            self.assertIsNone(_resolve_holdings_start_date())
        with patch("src.python.config.get_config", return_value={}):
            self.assertIsNone(_resolve_holdings_start_date())

    def test_invalid_format_returns_none(self):
        """非法日期格式 → None（仅成本分档近似，近似年化跳过）。"""
        with patch("src.python.config.get_config", return_value={"holdings_start_date": "2024/13/45"}):
            self.assertIsNone(_resolve_holdings_start_date())


class TestResolveMarketDataFlow(unittest.TestCase):
    """resolve_market_data 将 fund_flow_data 注入 data 字典（Excel 渲染数据源）。"""

    def test_fund_flow_data_injected_when_enabled(self):
        """开关开启且外部传入明细时，data 含 fund_flow_data（透传 _build_flow_data 结果）。"""
        modules = {
            "classify_holdings": MagicMock(return_value={}),
        }
        detail = MagicMock()
        detail.code = "600519"
        detail.price = 1500.0
        with patch(
            "src.python.report.excel_market_data._build_flow_data",
            return_value={"available": True, "xirr": {"rate": 0.1}},
        ) as mock_bfd:
            data = resolve_market_data(
                holdings=[MagicMock()],
                details=[detail],
                modules=modules,
                prog=MagicMock(),
                enable_cost_lots=True,
                transactions=[MagicMock()],
                dividends=[],
            )
        self.assertTrue(data["fund_flow_data"]["available"])
        self.assertEqual(data["fund_flow_data"]["xirr"]["rate"], 0.1)
        mock_bfd.assert_called_once()

    def test_fund_flow_data_none_when_disabled(self):
        """开关关闭（enable_cost_lots=False）→ data 中 fund_flow_data 为 None（保持既有输出）。"""
        modules = {
            "classify_holdings": MagicMock(return_value={}),
        }
        detail = MagicMock()
        detail.code = "600519"
        detail.price = 1500.0
        data = resolve_market_data(
            holdings=[MagicMock()],
            details=[detail],
            modules=modules,
            prog=MagicMock(),
            enable_cost_lots=False,
        )
        # 开关关闭 → 真实 _build_flow_data 直接返回 None，不触发任何成本流水计算
        self.assertIsNone(data["fund_flow_data"])
