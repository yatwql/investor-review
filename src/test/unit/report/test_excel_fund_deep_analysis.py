"""基金深度分析 Excel 章节辅助函数单元测试。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.report.holdings_freshness import evaluate_report_period
from src.test.helpers import recent_holdings_period

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestExcelFundDeepAnalysis:
    """基金深度分析基础函数测试。"""

    def test_process_fund_deep_analysis_module_signature(self):
        """_process_fund_deep_analysis_module 可调用并返回 (list, dict) 元组。"""
        from src.python.report.excel_fund_deep_analysis import _process_fund_deep_analysis_module

        class _MockHolding:
            def __init__(self, code: str = "000001"):
                self.code = code
                self.name = code
                self.account = "主账户"

        holdings = [_MockHolding("600519")]
        result = _process_fund_deep_analysis_module(holdings)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_period_info_carried_with_holdings(self):
        """持仓一并透出报告期判定——各消费者对时效的处置都以此为准。"""
        from src.python.report.excel_fund_deep_analysis import _process_fund_deep_analysis_module

        class _MockHolding:
            def __init__(self, code: str, name: str):
                self.code = code
                self.name = name
                self.account = "主账户"

        period = recent_holdings_period()
        with patch(
            "src.python.report.excel_fund_deep_analysis.fetch_fund_holdings_cached",
            return_value={"name": "某基金", "holdings": [{"code": "600519", "ratio": 9.0}], "date": period},
        ):
            _codes, map_ = _process_fund_deep_analysis_module([_MockHolding("110020", "沪深300指数基金")])

        assert map_["110020"]["period_info"].period == period
        assert map_["110020"]["period_info"].stale is False

    def test_split_fresh_fund_holdings_excludes_stale(self):
        """陈旧基金不入可用集合，且留下含报告期的标注文本。"""
        from src.python.report.excel_fund_deep_analysis import _split_fresh_fund_holdings

        fresh, names, stale_notes = _split_fresh_fund_holdings(
            {
                "110020": {
                    "name": "当代基金",
                    "holdings": [{"code": "600519", "ratio": 9.0}],
                    "period_info": evaluate_report_period(recent_holdings_period()),
                },
                "040046": {
                    "name": "陈年基金",
                    "holdings": [{"code": "000858", "ratio": 7.0}],
                    "period_info": evaluate_report_period("2022-12-08"),
                },
            }
        )

        assert list(fresh) == ["110020"]
        assert names == {"110020": "当代基金"}
        assert len(stale_notes) == 1
        assert "陈年基金" in stale_notes[0] and "2022-12-08" in stale_notes[0]

    def test_split_tolerates_missing_period_info(self):
        """未携带 period_info 的映射（直接构造的调用方）视为无报告期，不判陈旧。"""
        from src.python.report.excel_fund_deep_analysis import _split_fresh_fund_holdings

        fresh, _names, stale_notes = _split_fresh_fund_holdings(
            {"110020": {"name": "某基金", "holdings": [{"code": "600519", "ratio": 9.0}]}}
        )

        assert list(fresh) == ["110020"]
        assert stale_notes == []

    def test_write_fund_deep_analysis_disabled(self):
        """enable_fund_deep_analysis=False → 不写入任何内容（返回 None）。"""
        from src.python.report.excel_fund_deep_analysis import write_fund_deep_analysis_sheets

        result = write_fund_deep_analysis_sheets(
            sheets={},
            holdings=[],
            enable_fund_deep_analysis=False,
            data={},
            modules={},
            prog=type("_P", (), {"info": lambda s, m: None, "ok": lambda s, m: None, "add_error": lambda s, m: None})(),
        )
        assert result is None


class TestWriteFundDeepAnalysisDegrades:
    """数据准备返回空集时的三条降级分支（各自只影响本区块）。"""

    @staticmethod
    def _prog():
        from unittest.mock import MagicMock

        return MagicMock()

    def test_overlap_without_holdings_logs_and_skips_compute(self, caplog):
        """基金数够但持仓明细全空 → 记日志跳过计算，页签仍写入。"""
        from unittest.mock import MagicMock

        from src.python.report.excel_fund_deep_analysis import write_fund_deep_analysis_sheets

        compute_overlap = MagicMock()
        write_ps = MagicMock()
        with (
            patch(
                "src.python.report.excel_fund_deep_analysis._process_fund_deep_analysis_module",
                return_value=(["000001", "110011"], {}),
            ),
            caplog.at_level("INFO", logger="invest"),
        ):
            write_fund_deep_analysis_sheets(
                sheets={"position_structure": MagicMock()},
                holdings=[MagicMock()],
                enable_fund_deep_analysis=True,
                data={},
                modules={"compute_overlap_matrix": compute_overlap, "write_position_structure_sheet": write_ps},
                prog=self._prog(),
            )

        compute_overlap.assert_not_called()
        assert "无可用的基金持仓数据" in caplog.text
        write_ps.assert_called_once()

    def test_concentration_without_alert_rows_logs(self, caplog):
        """有基金持仓但集中度计算无告警行 → 记日志且不报完成。"""
        from unittest.mock import MagicMock

        from src.python.report.excel_fund_deep_analysis import write_fund_deep_analysis_sheets

        prog = self._prog()
        fund_map = {"110011": {"name": "易方达", "holdings": [{"code": "600519", "ratio": 9.0}]}}
        with (
            patch(
                "src.python.report.excel_fund_deep_analysis._process_fund_deep_analysis_module",
                return_value=(["110011"], fund_map),
            ),
            caplog.at_level("INFO", logger="invest"),
        ):
            write_fund_deep_analysis_sheets(
                sheets={"position_structure": MagicMock()},
                holdings=[MagicMock()],
                enable_fund_deep_analysis=True,
                data={},
                modules={
                    "compute_concentration": MagicMock(return_value={}),
                    "write_position_structure_sheet": MagicMock(),
                },
                prog=prog,
            )

        assert "持仓集中度监控：无持仓数据" in caplog.text
        # 只留页签写入的 ok，计算完成提示不得出现（
        # ``ok`` 未被 "持仓集中度计算完成" 调用）
        prog.ok.assert_called_once_with("持仓结构与集中度页签写入完成")

    def test_style_without_holdings_logs_and_skips_analysis(self, caplog):
        """无基金持仓明细 → 风格分析不计算，页签以空风格表写入。"""
        from unittest.mock import MagicMock

        from src.python.report.excel_fund_deep_analysis import write_fund_deep_analysis_sheets

        analyze_style = MagicMock()
        write_sf = MagicMock()
        with (
            patch(
                "src.python.report.excel_fund_deep_analysis._process_fund_deep_analysis_module",
                return_value=([], {}),
            ),
            caplog.at_level("INFO", logger="invest"),
        ):
            write_fund_deep_analysis_sheets(
                sheets={"style_factor": MagicMock()},
                holdings=[MagicMock()],
                enable_fund_deep_analysis=True,
                data={},
                modules={"analyze_style_for_all_funds": analyze_style, "write_style_factor_sheet": write_sf},
                prog=self._prog(),
            )

        analyze_style.assert_not_called()
        assert "风格与因子分析：无基金持仓数据" in caplog.text
        write_sf.assert_called_once()
