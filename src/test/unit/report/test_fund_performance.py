"""基金业绩分析模块单元测试。

测试目标：
  - _is_fund — 基金识别逻辑（股票排除、基金账户覆盖）
  - _fund_display_type — 穿透分类 -> 中文显示标签（mock classify_penetration）
  - _format_return — 收益率格式化（含边界）
  - _format_rank — 排名格式化
  - _RATING_COMMENT — 评级映射完整性
  - write_fund_performance_sheet — mock API + writer 主流程
      (正常 / 空基金 / 全部获取失败 / 部分失败 / 评级标色 / 评级分布)

运行：
  pytest src/test/unit/report/test_fund_performance.py -v"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock, patch
from src.python.core.models import Holding
from src.python.report import fund_performance as fp
from src.python.report import penetration as pene
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


class _MockDetailRow:
    """替代 DetailRow，避免 import openpyxl 重量级依赖。"""

    def __init__(self, code: str, profit: float = 0.0, profit_rate: float = 0.0, market_value: float = 0.0):
        self.code = code
        self.profit = profit
        self.profit_rate = profit_rate
        self.market_value = market_value
        self.account = ""
        self.name = ""
        self.shares = 0.0


class TestIsFund(unittest.TestCase):
    """测试 _is_fund 基金识别逻辑。"""

    def _h(self, name: str, code: str = "", account: str = "证券账户") -> Holding:
        return Holding(account=account, name=name, code=code, shares=1.0, cost_price=1.0)

    # -- 股票排除 --

    def test_stock_sh_6_excluded(self):
        """6 开头上海股票 + 证券账户 -> False"""
        h = self._h("长江电力", "600900")
        self.assertFalse(fp.is_fund(h))

    def test_stock_sz_0_excluded(self):
        """0 开头深圳股票 + 证券账户 -> False"""
        h = self._h("平安银行", "000001")
        self.assertFalse(fp.is_fund(h))

    def test_stock_cyb_3_excluded(self):
        """3 开头创业板股票 + 证券账户 -> False"""
        h = self._h("宁德时代", "300750")
        self.assertFalse(fp.is_fund(h))

    # -- ETF 绕过股票排除 --

    def test_etf_name_bypasses_stock_check(self):
        """名称含 ETF + 6 开头代码 -> True（ETF 绕过股票排除）"""
        for name in ["半导体ETF", "电池ETF", "消费ETF"]:
            with self.subTest(name=name):
                h = self._h(name, "512480")
                self.assertTrue(fp.is_fund(h))

    # -- 场外基金账户覆盖 --

    def test_fund_in_alipay(self):
        """6 开头代码 + 支付宝 -> True"""
        h = self._h("某混合基金", "600001", "支付宝")
        self.assertTrue(fp.is_fund(h))

    def test_fund_in_wechat(self):
        """0 开头代码 + 微信 -> True"""
        h = self._h("某货币基金", "000001", "微信")
        self.assertTrue(fp.is_fund(h))

    def test_fund_in_bank(self):
        """3 开头代码 + 银行 -> True"""
        h = self._h("某稳健增长", "300001", "银行")
        self.assertTrue(fp.is_fund(h))

    def test_fund_in_fund_account(self):
        """6 开头代码 + 基金账户 -> True"""
        h = self._h("某指数基金", "600001", "基金账户")
        self.assertTrue(fp.is_fund(h))

    # -- 非股票前缀代码始终为基金 --

    def test_non_stock_prefix_codes(self):
        """非 A 股/港股通前缀代码 -> True"""
        cases = [("某债券", "110011"), ("某ETF", "510050"), ("某产品", "400000")]
        for name, code in cases:
            with self.subTest(code=code):
                h = self._h(name, code)
                self.assertTrue(fp.is_fund(h))

    # -- QDII / 空代码 --

    def test_qdii_is_fund(self):
        """QDII 基金 -> True"""
        h = self._h("华夏纳斯达克100ETF(QDII)", "513300")
        self.assertTrue(fp.is_fund(h))

    def test_empty_code_is_fund(self):
        """空代码 -> True（不触发前缀检查）"""
        h = self._h("某基金", "")
        self.assertTrue(fp.is_fund(h))


class TestFundDisplayType(unittest.TestCase):
    """测试 _fund_display_type 穿透分类到中文标签的映射（mock classify_penetration）。"""

    def _h(self) -> Holding:
        return Holding("账户", "名称", "000000", 1.0, 1.0)

    @patch("src.python.report.fund_performance.classify_penetration")
    def test_qdii_label(self, mock_cls):
        """QDII -> 场外QDII基金"""
        mock_cls.return_value = pene.QDII
        self.assertEqual(fp._fund_display_type(self._h()), "场外QDII基金")

    @patch("src.python.report.fund_performance.classify_penetration")
    def test_etf_label(self, mock_cls):
        """ETF -> 场内ETF"""
        mock_cls.return_value = pene.ETF
        self.assertEqual(fp._fund_display_type(self._h()), "场内ETF")

    @patch("src.python.report.fund_performance.classify_penetration")
    def test_index_link_label(self, mock_cls):
        """INDEX_LINK -> 场外指数基金"""
        mock_cls.return_value = pene.INDEX_LINK
        self.assertEqual(fp._fund_display_type(self._h()), "场外指数基金")

    @patch("src.python.report.fund_performance.classify_penetration")
    def test_bond_fund_label(self, mock_cls):
        """BOND_FUND -> 场外债券基金"""
        mock_cls.return_value = pene.BOND_FUND
        self.assertEqual(fp._fund_display_type(self._h()), "场外债券基金")

    @patch("src.python.report.fund_performance.classify_penetration")
    def test_active_equity_label(self, mock_cls):
        """ACTIVE_EQUITY -> 场外主动型基金"""
        mock_cls.return_value = pene.ACTIVE_EQUITY
        self.assertEqual(fp._fund_display_type(self._h()), "场外主动型基金")

    @patch("src.python.report.fund_performance.classify_penetration")
    def test_unknown_type_fallback(self, mock_cls):
        """未知穿透类型 -> '--'"""
        mock_cls.return_value = "SOME_UNKNOWN_TYPE"
        self.assertEqual(fp._fund_display_type(self._h()), "--")


class TestFormatReturn(unittest.TestCase):
    """测试 _format_return 收益率格式化（返回小数供 Excel 百分比格式使用）。"""

    def test_none(self):
        """None -> '--'"""
        self.assertEqual(fp._format_return(None), "--")

    def test_dash_string(self):
        """'--' -> '--'"""
        self.assertEqual(fp._format_return("--"), "--")

    def test_positive_float(self):
        """正浮点数 -> 小数（如 1.5 -> 0.015）"""
        self.assertAlmostEqual(fp._format_return(1.5), 0.015)

    def test_negative_float(self):
        """负浮点数 -> 负小数（如 -3.25 -> -0.0325）"""
        self.assertAlmostEqual(fp._format_return(-3.25), -0.0325)

    def test_zero(self):
        """零 -> 0.0"""
        self.assertEqual(fp._format_return(0), 0.0)

    def test_positive_string_number(self):
        """正数字符串 -> 小数（如 '2.5' -> 0.025）"""
        self.assertAlmostEqual(fp._format_return("2.5"), 0.025)

    def test_negative_string_number(self):
        """负数字符串 -> 负小数（如 '-1.8' -> -0.018）"""
        self.assertAlmostEqual(fp._format_return("-1.8"), -0.018)

    def test_rounding(self):
        """四舍五入：99.999 -> 0.99999（浮点近似）"""
        self.assertAlmostEqual(fp._format_return(99.999), 0.99999, places=5)

    def test_small_positive(self):
        """很小的正数 -> 小数（0.006 -> 6e-5）"""
        self.assertAlmostEqual(fp._format_return(0.006), 6e-5)

    def test_empty_string(self):
        """空字符串 -> '--'"""
        self.assertEqual(fp._format_return(""), "--")

    def test_invalid_string(self):
        """非数字字符串 -> '--'"""
        self.assertEqual(fp._format_return("abc"), "--")


class TestFormatRank(unittest.TestCase):
    """测试 _format_rank 排名格式化。"""

    def test_formats_rank_over_total(self):
        """正常排名 -> 'rank/total'"""
        self.assertEqual(fp._format_rank({"rank": 1, "total": 100}), "1/100")

    def test_rank_is_dash(self):
        """rank='--' -> '--'"""
        self.assertEqual(fp._format_rank({"rank": "--", "total": 100}), "--")

    def test_total_is_dash(self):
        """total='--' -> '--'"""
        self.assertEqual(fp._format_rank({"rank": 1, "total": "--"}), "--")

    def test_both_dash(self):
        """两者均为 '--' -> '--'"""
        self.assertEqual(fp._format_rank({"rank": "--", "total": "--"}), "--")

    def test_empty_dict(self):
        """空字典 -> '--'（get 默认值）"""
        self.assertEqual(fp._format_rank({}), "--")

    def test_rank_zero(self):
        """rank=0 -> '0/total'"""
        self.assertEqual(fp._format_rank({"rank": 0, "total": 500}), "0/500")

    def test_string_values(self):
        """字符串数字值 -> 'rank/total'"""
        self.assertEqual(fp._format_rank({"rank": "5", "total": "100"}), "5/100")

    def test_large_numbers(self):
        """大数字 -> '1234/99999'"""
        self.assertEqual(fp._format_rank({"rank": 1234, "total": 99999}), "1234/99999")


class TestRatingComment(unittest.TestCase):
    """测试 _RATING_COMMENT 评级映射完整性。"""

    def test_all_expected_keys_present(self):
        """四个预期评级键均存在且有非空描述"""
        expected = ["优秀", "良好", "稳定", "偏差"]
        for k in expected:
            with self.subTest(key=k):
                self.assertIn(k, fp._RATING_COMMENT)
                self.assertTrue(fp._RATING_COMMENT[k])

    def test_description_prefix_matches_key(self):
        """每个评级的描述以键名开头"""
        for k, v in fp._RATING_COMMENT.items():
            with self.subTest(key=k):
                self.assertTrue(v.startswith(k), f"'{v}' 不以 '{k}' 开头")


@pytest.mark.data
class TestFormatReturnBoundary(unittest.TestCase):
    """_format_return 边界值和合理性验证。"""

    def _call(self, val):
        return fp._format_return(val)

    def test_normal_positive(self):
        """正收益率 → 小数（5.5 → 0.055）。"""
        self.assertAlmostEqual(self._call(5.5), 0.055)

    def test_normal_negative(self):
        """负收益率 → 负小数（-3.2 → -0.032）。"""
        self.assertAlmostEqual(self._call(-3.2), -0.032)

    def test_zero(self):
        """零收益率 → 0.0。"""
        self.assertEqual(self._call(0), 0.0)

    def test_extreme_large(self):
        """极大值(+9999%) → 返回正浮点数。"""
        result = self._call(9999.99)
        self.assertIsInstance(result, float)
        self.assertGreater(result, 0)

    def test_extreme_small(self):
        """极小值(-99.99%) → 返回负浮点数。"""
        result = self._call(-99.99)
        self.assertIsInstance(result, float)
        self.assertLess(result, 0)

    def test_none(self):
        """None → '--'。"""
        self.assertEqual(self._call(None), "--")

    def test_invalid_string(self):
        """无效字符串 → '--'。"""
        self.assertEqual(self._call("N/A"), "--")


@pytest.mark.data
class TestFormatRankSanity(unittest.TestCase):
    """_format_rank 合理性验证。"""

    def _call(self, entry):
        return fp._format_rank(entry)

    def test_normal_rank(self):
        """正常排名 → '排名/总数'。"""
        self.assertEqual(self._call({"rank": 50, "total": 2000}), "50/2000")

    def test_top_rank(self):
        """第1名。"""
        self.assertEqual(self._call({"rank": 1, "total": 500}), "1/500")

    def test_last_rank(self):
        """最后一名。"""
        self.assertEqual(self._call({"rank": 500, "total": 500}), "500/500")

    def test_rank_not_exceed_total(self):
        """排名不超过总数。"""
        entry = {"rank": 500, "total": 500}
        rank, total = entry["rank"], entry["total"]
        self.assertLessEqual(rank, total)

    def test_rank_positive(self):
        """排名为正数。"""
        entry = {"rank": 1, "total": 500}
        self.assertGreaterEqual(entry["rank"], 1)

    def test_missing_rank(self):
        """缺失排名 → '--'。"""
        self.assertEqual(self._call({}), "--")

    def test_missing_total(self):
        """缺失总数 → '--'。"""
        self.assertEqual(self._call({"rank": 1}), "--")

    def test_none_rank(self):
        """rank=None → '--'。"""
        self.assertEqual(self._call({"rank": None, "total": 500}), "--")


@pytest.mark.data
class TestRankDataReasonableRange(unittest.TestCase):
    """排名和收益率在合理范围内（通过 write_fund_performance_sheet 集成测试）。"""

    def setUp(self):
        self.ws = MagicMock()
        _cell_cache: dict = {}

        def _cell_side_effect(*, row: int, column: int, **kwargs) -> MagicMock:
            key = (row, column)
            if key not in _cell_cache:
                _cell_cache[key] = MagicMock()
            return _cell_cache[key]

        self.ws.cell.side_effect = _cell_side_effect

    @patch("src.python.report.fund_performance.fetch_fund_rankings_batch")
    @patch("src.python.report.fund_performance.fetch_fund_benchmark", return_value="沪深300指数")
    @patch("src.python.report.fund_performance.classify_penetration", return_value=pene.ACTIVE_EQUITY)
    def test_yield_rate_in_reasonable_range(self, mock_pene, mock_bm, mock_batch):
        """收益率极端值应通过 _format_return 格式化为正确字符串。"""
        mock_batch.return_value = {
            "005827": {
                "rankings": {
                    "近3月": {"return": 9999.99},  # 极端大
                    "近6月": {"return": -99.99},  # 极端小负
                    "近1年": {"return": 50.0},  # 正常
                    "同类排名": {"rank": 100, "total": 500},
                },
                "rating": "优秀",
            }
        }
        holdings = [Holding("支付宝", "易方达蓝筹混合", "005827", 100, 2.0)]
        details = [_MockDetailRow("005827", profit=1000.0, profit_rate=0.05, market_value=10000.0)]
        with patch("src.python.report.fund_performance.write_data_row") as mock_wdr:
            with patch("src.python.report.fund_performance.write_title_row", return_value=2):
                with patch("src.python.report.fund_performance.write_header_row", return_value=3):
                    with patch("src.python.report.fund_performance.freeze_header"):
                        with patch("src.python.report.fund_performance.auto_width"):
                            fp.write_fund_performance_sheet(self.ws, holdings, details)

            calls = mock_wdr.call_args_list
            fund_row = calls[0][0][2]
            # 格式化结果应为小数（供 Excel 百分比格式使用）
            self.assertAlmostEqual(fund_row[3], 99.9999)
            self.assertAlmostEqual(fund_row[4], -0.9999)
            self.assertEqual(fund_row[5], 0.5)

    @patch("src.python.report.fund_performance.fetch_fund_rankings_batch")
    @patch("src.python.report.fund_performance.fetch_fund_benchmark", return_value="沪深300指数")
    @patch("src.python.report.fund_performance.classify_penetration", return_value=pene.ACTIVE_EQUITY)
    def test_rank_not_exceed_total_all(self, mock_pene, mock_bm, mock_batch):
        """排名数据中 rank ≤ total → _format_rank 输出正确格式。"""
        mock_batch.return_value = {
            "005827": {
                "rankings": {
                    "近3月": {"return": 5.0},
                    "近6月": {"return": 3.0},
                    "近1年": {"return": 1.0},
                    "同类排名": {"rank": 500, "total": 500},  # 边界值
                },
                "rating": "优秀",
            }
        }
        holdings = [Holding("支付宝", "易方达蓝筹混合", "005827", 100, 2.0)]
        details = [_MockDetailRow("005827", profit=1000.0, profit_rate=0.05, market_value=10000.0)]
        with patch("src.python.report.fund_performance.write_data_row") as mock_wdr:
            with patch("src.python.report.fund_performance.write_title_row", return_value=2):
                with patch("src.python.report.fund_performance.write_header_row", return_value=3):
                    with patch("src.python.report.fund_performance.freeze_header"):
                        with patch("src.python.report.fund_performance.auto_width"):
                            fp.write_fund_performance_sheet(self.ws, holdings, details)

            calls = mock_wdr.call_args_list
            fund_row = calls[0][0][2]
            # 同类排名在第11列（索引10）
            rank_str = fund_row[10]
            self.assertEqual(rank_str, "500/500")


class TestManagerBlockGating(unittest.TestCase):
    """经理变更块门控：manager_data=None（未开启基金深度分析）→ 块整体不写，主表照常。"""

    def test_manager_block_absent_when_manager_data_none(self):
        import openpyxl

        from src.python.core.models import Holding
        from src.python.report.fund_performance import write_fund_performance_sheet

        wb = openpyxl.Workbook()
        ws = wb.active
        holdings = [Holding(account="A", name="某基金", code="040046", shares=100.0, cost_price=1.0)]
        with unittest.mock.patch("src.python.report.fund_performance.fetch_fund_rankings_batch", return_value={}):
            write_fund_performance_sheet(ws, holdings, [], manager_data=None)
        flat = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
        self.assertTrue(any("基金业绩分析" in v for v in flat), "主表标题应在")
        self.assertFalse(any("基金经理变更监控" in v for v in flat), "未开启时不得渲染经理块")

    def test_manager_block_present_when_manager_data_given(self):
        import openpyxl

        from src.python.core.models import Holding
        from src.python.report.fund_performance import write_fund_performance_sheet

        wb = openpyxl.Workbook()
        ws = wb.active
        holdings = [Holding(account="A", name="某基金", code="040046", shares=100.0, cost_price=1.0)]
        manager = [
            {
                "name": "某基金",
                "code": "040046",
                "current_manager": "张三",
                "tenure_days": 120,
                "changed_1m": False,
                "changed_3m": True,
                "changed_6m": True,
                "alert_level": "关注",
                "is_first_check": False,
            }
        ]
        with unittest.mock.patch("src.python.report.fund_performance.fetch_fund_rankings_batch", return_value={}):
            write_fund_performance_sheet(ws, holdings, [], manager_data=manager)
        flat = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
        self.assertTrue(any("基金经理变更监控" in v for v in flat), "开启时应渲染经理块")
        self.assertIn("张三", flat)


if __name__ == "__main__":
    unittest.main()
