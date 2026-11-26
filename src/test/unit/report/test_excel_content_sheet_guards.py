"""Excel 内容页签装配的守卫分支单测。

覆盖：
  - ``write_content_sheets`` 基金经理变更取数抛异常时的隔离降级（告警 + 记错误 + 区块置空，
    主表仍照常写入）；
  - ``stamp_back_to_summary`` 无汇总页签时直接返回；
  - ``write_source_catalog_block`` 目录为空时不写小节、返回原行号。

运行：
  pytest src/test/unit/report/test_excel_content_sheet_guards.py -v
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from src.python.report import data_quality_sheet, excel_content_sheets, excel_sheet_factory

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _ProgressStub:
    """ProgressReporter 桩：记录上屏文案与被记的错误，不落盘。"""

    def __init__(self) -> None:
        self.infos: list[str] = []
        self.errors: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def ok(self, message: str) -> None:
        self.infos.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)

    def call_sheet(self, *_args, **_kwargs) -> bool:
        return True


def _sheets() -> dict:
    return {
        "summary": SimpleNamespace(title="汇总"),
        "holdings_detail": SimpleNamespace(title="持仓明细"),
        "penetration": SimpleNamespace(title="穿透"),
        "fund_performance": SimpleNamespace(title="基金业绩"),
    }


class TestManagerChangeIsolation:
    """基金经理变更取数失败不阻断主表。"""

    def test_detect_raises_degrades_block(self):
        """detect_manager_changes 抛异常时记错误、manager_data 置 None，页签写入继续。"""
        prog = _ProgressStub()

        def _boom(_holdings):
            raise RuntimeError("provider down")

        result = excel_content_sheets.write_content_sheets(
            sheets=_sheets(),
            holdings=[],
            data={
                "total_mv": 0.0,
                "total_cost": 0.0,
                "total_profit": 0.0,
                "today_profit": 0.0,
                "categories": {},
                "update_status": {},
                "details": [],
            },
            a_indices={},
            us_indices={},
            modules={"detect_manager_changes": _boom},
            prog=prog,
            enable_fund_deep_analysis=True,
        )
        assert prog.errors == ["基金经理变更监控数据获取失败"]
        assert "正在分析基金经理变更..." in prog.infos
        assert result == {}


class TestStampBackWithoutSummary:
    """汇总页签缺席时回写静默跳过。"""

    def test_no_summary_sheet_returns_none(self):
        """只在存在 summary 页签时才回写标题索引，否则直接返回。"""
        assert excel_sheet_factory.stamp_back_to_summary({}) is None


class TestSourceCatalogEmpty:
    """数据源目录为空时不写小节。"""

    def test_empty_catalog_keeps_row(self):
        """catalog 为空列表时返回原行号（不占用新行、不写标题）。"""
        ws = Workbook().active
        assert data_quality_sheet.write_source_catalog_block(ws, 5, catalog=[]) == 5
