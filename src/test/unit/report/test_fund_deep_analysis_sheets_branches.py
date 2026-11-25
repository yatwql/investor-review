"""基金深度分析页签写入（`report/excel_fund_deep_analysis.write_fund_deep_analysis_sheets`）分支覆盖。

覆盖点：
  - 页签/模块缺失时各区块整体跳过（不得写半个页签）
  - 持仓重合度：基金数 < 2 跳过、有效持仓 ≥ 2 计算并注入市值权重、全部陈旧时跳过、
    数据获取异常转 add_error
  - 持仓集中度：无基金持仓、算得空结果、计算异常
  - 页签写入自身异常转 add_error（不打断后续章节）
  - 风格与因子：结果为空、计算异常、FACTOR_NAMES 导入失败降级为 None、
    style_factor_data 缺失时 factor_names 保持 None
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from src.python.report import excel_fund_deep_analysis as fda
from src.test.helpers import recent_holdings_period

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _Prog:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.oks: list[str] = []

    def info(self, *_a, **_k) -> None:
        pass

    def ok(self, msg: str, *_a, **_k) -> None:
        self.oks.append(msg)

    def warn(self, *_a, **_k) -> None:
        pass

    def add_error(self, msg: str, *_a, **_k) -> None:
        self.errors.append(msg)


def _holdings_are_funds(monkeypatch) -> None:
    monkeypatch.setattr(fda, "is_fund", lambda _h: True)


def _holdings_not_funds(monkeypatch) -> None:
    monkeypatch.setattr(fda, "is_fund", lambda _h: False)


def _fake_holdings(*codes: str) -> list[SimpleNamespace]:
    return [SimpleNamespace(code=code, name=f"基金{code}", shares=1.0) for code in codes]


def _fund_data(codes: dict[str, str]) -> dict[str, dict]:
    return {
        code: {"name": f"基金{code}", "holdings": [{"code": "600519", "ratio": 8.0}], "date": period}
        for code, period in codes.items()
    }


_RECENT = None  # 运行期填充，避免模块级依赖测试上下文


def _recent() -> str:
    return _RECENT or recent_holdings_period()


class TestPositionStructureBlocks:
    def test_sheet_or_writer_missing_skips_whole_block(self, monkeypatch):
        _holdings_are_funds(monkeypatch)
        calls: list[str] = []

        def _overlap(_fresh, fund_mv_map=None) -> dict:
            calls.append("overlap")
            return {}

        prog = _Prog()
        fda.write_fund_deep_analysis_sheets(
            sheets={},
            holdings=_fake_holdings("110020", "040046"),
            enable_fund_deep_analysis=True,
            data={},
            modules={
                "compute_overlap_matrix": _overlap,
                "write_position_structure_sheet": lambda *a, **k: calls.append("write"),
            },
            prog=prog,
        )

        assert calls == []
        assert prog.oks == [] and prog.errors == []

    def test_single_fund_skips_overlap_but_still_writes_sheet(self, monkeypatch):
        _holdings_are_funds(monkeypatch)
        monkeypatch.setattr(fda, "fetch_fund_holdings_cached", lambda code: _fund_data({code: _recent()}).get(code))
        calls: list[str] = []

        def _overlap(_fresh, fund_mv_map=None) -> dict:
            calls.append("overlap")
            return {}

        def _write(*_a, **_k) -> None:
            calls.append("write")

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("110020"),
            enable_fund_deep_analysis=True,
            data={},
            modules={"compute_overlap_matrix": _overlap, "write_position_structure_sheet": _write},
            prog=_Prog(),
        )

        assert calls == ["write"], "基金数 < 2 时不得调用重合度计算，但页签仍需写入（区块显示空态）"

    def test_overlap_uses_market_value_weights(self, monkeypatch):
        _holdings_are_funds(monkeypatch)
        monkeypatch.setattr(fda, "fetch_fund_holdings_cached", lambda code: _fund_data({code: _recent()}).get(code))
        seen: dict[str, object] = {}

        def _overlap(fresh, fund_mv_map=None) -> dict:
            seen["fresh"] = sorted(fresh)
            seen["mv"] = fund_mv_map
            return {"matrix": []}

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("110020", "040046"),
            enable_fund_deep_analysis=True,
            data={
                "details": [
                    SimpleNamespace(code="110020", market_value=100.0),
                    SimpleNamespace(code="040046", market_value=50.0),
                    SimpleNamespace(code="600519", market_value=9.0),
                ]
            },
            modules={"compute_overlap_matrix": _overlap, "write_position_structure_sheet": lambda *a, **k: None},
            prog=_Prog(),
        )

        assert seen["fresh"] == ["040046", "110020"]
        assert seen["mv"] == {"110020": 100.0, "040046": 50.0}, "非基金明细不得进入市值权重表"

    def test_all_funds_stale_skips_overlap_and_labels_notes(self, monkeypatch):
        _holdings_are_funds(monkeypatch)
        monkeypatch.setattr(fda, "fetch_fund_holdings_cached", lambda code: _fund_data({code: "2020-03-31"}).get(code))
        calls: list[str] = []
        captured: dict[str, object] = {}

        def _write(_ws, overlap_result, **kwargs) -> None:
            captured.update(kwargs)
            captured["overlap_result"] = overlap_result

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("110020", "040046"),
            enable_fund_deep_analysis=True,
            data={},
            modules={
                "compute_overlap_matrix": lambda *a, **k: calls.append("overlap") or {},
                "write_position_structure_sheet": _write,
            },
            prog=_Prog(),
        )

        assert calls == [], "全部基金陈旧时不得计算重合度矩阵"
        assert len(captured["stale_fund_notes"]) == 2
        assert captured["overlap_result"] is None

    def test_overlap_exception_reports_error_and_still_writes(self, monkeypatch):
        monkeypatch.setattr(
            fda, "_process_fund_deep_analysis_module", lambda _h: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        calls: list[str] = []
        prog = _Prog()

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("110020", "040046"),
            enable_fund_deep_analysis=True,
            data={},
            modules={
                "compute_overlap_matrix": lambda *a, **k: {},
                "write_position_structure_sheet": lambda *a, **k: calls.append("write"),
            },
            prog=prog,
        )

        assert prog.errors == ["持仓重合度矩阵数据获取失败"]
        assert calls == ["write"]

    def test_concentration_ok_and_empty(self, monkeypatch):
        _holdings_are_funds(monkeypatch)
        monkeypatch.setattr(fda, "fetch_fund_holdings_cached", lambda code: _fund_data({code: _recent()}).get(code))
        captured: dict[str, object] = {}
        prog = _Prog()

        def _write(_ws, _overlap, **kwargs) -> None:
            captured.update(kwargs)

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("110020"),
            enable_fund_deep_analysis=True,
            data={},
            modules={
                "compute_concentration": lambda _fh: {"top1": 0.5},
                "write_position_structure_sheet": _write,
            },
            prog=prog,
        )

        assert captured["concentration_data"] == {"top1": 0.5}
        assert "持仓集中度计算完成" in prog.oks

    def test_concentration_without_fund_holdings_passes_none(self, monkeypatch):
        _holdings_not_funds(monkeypatch)
        captured: dict[str, object] = {}

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("600519"),
            enable_fund_deep_analysis=True,
            data={},
            modules={
                "compute_concentration": lambda _fh: {"top1": 0.5},
                "write_position_structure_sheet": lambda _ws, _o, **k: captured.update(k),
            },
            prog=_Prog(),
        )

        assert captured["concentration_data"] is None

    def test_concentration_exception_reports_error(self, monkeypatch):
        _holdings_are_funds(monkeypatch)
        monkeypatch.setattr(fda, "fetch_fund_holdings_cached", lambda code: _fund_data({code: _recent()}).get(code))
        prog = _Prog()

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("110020"),
            enable_fund_deep_analysis=True,
            data={},
            modules={
                "compute_concentration": lambda _fh: (_ for _ in ()).throw(RuntimeError("boom")),
                "write_position_structure_sheet": lambda *a, **k: None,
            },
            prog=prog,
        )

        assert prog.errors == ["持仓集中度数据获取失败"]

    def test_sheet_writer_exception_reports_error(self, monkeypatch):
        _holdings_not_funds(monkeypatch)
        prog = _Prog()

        fda.write_fund_deep_analysis_sheets(
            sheets={"position_structure": object()},
            holdings=_fake_holdings("600519"),
            enable_fund_deep_analysis=True,
            data={},
            modules={"write_position_structure_sheet": lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))},
            prog=prog,
        )

        assert prog.errors == ["持仓结构与集中度页签写入失败"]


class TestStyleFactorBlock:
    def _write(self, monkeypatch, *, analyze, style_factor_data=None, factor_catalog_data=None):
        monkeypatch.setattr(
            fda, "_process_fund_deep_analysis_module", lambda _h: (["110020"], {"110020": {"holdings": []}})
        )
        captured: dict[str, object] = {}

        def _write_sf(_ws, **kwargs) -> None:
            captured.update(kwargs)

        prog = _Prog()
        fda.write_fund_deep_analysis_sheets(
            sheets={"style_factor": object()},
            holdings=_fake_holdings("110020"),
            enable_fund_deep_analysis=True,
            data={},
            modules={"analyze_style_for_all_funds": analyze, "write_style_factor_sheet": _write_sf},
            prog=prog,
            style_factor_data=style_factor_data,
            factor_catalog_data=factor_catalog_data,
        )
        return captured, prog

    def test_style_results_passed_through(self, monkeypatch):
        captured, prog = self._write(monkeypatch, analyze=lambda _fh: {"results": [{"code": "110020"}]})

        assert captured["style_data"] == [{"code": "110020"}]
        assert "风格与因子分析计算完成" in prog.oks

    def test_empty_style_results_written_as_empty_list(self, monkeypatch):
        captured, prog = self._write(monkeypatch, analyze=lambda _fh: {})

        assert captured["style_data"] == []
        assert "风格与因子分析计算完成" not in prog.oks

    def test_style_exception_reports_error(self, monkeypatch):
        _captured, prog = self._write(monkeypatch, analyze=lambda _fh: (_ for _ in ()).throw(RuntimeError("boom")))

        assert prog.errors == ["风格与因子分析数据获取失败"]

    def test_factor_names_derived_only_when_style_data_present(self, monkeypatch):
        captured_noop, _ = self._write(monkeypatch, analyze=lambda _fh: {})
        assert captured_noop["factor_names"] is None

        captured, _ = self._write(
            monkeypatch, analyze=lambda _fh: {}, style_factor_data={"available": True, "industry_beta": {"betas": {}}}
        )
        assert captured["factor_names"], "存在风格因子数据时必须透出因子中文名表"
        assert captured["industry_beta"] == {"betas": {}}

    def test_factor_names_import_failure_degrades_to_none(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "src.python.analysis.style_factor_regression", None)
        captured, _ = self._write(monkeypatch, analyze=lambda _fh: {}, style_factor_data={"available": True})

        assert captured["factor_names"] is None

    def test_writer_exception_reports_error(self, monkeypatch):
        monkeypatch.setattr(fda, "_process_fund_deep_analysis_module", lambda _h: (["110020"], {}))
        prog = _Prog()

        fda.write_fund_deep_analysis_sheets(
            sheets={"style_factor": object()},
            holdings=_fake_holdings("110020"),
            enable_fund_deep_analysis=True,
            data={},
            modules={"write_style_factor_sheet": lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))},
            prog=prog,
        )

        assert prog.errors == ["风格与因子分析页签写入失败"]
