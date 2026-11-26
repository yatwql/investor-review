"""报告模块加载器（`report/excel_module_loader`）ImportError 兜底分支覆盖。

覆盖点：任一子模块缺失时**只降级该模块**并记 add_error，其余模块照常装配；
excel_writer 缺失视为硬失败（返回空字典，后续流程不再继续）。
"""

from __future__ import annotations

import sys

import pytest

from src.python.report import excel_module_loader as loader

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _Prog:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def info(self, *_a, **_k) -> None:
        pass

    def ok(self, *_a, **_k) -> None:
        pass

    def add_error(self, msg: str, *_a, **_k) -> None:
        self.errors.append(msg)


def _load(monkeypatch, *poisoned: str) -> tuple[dict, list[str]]:
    for name in poisoned:
        monkeypatch.setitem(sys.modules, name, None)
    prog = _Prog()
    return loader.load_report_modules(prog), prog.errors


class TestLoadReportModules:
    def test_all_modules_available_no_errors(self, monkeypatch):
        modules, errors = _load(monkeypatch)

        assert errors == []
        assert modules["write_summary_sheet"] is not None
        assert modules["write_position_structure_sheet"] is not None
        assert callable(modules["compute_concentration"])

    def test_excel_writer_missing_is_fatal(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.excel_writer")

        assert modules == {}, "核心写盘模块缺失时不应装配半套依赖"
        assert any("excel_writer" in e for e in errors)

    def test_index_missing_falls_back_to_empty_fetchers(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.fetcher.index")

        assert modules["fetch_indices"]() == {}
        assert modules["fetch_us_indices"]() == {}
        assert any("fetcher" in e for e in errors)

    def test_summary_missing_sets_none(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.summary")

        assert modules["write_summary_sheet"] is None
        assert any("summary" in e for e in errors)

    def test_market_value_missing_falls_back_to_stubs(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.market_value")

        assert modules["classify_holdings"]([1]) == {}
        assert modules["get_last_trading_day"]() == ""
        assert modules["price_update_status"]([], []) == (0, 0, True)
        assert modules["_generate_details"] is None
        assert any("market_value" in e for e in errors)

    def test_holdings_detail_sheet_missing_sets_none(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.holdings_detail_sheet")

        assert modules["write_holdings_detail_sheet"] is None
        assert any("holdings_detail_sheet" in e for e in errors)

    def test_penetration_missing_falls_back_to_stub(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.penetration")

        assert modules["write_penetration_sheet"] is None
        assert modules["compute_penetration_top10"]([], {}) == {}
        assert any("penetration" in e for e in errors)

    def test_fund_performance_missing_sets_none(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.fund_performance")

        assert modules["write_fund_performance_sheet"] is None
        assert any("fund_performance" in e for e in errors)

    def test_fundamental_snapshot_missing_sets_none(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.fundamental_snapshot_sheet")

        assert modules["write_fundamental_snapshot_sheet"] is None
        assert any("fundamental_snapshot" in e for e in errors)

    def test_position_overlap_missing_falls_back_to_stub(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.position_overlap")

        assert modules["compute_overlap_matrix"]({}) == {}
        assert any("position_overlap" in e for e in errors)

    def test_position_structure_missing_sets_none(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.position_structure_sheet")

        assert modules["write_position_structure_sheet"] is None
        assert any("position_structure" in e for e in errors)

    def test_fund_concentration_missing_falls_back_to_stub(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.fund_concentration")

        assert modules["compute_concentration"]({}) == []
        assert any("fund_concentration" in e for e in errors)

    def test_style_factor_missing_falls_back_to_stub(self, monkeypatch):
        modules, errors = _load(monkeypatch, "src.python.report.fund_style_report")

        assert modules["analyze_style_for_all_funds"]({}) == {"results": []}
        assert modules["write_style_factor_sheet"] is None
        assert any("style_factor" in e for e in errors)
