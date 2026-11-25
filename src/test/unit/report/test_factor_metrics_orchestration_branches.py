"""风格因子 / 行业 Beta 编排（`report/_report_factor_metrics.py`）降级分支覆盖。

覆盖点（§1.4.5 双层降级口径）：
  - 功能开关关闭 → 返回 None（章节隐藏），而非降级占位
  - 纯计算层依赖缺失（ImportError）→ status=source_failed + warn
  - 组合收益为空 → insufficient；因子/指数全部拉取为空 → source_failed
  - 有效因子不足 MIN_FACTORS → insufficient 且 stale_factors 含空拉取与停更因子
  - 计算成功但 available=False → warn；计算抛异常 → source_failed（不冒泡）
  - 行业 Beta：映射行业为空时不发指数请求、无映射行业透出、IndexError 不冒泡
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import cast

import pytest

from src.python.analysis import industry_beta as ib
from src.python.analysis import style_factor_regression as sfr
from src.python.report import _report_factor_metrics as rfm
from src.python.report.progress import ProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _Reporter:
    def __init__(self) -> None:
        self.warns: list[str] = []
        self.oks: list[str] = []

    def info(self, *_a, **_k) -> None:
        pass

    def ok(self, msg: str, *_a, **_k) -> None:
        self.oks.append(msg)

    def warn(self, msg: str, *_a, **_k) -> None:
        self.warns.append(msg)


def _holding(code: str, name: str = "标的", shares: float = 100.0) -> SimpleNamespace:
    return SimpleNamespace(code=code, name=name, shares=shares)


def _bars() -> list[dict]:
    return [{"date": "2026-09-01", "close": 1.0}]


def _detail(code: str, name: str = "贵州茅台", market_value: float = 1000.0) -> SimpleNamespace:
    return SimpleNamespace(code=code, name=name, market_value=market_value)


def _reporter() -> ProgressReporter:
    return cast(ProgressReporter, _Reporter())


def _enable(monkeypatch, *, fund_deep: bool = True, factor_catalog: bool = True) -> None:
    monkeypatch.setattr("src.python.config.is_enable_fund_deep_analysis", lambda config: fund_deep)
    monkeypatch.setattr("src.python.config.is_enable_factor_catalog", lambda: factor_catalog)


def _stub_compute_layer(monkeypatch) -> None:
    monkeypatch.setattr(rfm, "_fetch_holding_bars", lambda code, name, days: _bars())
    monkeypatch.setattr("src.python.fetcher.index.fetch_index_history", lambda code, days=90, start_from=None: _bars())
    monkeypatch.setattr(sfr, "asif_portfolio_daily_returns", lambda bars: {"2026-09-01": 0.02})
    monkeypatch.setattr(sfr, "filter_stale_factor_klines", lambda klines, today: (dict(klines), []))
    monkeypatch.setattr(sfr, "klines_to_returns", lambda bars: {"2026-09-01": 0.01})
    monkeypatch.setattr(sfr, "compute_factor_exposure", lambda *a, **k: {"available": True, "sample_count": 60})


class TestComputeFactorExposureData:
    def test_feature_disabled_returns_none(self, monkeypatch):
        _enable(monkeypatch, fund_deep=False)
        assert rfm.compute_factor_exposure_data([], {}, _reporter()) is None

    def test_compute_layer_import_error_degrades(self, monkeypatch):
        _enable(monkeypatch)
        monkeypatch.setitem(sys.modules, "src.python.analysis.style_factor_regression", None)
        reporter = _Reporter()

        result = rfm.compute_factor_exposure_data([], {}, cast(ProgressReporter, reporter))

        assert result is not None and result["available"] is False
        assert result["status"] == "source_failed"
        assert reporter.warns, "依赖缺失必须留 warn，否则报告只有占位看不出原因"

    def test_empty_portfolio_returns_reports_insufficient(self, monkeypatch):
        _enable(monkeypatch)
        _stub_compute_layer(monkeypatch)
        monkeypatch.setattr(sfr, "asif_portfolio_daily_returns", lambda bars: {})

        result = rfm.compute_factor_exposure_data([_holding("600519")], {}, _reporter())

        assert result is not None and result["status"] == "insufficient"

    def test_all_factor_klines_empty_reports_source_failed(self, monkeypatch):
        _enable(monkeypatch)
        _stub_compute_layer(monkeypatch)
        monkeypatch.setattr("src.python.fetcher.index.fetch_index_history", lambda code, days=90, start_from=None: [])

        result = rfm.compute_factor_exposure_data([_holding("600519")], {}, _reporter())

        assert result is not None and result["status"] == "source_failed", "全部因子空拉取属数据源故障，不是数据不足"

    def test_too_few_fresh_factors_lists_excluded(self, monkeypatch):
        _enable(monkeypatch)
        _stub_compute_layer(monkeypatch)

        def _filter(klines, today):
            stale = sorted(klines)[: len(klines) - 1]
            fresh = {f: bars for f, bars in klines.items() if f not in stale}
            return fresh, stale

        monkeypatch.setattr(sfr, "filter_stale_factor_klines", _filter)

        result = rfm.compute_factor_exposure_data([_holding("600519")], {}, _reporter())

        assert result is not None and result["status"] == "insufficient"
        assert len(result["stale_factors"]) == len(sfr.FACTOR_INDICES) - 1

    def test_success_carries_stale_factor_list(self, monkeypatch):
        _enable(monkeypatch)
        _stub_compute_layer(monkeypatch)
        monkeypatch.setattr(sfr, "filter_stale_factor_klines", lambda klines, today: (dict(klines), ["value"]))
        reporter = _Reporter()

        result = rfm.compute_factor_exposure_data([_holding("600519")], {}, cast(ProgressReporter, reporter))

        assert result is not None and result["available"] is True
        assert result["stale_factors"] == ["value"], "剔除的停更因子必须进契约，供报告标注"
        assert reporter.oks == ["风格因子回归完成"]

    def test_unavailable_result_warns_with_sample_count(self, monkeypatch):
        _enable(monkeypatch)
        _stub_compute_layer(monkeypatch)
        monkeypatch.setattr(sfr, "compute_factor_exposure", lambda *a, **k: {"available": False, "sample_count": 12})
        reporter = _Reporter()

        rfm.compute_factor_exposure_data([_holding("600519")], {}, cast(ProgressReporter, reporter))

        assert any("12" in msg for msg in reporter.warns), reporter.warns

    def test_exception_degrades_without_raising(self, monkeypatch):
        _enable(monkeypatch)
        _stub_compute_layer(monkeypatch)
        monkeypatch.setattr(sfr, "compute_factor_exposure", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

        result = rfm.compute_factor_exposure_data([_holding("600519")], {}, _reporter())

        assert result is not None and result["status"] == "source_failed"


class TestComputeIndustryBetaData:
    def _stub(self, monkeypatch, *, exposure: dict, betas: dict | None = None) -> dict[str, object]:
        calls: dict[str, object] = {"index_codes": []}

        monkeypatch.setattr(
            "src.python.fetcher.industry.batch_fetch_industry_data",
            lambda codes: calls.update(codes=codes) or _INDUSTRY_MAP,
        )
        monkeypatch.setattr(ib, "compute_industry_exposure", lambda cap: {"available": True, "exposure": exposure})
        monkeypatch.setattr(
            ib,
            "compute_industry_beta_analysis",
            lambda portfolio, returns: (
                {"available": True, "betas": betas or {}}
                if betas is not None
                else {"available": False, "status": "insufficient"}
            ),
        )

        def _index_history(code, days=90, start_from=None):
            cast(list[str], calls["index_codes"]).append(code)
            return _bars()

        monkeypatch.setattr("src.python.fetcher.index.fetch_index_history", _index_history)
        monkeypatch.setattr(rfm, "_fetch_holding_bars", lambda code, name, days: _bars())
        monkeypatch.setattr(sfr, "asif_portfolio_daily_returns", lambda bars: {"2026-09-01": 0.02})
        monkeypatch.setattr(sfr, "klines_to_returns", lambda bars: {"2026-09-01": 0.01})
        return calls

    def test_fund_deep_analysis_disabled_returns_none(self, monkeypatch):
        _enable(monkeypatch, fund_deep=False)
        assert rfm.compute_industry_beta_data([], [], {}, _reporter()) is None

    def test_factor_catalog_disabled_returns_none(self, monkeypatch):
        _enable(monkeypatch, factor_catalog=False)
        assert rfm.compute_industry_beta_data([], [], {}, _reporter()) is None

    def test_industry_beta_import_error_degrades(self, monkeypatch):
        _enable(monkeypatch)
        monkeypatch.setitem(sys.modules, "src.python.analysis.industry_beta", None)
        reporter = _Reporter()

        result = rfm.compute_industry_beta_data([], [], {}, cast(ProgressReporter, reporter))

        assert result is not None and result["status"] == "source_failed"
        assert reporter.warns, "依赖缺失必须留 warn"

    def test_exposure_unavailable_degrades(self, monkeypatch):
        _enable(monkeypatch)
        self._stub(monkeypatch, exposure={})
        monkeypatch.setattr(ib, "compute_industry_exposure", lambda cap: {"available": False, "exposure": {}})

        result = rfm.compute_industry_beta_data([], [_detail("600519")], {}, _reporter())

        assert result is not None and result["status"] == "source_failed"

    def test_empty_portfolio_returns_insufficient(self, monkeypatch):
        _enable(monkeypatch)
        self._stub(monkeypatch, exposure={"银行": 0.4})
        monkeypatch.setattr(sfr, "asif_portfolio_daily_returns", lambda bars: {})

        result = rfm.compute_industry_beta_data([_holding("600519")], [_detail("600519")], {}, _reporter())

        assert result is not None and result["status"] == "insufficient"

    def test_beta_unavailable_keeps_exposure_and_fetches_no_index(self, monkeypatch):
        _enable(monkeypatch)
        calls = self._stub(monkeypatch, exposure={"未映射行业": 0.6})
        reporter = _Reporter()

        result = rfm.compute_industry_beta_data(
            [_holding("600519")], [_detail("600519")], {}, cast(ProgressReporter, reporter)
        )

        assert result is not None and result["available"] is False
        assert result["exposure"] == {"未映射行业": 0.6}
        assert calls["index_codes"] == [], "无映射行业时不得发出指数 K 线请求"
        assert reporter.warns

    def test_success_merges_exposure_index_codes_and_unmapped(self, monkeypatch):
        _enable(monkeypatch)
        calls = self._stub(monkeypatch, exposure={"银行": 0.6, "未映射行业": 0.4}, betas={"银行": 0.83})
        reporter = _Reporter()

        result = rfm.compute_industry_beta_data(
            [_holding("600519")], [_detail("600519")], {}, cast(ProgressReporter, reporter)
        )

        assert result is not None and result["available"] is True
        assert calls["index_codes"] == [ib.INDUSTRY_INDEX_MAP["银行"]]
        assert result["index_codes"] == {"银行": ib.INDUSTRY_INDEX_MAP["银行"]}
        assert result["unmapped_industries"] == ["未映射行业"]
        assert reporter.oks == ["行业 Beta 子表计算完成"]

    def test_exception_degrades_without_raising(self, monkeypatch):
        _enable(monkeypatch)
        self._stub(monkeypatch, exposure={"银行": 0.6})
        monkeypatch.setattr(ib, "compute_industry_exposure", lambda cap: (_ for _ in ()).throw(RuntimeError("boom")))

        result = rfm.compute_industry_beta_data([], [_detail("600519")], {}, _reporter())

        assert result is not None and result["status"] == "source_failed"


_INDUSTRY_MAP = {"600519": {"industry": "白酒"}}
