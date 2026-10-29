"""组合历史走势计算器单元测试。

测试目标：
  - calculate_for_holding — 代码类型路由与 00 代码降级
  - _get_stock_history / _get_fund_history — 内部路由
  - _compute_annualized_volatility — 波动率计算
  - _validate_bars — 数据质量校验
  - get_combined_timeseries — 综合走势合并
  - _is_bond_fund — 债券基金名称识别
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


class TestCalculateForHolding(unittest.TestCase):
    """calculate_for_holding 路由与降级逻辑测试。"""

    def _make_calculator(self, session_cache: dict | None = None) -> Any:
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        return PortfolioHistoryCalculator(session_cache or {})

    # ── 正常路由 ──────────────────────────────────────────

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_a_share_code_routes_to_stock(self, mock_fetch):
        """6 开头 A 股 → _get_stock_history。"""
        fake_bars = [{"date": "2026-07-01", "close": 26.65}]
        mock_fetch.return_value = fake_bars

        calc = self._make_calculator()
        result = calc.calculate_for_holding("600900", "长江电力", 800)
        self.assertIsNotNone(result)
        mock_fetch.assert_called_once_with("history_stock", "600900", 30)

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_zero_prefix_code_routes_to_stock(self, mock_fetch):
        """0 开头代码且非 OTC 基金 → _get_stock_history。"""
        fake_bars = [{"date": "2026-07-01", "close": 12.50}]
        mock_fetch.return_value = fake_bars

        calc = self._make_calculator()
        result = calc.calculate_for_holding("000001", "平安银行", 500)
        self.assertIsNotNone(result)
        mock_fetch.assert_called_once_with("history_stock", "000001", 30)

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_five_prefix_etf_routes_to_stock(self, mock_fetch):
        """5 开头 ETF → _get_stock_history。"""
        fake_bars = [{"date": "2026-07-01", "close": 1.234}]
        mock_fetch.return_value = fake_bars

        calc = self._make_calculator()
        result = calc.calculate_for_holding("511880", "银华日利", 100)
        self.assertIsNotNone(result)
        mock_fetch.assert_called_once_with("history_stock", "511880", 30)

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_six_digit_code_routes_to_fund(self, mock_fetch):
        """6 位纯数字非 A 股/ETF → _get_fund_history。"""
        fake_bars = [{"date": "2026-07-01", "nav": 1.5}]
        mock_fetch.return_value = fake_bars

        calc = self._make_calculator()
        result = calc.calculate_for_holding("011506", "某基金", 1000)
        self.assertIsNotNone(result)
        mock_fetch.assert_called_once_with("history_fund_otc", "011506", 30)

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_bond_fund_routes_to_fund(self, mock_fetch):
        """债券基金名称 → _get_fund_history。"""
        fake_bars = [{"date": "2026-07-01", "nav": 1.02}]
        mock_fetch.return_value = fake_bars

        calc = self._make_calculator()
        result = calc.calculate_for_holding("012325", "招商鑫福中短债A", 5000)
        self.assertIsNotNone(result)
        mock_fetch.assert_called_once_with("history_fund_otc", "012325", 30)

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_otc_fund_name_routes_directly_to_fund(self, mock_fetch):
        """002943 名称可识别为场外基金 → 直接走基金净值，不误取同代码股票 K 线。

        回归：先前 00 前缀优先判 A 股，只要股票 K 线有数据就不降级，
        以致取到同代码深市股票（宇晶股份）的历史而非基金净值。
        """
        fake_bars = [{"date": "2026-07-01", "nav": 4.77}]
        mock_fetch.return_value = fake_bars

        calc = self._make_calculator()
        result = calc.calculate_for_holding("002943", "广发多因子灵活配置混合", 2000)
        self.assertIsNotNone(result)
        mock_fetch.assert_called_once_with("history_fund_otc", "002943", 30)

    def test_hk_stock_returns_none(self):
        """港股通代码 → None。"""
        calc = self._make_calculator()
        result = calc.calculate_for_holding("00700", "腾讯控股", 100)
        self.assertIsNone(result)

    def test_unknown_type_returns_none(self):
        """未知类型代码 → None。"""
        calc = self._make_calculator()
        result = calc.calculate_for_holding("ABCDE", "未知资产", 100)
        self.assertIsNone(result)

    # ── 00 代码降级 ────────────────────────────────────────

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_code_fallback_to_fund(self, mock_fetch):
        """00 代码 K 线全空 → 降级至基金净值。"""
        mock_fetch.side_effect = [
            None,  # history_stock → 失败
            [{"date": "2026-07-01", "nav": 1.2345}],  # history_fund_otc → 成功
        ]

        calc = self._make_calculator()
        result = calc.calculate_for_holding("002943", "广发多因子", 1000)
        self.assertIsNotNone(result)
        self.assertEqual(mock_fetch.call_count, 2)
        # 第 1 次调用必须是 history_stock
        self.assertEqual(mock_fetch.call_args_list[0][0][0], "history_stock")
        # 第 2 次调用必须是 history_fund_otc（降级）
        self.assertEqual(mock_fetch.call_args_list[1][0][0], "history_fund_otc")

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_kline_success_no_fallback(self, mock_fetch):
        """00 代码但 K 线成功 → 不降级。"""
        mock_fetch.return_value = [{"date": "2026-07-01", "close": 12.50}]

        calc = self._make_calculator()
        result = calc.calculate_for_holding("000001", "平安银行", 500)
        self.assertIsNotNone(result)
        mock_fetch.assert_called_once_with("history_stock", "000001", 30)

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_code_fallback_all_fail(self, mock_fetch):
        """00 代码 K 线 + 基金净值均失败 → None。"""
        mock_fetch.side_effect = [None, None]

        calc = self._make_calculator()
        result = calc.calculate_for_holding("002943", "广发多因子", 1000)
        self.assertIsNone(result)
        self.assertEqual(mock_fetch.call_count, 2)

    # ── Session Cache ────────────────────────────────────

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_session_cache_stock(self, mock_fetch):
        """_get_stock_history 复用会话缓存。"""
        calc = self._make_calculator(
            {
                "history_stock_600900": [{"date": "2026-07-01", "close": 26.65}],
            }
        )
        result = calc.calculate_for_holding("600900", "长江电力", 800)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["close"], 26.65)
        mock_fetch.assert_not_called()

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_session_cache_fund(self, mock_fetch):
        """_get_fund_history 复用会话缓存（00 代码触发降级路径）。"""
        mock_fetch.return_value = None  # stock 路径也 mock 掉
        calc = self._make_calculator(
            {
                "history_fund_otc_002943": [{"date": "2026-07-01", "nav": 1.2345}],
            }
        )
        result = calc.calculate_for_holding("002943", "广发多因子", 1000)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]["close"], 1.2345)

    # ── as-if 市值计算 ─────────────────────────────────

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_as_if_market_value(self, mock_fetch):
        """as-if 市值 = close × shares。"""
        mock_fetch.return_value = [
            {"date": "2026-07-01", "close": 10.0},
            {"date": "2026-07-02", "close": 11.0},
        ]

        calc = self._make_calculator()
        result = calc.calculate_for_holding("600900", "长江电力", 800)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["value"], 8000.0)  # 10.0 × 800
        self.assertEqual(result[1]["value"], 8800.0)  # 11.0 × 800

    @patch("src.python.report.portfolio_history.fetch_with_incremental_fallback")
    def test_as_if_skips_zero_close(self, mock_fetch):
        """close <= 0 的 bar 跳过。"""
        mock_fetch.return_value = [
            {"date": "2026-07-01", "close": 0.0},
            {"date": "2026-07-02", "close": 10.0},
        ]

        calc = self._make_calculator()
        result = calc.calculate_for_holding("600900", "长江电力", 800)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["value"], 8000.0)


class TestGetCombinedTimeseries(unittest.TestCase):
    """get_combined_timeseries 综合走势测试。"""

    def _make_calculator(self):
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        return PortfolioHistoryCalculator({})

    def _bars(self, close_values: list[float], shares: float = 1, start: str = "2026-07-01") -> list[dict]:
        """生成 calculate_for_holding 的返回格式（含 value）。"""
        return [
            {"date": f"2026-07-{1 + i:02d}", "close": v, "value": round(v * shares, 2)}
            for i, v in enumerate(close_values)
        ]

    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_all_success_status_ok(self, mock_calc):
        """全部成功 → status=ok。"""
        mock_calc.side_effect = [
            self._bars([10, 11, 12]),  # 持仓 1
            self._bars([20, 21, 22]),  # 持仓 2
        ]
        calc = self._make_calculator()
        result = calc.get_combined_timeseries(
            [
                ("600900", "长江电力", 100),
                ("002943", "广发多因子", 200),
            ],
            days=3,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["bars"]), 3)

    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_partial_fail_status_degraded(self, mock_calc):
        """部分失败 → status=degraded。"""
        mock_calc.side_effect = [
            self._bars([10, 11, 12]),  # 成功
            None,  # 失败
        ]
        calc = self._make_calculator()
        result = calc.get_combined_timeseries(
            [
                ("600900", "长江电力", 100),
                ("002943", "广发多因子", 200),
            ],
            days=3,
        )
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(any("部分持仓" in w for w in result["warnings"]))

    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_all_fail_status_unavailable(self, mock_calc):
        """全部失败 → status=unavailable。"""
        mock_calc.side_effect = [None, None]
        calc = self._make_calculator()
        result = calc.get_combined_timeseries(
            [
                ("600900", "长江电力", 100),
                ("002943", "广发多因子", 200),
            ]
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(len(result["bars"]), 0)

    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_days_passthrough_to_holdings(self, mock_calc):
        """days 透传：get_combined_timeseries 指定 days → calculate_for_holding 收到相同 days。"""
        mock_calc.side_effect = [
            self._bars([10, 11, 12]),
            self._bars([20, 21, 22]),
        ]
        calc = self._make_calculator()
        result = calc.get_combined_timeseries(
            [
                ("600900", "长江电力", 100),
                ("002943", "广发多因子", 200),
            ],
            days=365,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(mock_calc.call_count, 2)
        self.assertEqual(mock_calc.call_args_list[0].args, ("600900", "长江电力", 100, 365))
        self.assertEqual(mock_calc.call_args_list[1].args, ("002943", "广发多因子", 200, 365))

    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_days_default_30(self, mock_calc):
        """days 缺省 → calculate_for_holding 收到默认 30。"""
        mock_calc.side_effect = [self._bars([10, 11, 12])]
        calc = self._make_calculator()
        result = calc.get_combined_timeseries([("600900", "长江电力", 100)])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(mock_calc.call_args_list[0].args, ("600900", "长江电力", 100, 30))

    # ── Benchmark integration ──────────────────────────────

    @patch("src.python.report.portfolio_history.normalize_benchmarks")
    @patch("src.python.report.portfolio_history.fetch_benchmarks")
    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_benchmark_indices_provided_calls_fetch(self, mock_calc, mock_fetch, mock_norm):
        """传入 benchmark_indices → 调用 fetch_benchmarks + normalize_benchmarks。"""
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        mock_calc.side_effect = [self._bars([10, 11, 12])]
        mock_fetch.return_value = {"sh000300": {"name": "沪深300", "bars": []}}
        mock_norm.return_value = [
            {
                "code": "sh000300",
                "name": "沪深300",
                "bars": [],
                "total_return_pct": 2.0,
                "max_drawdown_pct": -1.0,
                "data_start": "",
                "data_end": "",
                "status": "ok",
            }
        ]

        calc = PortfolioHistoryCalculator(
            {},
            benchmark_indices={"sh000300": "沪深300"},
        )
        result = calc.get_combined_timeseries([("600900", "长江电力", 100)], days=30)
        mock_fetch.assert_called_once_with({"sh000300": "沪深300"}, days=30)
        mock_norm.assert_called_once()
        self.assertIn("benchmarks", result)
        self.assertEqual(len(result["benchmarks"]), 1)
        self.assertEqual(result["benchmarks"][0]["code"], "sh000300")

    @patch("src.python.report.portfolio_history.normalize_benchmarks")
    @patch("src.python.report.portfolio_history.fetch_benchmarks")
    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_benchmark_indices_empty_skips_fetch(self, mock_calc, mock_fetch, mock_norm):
        """benchmark_indices 为空字典 → 不调用 fetch_benchmarks。"""
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        mock_calc.side_effect = [self._bars([10, 11, 12])]

        calc = PortfolioHistoryCalculator(
            {},
            benchmark_indices={},
        )
        result = calc.get_combined_timeseries([("600900", "长江电力", 100)], days=30)
        mock_fetch.assert_not_called()
        mock_norm.assert_not_called()
        self.assertEqual(result["benchmarks"], [])

    @patch("src.python.report.portfolio_history.normalize_benchmarks")
    @patch("src.python.report.portfolio_history.fetch_benchmarks")
    @patch("src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding")
    def test_benchmark_fetch_exception_handled(self, mock_calc, mock_fetch, mock_norm):
        """fetch_benchmarks 抛出异常 → 不阻塞，返回空列表。"""
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        mock_calc.side_effect = [self._bars([10, 11, 12])]
        mock_fetch.side_effect = RuntimeError("网络错误")

        calc = PortfolioHistoryCalculator(
            {},
            benchmark_indices={"sh000300": "沪深300"},
        )
        result = calc.get_combined_timeseries([("600900", "长江电力", 100)], days=30)
        mock_fetch.assert_called_once()
        mock_norm.assert_not_called()
        self.assertEqual(result["benchmarks"], [])
        self.assertEqual(result["status"], "ok")  # 基准异常不影响组合走势


class TestTerminalStaleness(unittest.TestCase):
    """走势终点口径校验：LOCF 造成的滞后终值必须显式提示。"""

    _DATES = ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-06"]

    def _make_calculator(self):
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        return PortfolioHistoryCalculator({})

    @staticmethod
    def _series(values: list[float], dates: list[str]) -> list[dict]:
        return [{"date": d, "close": 1.0, "value": v} for d, v in zip(dates, values, strict=True)]

    def _run(self, series_by_code: dict[str, list[dict]]) -> dict:
        holdings = [
            ("600900", "长江电力", 100.0),
            ("601398", "工商银行", 100.0),
            ("022365", "永赢科技智选混合C", 100.0),
        ]
        # 按 code 分发而非按列表顺序：并行取数下 side_effect 的消耗顺序不确定
        with patch(
            "src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding",
            side_effect=lambda code, *_args, **_kwargs: series_by_code[code],
        ):
            return self._make_calculator().get_combined_timeseries(holdings, days=4)

    def test_lag_two_trading_days_warns(self):
        """某标的净值停在 2 个交易日前 → 告警 + 契约字段带上滞后明细。"""
        result = self._run(
            {
                "600900": self._series([100.0] * 4, self._DATES),
                "601398": self._series([200.0] * 3, self._DATES[:3]),  # 落后 1 个交易日（T-1 常态）
                "022365": self._series([300.0] * 2, self._DATES[:2]),  # 落后 2 个交易日 → 告警
            }
        )

        self.assertTrue(any("净值滞后" in w for w in result["warnings"]))
        staleness = result["terminal_staleness"]
        self.assertIsNotNone(staleness)
        self.assertEqual(staleness["max_lag_trading_days"], 2)
        self.assertEqual([a["label"] for a in staleness["assets"]], ["永赢科技智选混合C(022365)"])
        # 终值 600 = 100 + 200 + 300，滞后标的 300 → 50%
        self.assertAlmostEqual(staleness["assets"][0]["weight_pct"], 50.0, places=2)

    def test_t_minus_one_lag_not_warned(self):
        """仅落后 1 个交易日（QDII/场外基金常态）→ 不告警。"""
        result = self._run(
            {
                "600900": self._series([100.0] * 4, self._DATES),
                "601398": self._series([200.0] * 3, self._DATES[:3]),
                "022365": self._series([300.0] * 3, self._DATES[:3]),
            }
        )

        self.assertFalse(any("净值滞后" in w for w in result["warnings"]))
        self.assertIsNone(result["terminal_staleness"])

    def test_same_last_date_no_staleness(self):
        """全部标的终点同日 → 无滞后（不产生噪声告警）。"""
        result = self._run(
            {
                "600900": self._series([100.0] * 4, self._DATES),
                "601398": self._series([200.0] * 4, self._DATES),
                "022365": self._series([300.0] * 4, self._DATES),
            }
        )

        self.assertFalse(any("净值滞后" in w for w in result["warnings"]))
        self.assertIsNone(result["terminal_staleness"])


class TestLatestQuoteBackfill(unittest.TestCase):
    """历史末条落后最新行情时，按最新估值回填终点（as-if 口径不变）。"""

    _DATES = ["2026-07-01", "2026-07-02", "2026-07-03"]
    _HOLDINGS = [("600900", "长江电力", 100.0), ("601398", "工商银行", 100.0), ("022365", "永赢科技智选混合C", 100.0)]

    @staticmethod
    def _series(values: list[float], dates: list[str]) -> list[dict]:
        return [{"date": d, "close": 1.0, "value": v} for d, v in zip(dates, values, strict=True)]

    def _run(self, series_by_code: dict[str, list[dict]], **kwargs) -> dict:
        with patch(
            "src.python.report.portfolio_history.PortfolioHistoryCalculator.calculate_for_holding",
            side_effect=lambda code, *_args, **_kwargs: series_by_code[code],
        ):
            from src.python.report.portfolio_history import PortfolioHistoryCalculator

            return PortfolioHistoryCalculator({}).get_combined_timeseries(self._HOLDINGS, days=3, **kwargs)

    def test_quote_fills_terminal_bar(self):
        """滞后 1 个交易日的标的按最新价补齐 → 终值含最新估值、且不再报滞后。"""
        lagging = self._series([300.0, 300.0], self._DATES[:2])
        result = self._run(
            {
                "600900": self._series([100.0] * 3, self._DATES),
                "601398": self._series([200.0] * 3, self._DATES),
                "022365": lagging,
            },
            latest_quotes={"022365": (3.5, self._DATES[2])},
        )

        # 回填值 = 3.5 × 100 份 = 350（original 300 停在 07-02）
        self.assertAlmostEqual(result["bars"][-1]["total_value"], 100.0 + 200.0 + 350.0, places=2)
        self.assertIsNone(result["terminal_staleness"])
        self.assertFalse(any("净值滞后" in w for w in result["warnings"]))
        # 会话缓存里的原序列不被就地修改（回填走副本）
        self.assertEqual(len(lagging), 2)

    def test_quote_not_newer_skips_backfill(self):
        """行情日不晚于历史末条 → 不回填（不重复追加同日 bar）。"""
        result = self._run(
            {
                "600900": self._series([100.0] * 3, self._DATES),
                "601398": self._series([200.0] * 3, self._DATES),
                "022365": self._series([300.0] * 3, self._DATES),
            },
            latest_quotes={"022365": (3.5, self._DATES[2])},
        )

        self.assertEqual(result["bars"][-1]["date"], self._DATES[2])
        self.assertAlmostEqual(result["bars"][-1]["total_value"], 600.0, places=2)

    def test_long_window_suppresses_duplicate_warning(self):
        """长窗（同一次运行的第二次全量计算）不打 WARNING，但契约字段照常给出。"""
        with self.assertNoLogs("invest", level="WARNING"):
            result = self._run(
                {
                    "600900": self._series([100.0] * 3, self._DATES),
                    "601398": self._series([200.0] * 3, self._DATES),
                    "022365": self._series([300.0] * 1, self._DATES[:1]),
                },
                warn_on_terminal_staleness=False,
            )

        self.assertIsNotNone(result["terminal_staleness"])
        self.assertEqual(result["terminal_staleness"]["max_lag_trading_days"], 2)


class TestComputeAnnualizedVolatility(unittest.TestCase):
    """年化波动率计算测试。"""

    def _call(self, daily_returns: list[float]) -> float:
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        return PortfolioHistoryCalculator._compute_annualized_volatility(daily_returns)

    def test_annualized_volatility_normal_returns_positive(self):
        """正常收益率序列 → 正波动率。"""
        result = self._call([0.01, -0.005, 0.02, -0.01, 0.015])
        self.assertGreater(result, 0)

    def test_annualized_volatility_single_return_zero(self):
        """单元素 → 0。"""
        self.assertEqual(self._call([0.01]), 0.0)

    def test_annualized_volatility_empty_list_zero(self):
        """空列表 → 0。"""
        self.assertEqual(self._call([]), 0.0)

    def test_annualized_volatility_identical_returns_zero(self):
        """全部相同（无波动）→ 0。"""
        self.assertEqual(self._call([0.01, 0.01, 0.01]), 0.0)


class TestValidateBars(unittest.TestCase):
    """走势数据质量校验测试。"""

    def _call(self, bars: list[dict]) -> list[str]:
        from src.python.report.portfolio_history import _validate_bars

        return _validate_bars(bars)

    def test_clean_bars_no_warnings(self):
        """正常数据 → 无警告。"""
        warnings = self._call(
            [
                {"date": "2026-07-01", "close": 10.0},
                {"date": "2026-07-02", "close": 11.0},
            ]
        )
        self.assertEqual(warnings, [])

    def test_zero_close_warning(self):
        """收盘价为 0 → 警告。"""
        warnings = self._call(
            [
                {"date": "2026-07-01", "close": 0.0},
            ]
        )
        self.assertTrue(any("收盘价为 0" in w for w in warnings))
