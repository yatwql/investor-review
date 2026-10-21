"""test_fund_performance 兄弟分片（sheet）：业绩分析页签写入器（评级/业绩/候选不可得块）。"""

from __future__ import annotations
import unittest
from typing import Any
from unittest.mock import MagicMock, patch
from src.python.core.models import Holding
from src.python.report import fund_performance as fp
from src.python.report import penetration as pene
from src.python.report.styles import BLUE_FONT, GREEN_FONT, RED_FONT
import pytest

from src.test.unit.report.test_fund_performance import (
    _MockDetailRow,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


class TestWriteFundPerformanceSheet(unittest.TestCase):
    """测试 write_fund_performance_sheet 主流程（mock API + writer）。"""

    _PATCH_TARGETS = [
        "src.python.report.fund_performance.write_title_row",
        "src.python.report.fund_performance.write_header_row",
        "src.python.report.fund_performance.write_data_row",
        "src.python.report.fund_performance.freeze_header",
        "src.python.report.fund_performance.auto_width",
        "src.python.report.fund_performance.fetch_fund_rankings_batch",
        "src.python.report.fund_performance.fetch_fund_rankings",
        "src.python.report.fund_performance.fetch_fund_benchmark",
        "src.python.report.fund_performance.classify_penetration",
    ]

    def setUp(self):
        self.ws = MagicMock()
        # ws.cell 必须通过 side_effect 返回独立 mock，否则 Python 3.13+ 中
        # _Call 不可 hash，所有 ws.cell() 返回同一对象，font 会相互覆盖
        _cell_cache: dict[tuple[int, int], MagicMock] = {}

        def _cell_side_effect(*, row: int, column: int, **kwargs) -> MagicMock:
            key = (row, column)
            if key not in _cell_cache:
                _cell_cache[key] = MagicMock()
            return _cell_cache[key]

        self.ws.cell.side_effect = _cell_side_effect

        self._patchers: dict[str, Any] = {}
        self.mocks: dict[str, Any] = {}
        for target in self._PATCH_TARGETS:
            p = patch(target)
            self._patchers[target] = p
            name = target.rsplit(".", 1)[-1]
            self.mocks[name] = p.start()

        self.mocks["write_title_row"].return_value = 2
        self.mocks["write_header_row"].return_value = 3

        # -- classify_penetration 侧效 --
        def _cls_side_effect(h: Holding) -> str:
            if h.code == "561910" or "ETF" in h.name.upper():
                return pene.ETF
            if h.code == "012325":
                return pene.BOND_FUND
            return pene.ACTIVE_EQUITY

        self.mocks["classify_penetration"].side_effect = _cls_side_effect

        # -- fetch_fund_rankings_batch 侧效 --
        _RANKINGS_DATA = {
            "561910": {
                "rankings": {
                    "近3月": {"return": 1.5},
                    "近6月": {"return": 3.2},
                    "近1年": {"return": 8.5},
                    "同类排名": {"rank": 50, "total": 500},
                },
                "rating": "优秀",
            },
            "012325": {
                "rankings": {
                    "近3月": {"return": 0.8},
                    "近6月": {"return": 1.5},
                    "近1年": {"return": 3.0},
                    "同类排名": {"rank": 100, "total": 800},
                },
                "rating": "稳定",
            },
        }

        def _rankings_batch_side_effect(codes: list[str]) -> dict:
            return {code: _RANKINGS_DATA.get(code) for code in codes}

        self.mocks["fetch_fund_rankings_batch"].side_effect = _rankings_batch_side_effect

        # -- fetch_fund_benchmark 侧效 --
        def _benchmark_side_effect(code: str) -> str:
            return {"561910": "沪深300指数", "012325": "中债综合指数"}.get(code, "--")

        self.mocks["fetch_fund_benchmark"].side_effect = _benchmark_side_effect

        # -- 公共测试数据 --
        self.holdings = [
            Holding("证券账户", "电池ETF", "561910", 1000, 1.0),
            Holding("支付宝", "招商鑫福中短债A", "012325", 500, 1.0),
            Holding("证券账户", "长江电力", "600900", 200, 50.0),
        ]
        self.details = [
            _MockDetailRow("561910", profit=1000.0, profit_rate=0.05, market_value=10000.0),
            _MockDetailRow("012325", profit=200.0, profit_rate=0.03, market_value=5000.0),
            _MockDetailRow("600900", profit=500.0, profit_rate=0.10, market_value=10000.0),
        ]

    def tearDown(self):
        for p in self._patchers.values():
            p.stop()

    # -- normal flow -------------------------------------------------

    def test_normal_flow(self):
        """正常流程：两只基金获取到业绩数据，正确写入行、标色、统计。"""
        fp.write_fund_performance_sheet(self.ws, self.holdings, self.details)

        # write_data_row 调用顺序：fund1 + fund2 + 统计行 + 评级分布 + 业绩评价标准说明
        calls = self.mocks["write_data_row"].call_args_list
        self.assertEqual(len(calls), 5)

        # --- Fund 1 (561910, 市值 10000 -> 排首位) ---
        vals0 = calls[0][0][2]
        self.assertEqual(vals0[0], "电池ETF")
        self.assertEqual(vals0[1], "561910")
        self.assertEqual(vals0[2], "场内ETF")
        self.assertEqual(vals0[3], 0.015)  # 1.5% → 小数
        self.assertEqual(vals0[4], 0.032)  # 3.2% → 小数
        self.assertEqual(vals0[5], 0.085)  # 8.5% → 小数
        self.assertEqual(vals0[6], 1000.0)  # 持仓盈亏(¥) 原始值
        self.assertEqual(vals0[7], 0.05)  # 持仓收益率 小数
        self.assertEqual(vals0[8], "沪深300指数")
        self.assertEqual(vals0[9], "优秀 持续跑赢基准，超额收益显著（基准：沪深300指数）")
        self.assertEqual(vals0[10], "50/500")

        # --- Fund 2 (012325, 市值 5000 -> 排第二) ---
        vals1 = calls[1][0][2]
        self.assertEqual(vals1[0], "招商鑫福中短债A")
        self.assertEqual(vals1[1], "012325")
        self.assertEqual(vals1[2], "场外债券基金")
        self.assertEqual(vals1[3], 0.008)  # 0.8% → 小数
        self.assertEqual(vals1[4], 0.015)  # 1.5% → 小数
        self.assertEqual(vals1[5], 0.03)  # 3.0% → 小数
        self.assertEqual(vals1[6], 200.0)  # 持仓盈亏(¥) 原始值
        self.assertEqual(vals1[7], 0.03)  # 持仓收益率 小数
        self.assertEqual(vals1[8], "中债综合指数")
        self.assertEqual(vals1[9], "稳定 收益率稳健，波动控制良好（基准：中债综合指数）")
        self.assertEqual(vals1[10], "100/800")

        # --- 统计行 ---
        vals2 = calls[2][0][2]
        self.assertEqual(vals2[0], "共 2 只基金，2 只获取到业绩数据")

        # --- 评级分布 ---
        vals3 = calls[3][0][2]
        self.assertIn("优秀: 1只", vals3[0])
        self.assertIn("稳定: 1只", vals3[0])

        # -- 单元格标色 --
        cell_3 = self.ws.cell(row=3, column=10)
        self.assertIs(cell_3.font, RED_FONT)  # 优秀 -> 红
        cell_4 = self.ws.cell(row=4, column=10)
        self.assertIs(cell_4.font, BLUE_FONT)  # 稳定 -> 蓝

        # -- 冻结 + 自动列宽 --
        self.mocks["freeze_header"].assert_called_once_with(self.ws, 2)
        self.mocks["auto_width"].assert_called_once_with(self.ws, min_width=10, max_width=30)

    # -- no funds ----------------------------------------------------

    def test_no_funds(self):
        """全部非基金持仓 -> 写入占位提示并提前返回。"""
        stocks = [
            Holding("证券账户", "长江电力", "600900", 200, 50.0),
            Holding("证券账户", "平安银行", "000001", 100, 10.0),
        ]
        fp.write_fund_performance_sheet(self.ws, stocks, [])

        self.mocks["write_title_row"].assert_called_once_with(self.ws, 1, "基金业绩分析", 11)
        self.mocks["write_header_row"].assert_called_once()

        # write_data_row 仅调用一次（占位行）
        self.mocks["write_data_row"].assert_called_once()
        args = self.mocks["write_data_row"].call_args[0]
        self.assertIn("未检测到基金持仓", args[2][0])

        # freeze + auto_width 仍被调用
        self.mocks["freeze_header"].assert_called_once_with(self.ws, 2)
        self.mocks["auto_width"].assert_called_once_with(self.ws)

        # fetch 不应被调用
        self.mocks["fetch_fund_rankings_batch"].assert_not_called()
        self.mocks["fetch_fund_benchmark"].assert_not_called()

    # -- all fail ----------------------------------------------------

    def test_all_funds_fail(self):
        """所有基金 API 获取失败 -> 全部写占位行 + 统计正确。"""
        self.mocks["fetch_fund_rankings_batch"].side_effect = lambda codes: {code: None for code in codes}

        fp.write_fund_performance_sheet(self.ws, self.holdings, self.details)

        calls = self.mocks["write_data_row"].call_args_list
        # 2 占位行 + 1 统计行 + 1 业绩评价标准说明行（perf_results 为空 -> 无评级分布）
        self.assertEqual(len(calls), 4)

        # 两只基金都是占位行
        for i in range(2):
            vals = calls[i][0][2]
            self.assertEqual(vals[3], "--")
            self.assertEqual(vals[4], "--")
            self.assertEqual(vals[5], "--")
            self.assertEqual(vals[6], "--")
            self.assertEqual(vals[7], "--")
            self.assertEqual(vals[8], "--")
            self.assertEqual(vals[9], "--")
            self.assertEqual(vals[10], "--")

        # 统计行
        summary_vals = calls[2][0][2]
        self.assertEqual(summary_vals[0], "共 2 只基金，0 只获取到业绩数据")

        # benchmark 不应被调用（continue 跳过）
        self.mocks["fetch_fund_benchmark"].assert_not_called()

        # ws.cell 不会被 _write_data_status_foot 调用
        # （首次失败未达降级阈值 → data_status 为空 → foot 提前返回）
        self.assertEqual(self.ws.cell.call_count, 0)

    # -- partial fail ------------------------------------------------

    def test_partial_fail(self):
        """部分基金获取失败 -> 成功行 + 占位行 + 统计 + 评级分布。"""
        # 只有 561910 成功
        self.mocks["fetch_fund_rankings_batch"].side_effect = lambda codes: {
            code: (
                None
                if code == "012325"
                else {
                    "561910": {
                        "rankings": {
                            "近3月": {"return": 1.5},
                            "近6月": {"return": 3.2},
                            "近1年": {"return": 8.5},
                            "同类排名": {"rank": 50, "total": 500},
                        },
                        "rating": "优秀",
                    },
                }.get(code)
            )
            for code in codes
        }

        # 额外细节：002325 的 detail 实际上不会被用到（占位行）
        fp.write_fund_performance_sheet(self.ws, self.holdings, self.details)

        calls = self.mocks["write_data_row"].call_args_list
        # 1 成功 + 1 占位 + 1 统计 + 1 评级分布 + 1 业绩评价标准说明
        self.assertEqual(len(calls), 5)

        # 成功行
        vals0 = calls[0][0][2]
        self.assertEqual(vals0[1], "561910")
        self.assertEqual(vals0[9], "优秀 持续跑赢基准，超额收益显著（基准：沪深300指数）")
        self.assertEqual(vals0[10], "50/500")

        # 占位行
        vals1 = calls[1][0][2]
        self.assertEqual(vals1[1], "012325")
        self.assertEqual(vals1[3], "--")
        self.assertEqual(vals1[9], "--")

        # 统计
        self.assertIn("1 只获取到业绩数据", calls[2][0][2][0])

        # 评级分布（只有优秀）
        self.assertIn("优秀: 1只", calls[3][0][2][0])

        # 仅成功的那只标色
        cell_3 = self.ws.cell(row=3, column=10)
        self.assertIs(cell_3.font, RED_FONT)

    # -- empty details -----------------------------------------------

    def test_empty_details(self):
        """details 为空 -> 盈亏字段按 0 处理，不报错。"""
        fp.write_fund_performance_sheet(self.ws, self.holdings, [])

        calls = self.mocks["write_data_row"].call_args_list
        self.assertEqual(len(calls), 5)  # 2 基金 + 统计 + 评级分布 + 业绩评价标准说明

        # 利润字段为 0（原始数值，Excel 数字格式处理显示）
        vals0 = calls[0][0][2]
        self.assertEqual(vals0[6], 0.0)
        self.assertEqual(vals0[7], 0.0)

        vals1 = calls[1][0][2]
        self.assertEqual(vals1[6], 0.0)
        self.assertEqual(vals1[7], 0.0)

    # -- all ratings (color test) ------------------------------------

    def test_rating_colors(self):
        """各种评级对应正确的单元格字体颜色。"""

        def _rankings_all_ratings(codes: list[str]) -> dict:
            data = {
                "561910": {
                    "rankings": {
                        "近3月": {"return": 1.0},
                        "近6月": {"return": 2.0},
                        "近1年": {"return": 3.0},
                        "同类排名": {"rank": 1, "total": 100},
                    },
                    "rating": "优秀",
                },
                "012325": {
                    "rankings": {
                        "近3月": {"return": 0.5},
                        "近6月": {"return": 1.0},
                        "近1年": {"return": 1.5},
                        "同类排名": {"rank": 50, "total": 100},
                    },
                    "rating": "稳定",
                },
            }
            return {code: data.get(code) for code in codes}

        self.mocks["fetch_fund_rankings_batch"].side_effect = _rankings_all_ratings

        # 添加第三只基金仅用于测试 "偏差" 评级
        holdings = self.holdings + [
            Holding("微信", "易方达蓝筹精选", "005827", 300, 2.0),
        ]
        details = self.details + [
            _MockDetailRow("005827", profit=-100.0, profit_rate=-0.02, market_value=3000.0),
        ]

        def _cls_side_effect_3(h: Holding) -> str:
            if h.code == "561910" or "ETF" in h.name.upper():
                return pene.ETF
            if h.code == "012325":
                return pene.BOND_FUND
            return pene.ACTIVE_EQUITY

        self.mocks["classify_penetration"].side_effect = _cls_side_effect_3

        def _rankings_3_batch(codes: list[str]) -> dict:
            data = {
                "561910": {
                    "rankings": {
                        "近3月": {"return": 1.0},
                        "近6月": {"return": 2.0},
                        "近1年": {"return": 3.0},
                        "同类排名": {"rank": 1, "total": 100},
                    },
                    "rating": "优秀",
                },
                "012325": {
                    "rankings": {
                        "近3月": {"return": 0.5},
                        "近6月": {"return": 1.0},
                        "近1年": {"return": 1.5},
                        "同类排名": {"rank": 50, "total": 100},
                    },
                    "rating": "稳定",
                },
                "005827": {
                    "rankings": {
                        "近3月": {"return": -2.0},
                        "近6月": {"return": -5.0},
                        "近1年": {"return": -8.0},
                        "同类排名": {"rank": 90, "total": 100},
                    },
                    "rating": "偏差",
                },
            }
            return {code: data.get(code) for code in codes}

        self.mocks["fetch_fund_rankings_batch"].side_effect = _rankings_3_batch

        fp.write_fund_performance_sheet(self.ws, holdings, details)

        # 排序：561910(10000) > 012325(5000) > 005827(3000)
        # row 3: 561910 -> 优秀 -> RED_FONT
        # row 4: 012325 -> 稳定 -> BLUE_FONT
        # row 5: 005827 -> 偏差 -> GREEN_FONT
        self.assertIs(self.ws.cell(row=3, column=10).font, RED_FONT)
        self.assertIs(self.ws.cell(row=4, column=10).font, BLUE_FONT)
        self.assertIs(self.ws.cell(row=5, column=10).font, GREEN_FONT)

    # -- rating distribution with diverse ratings --------------------

    def test_rating_distribution(self):
        """多基金不同评级 -> 评级分布汇总行正确。"""

        # 3 只基金，评级分别为 优秀 x2, 偏差 x1
        def _rankings_dist_batch(codes: list[str]) -> dict:
            data = {
                "561910": {
                    "rankings": {
                        "近3月": {"return": 1.0},
                        "近6月": {"return": 2.0},
                        "近1年": {"return": 3.0},
                        "同类排名": {"rank": 1, "total": 100},
                    },
                    "rating": "优秀",
                },
                "012325": {
                    "rankings": {
                        "近3月": {"return": 0.5},
                        "近6月": {"return": 1.0},
                        "近1年": {"return": 1.5},
                        "同类排名": {"rank": 50, "total": 100},
                    },
                    "rating": "优秀",
                },
                "005827": {
                    "rankings": {
                        "近3月": {"return": -2.0},
                        "近6月": {"return": -5.0},
                        "近1年": {"return": -8.0},
                        "同类排名": {"rank": 90, "total": 100},
                    },
                    "rating": "偏差",
                },
            }
            return {code: data.get(code) for code in codes}

        self.mocks["fetch_fund_rankings_batch"].side_effect = _rankings_dist_batch

        holdings = self.holdings + [
            Holding("微信", "易方达蓝筹精选", "005827", 300, 2.0),
        ]
        details = self.details + [
            _MockDetailRow("005827", profit=-100.0, profit_rate=-0.02, market_value=3000.0),
        ]

        def _cls_dist(h: Holding) -> str:
            if h.code == "561910" or "ETF" in h.name.upper():
                return pene.ETF
            if h.code == "012325":
                return pene.BOND_FUND
            return pene.ACTIVE_EQUITY

        self.mocks["classify_penetration"].side_effect = _cls_dist

        fp.write_fund_performance_sheet(self.ws, holdings, details)

        calls = self.mocks["write_data_row"].call_args_list
        # 3 基金 + 1 统计 + 1 评级分布 + 1 业绩评价标准说明 = 6
        self.assertEqual(len(calls), 6)

        rating_row = calls[4][0][2][0]
        self.assertIn("评级分布:", rating_row)
        self.assertIn("优秀: 2只", rating_row)
        self.assertIn("偏差: 1只", rating_row)

        # 评级按 _RATING_COMMENT 顺序：优秀 -> 良好 -> 稳定 -> 偏差
        # 应出现 优秀 在 偏差 之前
        self.assertLess(rating_row.index("优秀"), rating_row.index("偏差"))

    # -- perf_evaluation JSON null safety --------------------------------

    def test_perf_eval_null_categories(self):
        """perf_evaluation.categories 为 JSON null → 不崩溃，正确兜底。"""
        _data = {
            "561910": {
                "rankings": {
                    "近3月": {"return": 1.5},
                    "近6月": {"return": 3.2},
                    "近1年": {"return": 8.5},
                    "同类排名": {"rank": 50, "total": 500},
                },
                "rating": "优秀",
                "perf_evaluation": {"categories": None, "data": None},
            },
            "012325": {
                "rankings": {
                    "近3月": {"return": 0.8},
                    "近6月": {"return": 1.5},
                    "近1年": {"return": 3.0},
                    "同类排名": {"rank": 100, "total": 800},
                },
                "rating": "稳定",
                "perf_evaluation": {"categories": None, "data": None},
            },
        }
        self.mocks["fetch_fund_rankings_batch"].side_effect = lambda codes: {code: _data.get(code) for code in codes}

        fp.write_fund_performance_sheet(self.ws, self.holdings, self.details)

        calls = self.mocks["write_data_row"].call_args_list
        # 2 基金 + 统计 + 评级分布 + 业绩评价标准说明 = 5
        self.assertEqual(len(calls), 5)

        # 正常写入，评级未降级（无超额收益数据）
        vals0 = calls[0][0][2]
        self.assertEqual(vals0[9], "优秀 持续跑赢基准，超额收益显著（基准：沪深300指数）")

        vals1 = calls[1][0][2]
        self.assertEqual(vals1[9], "稳定 收益率稳健，波动控制良好（基准：中债综合指数）")

    def test_perf_eval_null_data(self):
        """perf_evaluation.data 为 JSON null，categories 正常 → 不崩溃。"""
        _data = {
            "561910": {
                "rankings": {
                    "近3月": {"return": 1.5},
                    "近6月": {"return": 3.2},
                    "近1年": {"return": 8.5},
                    "同类排名": {"rank": 50, "total": 500},
                },
                "rating": "优秀",
                "perf_evaluation": {"categories": ["超额收益", "选股能力"], "data": None},
            },
        }
        self.mocks["fetch_fund_rankings_batch"].side_effect = lambda codes: {code: _data.get(code) for code in codes}

        fp.write_fund_performance_sheet(self.ws, [self.holdings[0]], [self.details[0]])

        calls = self.mocks["write_data_row"].call_args_list
        # 1 基金 + 统计 + 评级分布 + 业绩评价标准说明 = 4
        self.assertEqual(len(calls), 4)

        # categories 正常但 data 为 None，len(scores) 应兜底为 0
        vals0 = calls[0][0][2]
        self.assertIn("基准：沪深300指数", vals0[9])


class TestWriteCandidateUnavailableBlock(unittest.TestCase):
    """_write_candidate_unavailable_block: 无有效候选时写出标题 + 占位提示。"""

    @patch("src.python.report.fund_performance.write_block_title")
    @patch("src.python.report.fund_performance._write_placeholder")
    def test_no_valid_candidate_writes_placeholder(self, mock_placeholder, mock_title):
        """available=False（无有效候选）→ 写标题 + 「未配置候选基金」占位。"""
        mock_title.return_value = 2
        mock_placeholder.return_value = 3
        ws = MagicMock()
        candidate_data = {
            "available": False,
            "reason": "no_valid_candidate",
            "exceed_limit": False,
            "invalid": [],
            "rows": [],
        }

        fp._write_candidate_unavailable_block(ws, 2, candidate_data)

        mock_title.assert_called_once_with(ws, 2, "候选基金比较（比较对象由配置指定）", 11)
        self.assertEqual(mock_placeholder.call_count, 1)
        args = mock_placeholder.call_args[0]
        self.assertIn("未配置候选基金", args[1])
        self.assertIn("comparison_candidates", args[1])

    @patch("src.python.report.fund_performance.write_block_title")
    @patch("src.python.report.fund_performance._write_placeholder")
    def test_placeholder_lists_invalid_codes(self, mock_placeholder, mock_title):
        """存在非法候选代码 → 占位文本中列出被忽略代码。"""
        mock_title.return_value = 2
        mock_placeholder.return_value = 3
        ws = MagicMock()
        candidate_data = {
            "available": False,
            "reason": "no_valid_candidate",
            "exceed_limit": False,
            "invalid": ["abc123"],
            "rows": [],
        }

        fp._write_candidate_unavailable_block(ws, 2, candidate_data)

        args = mock_placeholder.call_args[0]
        self.assertIn("abc123", args[1])
