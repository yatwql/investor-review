"""编排辅助（`report/_report_aux_metrics.py`）降级分支契约测试。

锁住的契约：
  - 市场温度的估值/无风险利率历史取数异常各自独立缺席（不连带）
  - 基金深度分析关闭时相关性章节返回 None（章节隐藏，非降级占位）
  - 单品种 K 线取数异常只丢该品种，有效持仓不足时落数据不足契约
  - 相关矩阵不可用/编排异常均返回携带 rolling=None 的降级契约
  - 市场情绪开关打开时上报进度并按装配函数契约原样返回
  - 景气度框架四个取数环节（穿透/历史快照/基金 ROE）异常各自降级，不拖垮其余维度

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_report_aux_metrics_branches.py -v
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.python.report import _report_aux_metrics as aux
from src.python.report.market_value import DetailRow

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


def _bars(n: int = 3, start: date = date(2026, 3, 2)) -> list[dict]:
    """确定性 K 线（date/close），两个端点即可产生一条日收益。"""
    out = []
    d = start
    for i in range(n):
        out.append({"date": (d + timedelta(days=i)).isoformat(), "close": 10.0 + i})
    return out


def _holdings(codes=("600001", "600002", "600003")) -> list[SimpleNamespace]:
    return [SimpleNamespace(code=c, name=f"品种{c[-1]}") for c in codes]


def _details() -> list[DetailRow]:
    return [DetailRow(account="A", name="贵州茅台", code="600519", market_value=100_000.0, cost=90_000.0)]


class TestTemperatureValuationInputs:
    """估值/ERP 输入序列的独立缺席降级。"""

    def test_valuation_fetch_exception_degrades_to_none(self, monkeypatch):
        def _boom(_code):
            raise RuntimeError("valuation boom")

        monkeypatch.setattr("src.python.fetcher.index_valuation.fetch_index_valuation_history", _boom)
        monkeypatch.setattr(
            "src.python.fetcher.bond_yield.get_risk_free_rate_history", lambda: [{"date": "2026-01-05", "yield": 1.8}]
        )

        assert aux._fetch_temperature_valuation_inputs("sh000300") == (None, None, None)

    def test_bond_yield_fetch_exception_only_drops_erp(self, monkeypatch):
        rows = [{"date": "2026-01-05", "pe": 13.0, "pb": 1.4}]

        def _boom():
            raise RuntimeError("bond boom")

        monkeypatch.setattr("src.python.fetcher.index_valuation.fetch_index_valuation_history", lambda _code: rows)
        monkeypatch.setattr("src.python.fetcher.bond_yield.get_risk_free_rate_history", _boom)

        pe, pb, erp = aux._fetch_temperature_valuation_inputs("sh000300")

        assert pe == [13.0], "估值序列不受利率链路异常影响"
        assert pb == [1.4]
        assert erp is None


class TestCorrelationDegrade:
    """相关性章节的开关与降级契约。"""

    def test_fund_deep_analysis_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr("src.python.config.is_enable_fund_deep_analysis", lambda config: False)

        assert aux.compute_correlation_data(_holdings(), {}, MagicMock()) is None

    def test_single_route_exception_degrades_to_insufficient(self, monkeypatch):
        def _boom(_code, _name, _days):
            raise RuntimeError("bar boom")

        monkeypatch.setattr("src.python.report._report_factor_metrics._fetch_holding_bars", _boom)

        result = aux.compute_correlation_data(_holdings(), {}, MagicMock())

        assert result is not None
        assert result["available"] is False
        assert result["rolling"] is None

    def test_matrix_unavailable_warns_and_carries_rolling_none(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.report._report_factor_metrics._fetch_holding_bars",
            lambda code, name, days: _bars(),
        )
        monkeypatch.setattr(
            "src.python.analysis.correlation.compute_correlation_matrix",
            lambda *a, **k: {"available": False, "sample_count": 0},
        )
        reporter = MagicMock()

        result = aux.compute_correlation_data(_holdings(), {}, reporter)

        assert result is not None
        assert result["available"] is False
        assert result["rolling"] is None, "不可用契约同样须带 rolling 键（渲染层统一判空）"
        reporter.warn.assert_called_once()

    def test_orchestration_exception_returns_source_failed(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.report._report_factor_metrics._fetch_holding_bars",
            lambda code, name, days: _bars(),
        )

        def _boom(*_a, **_k):
            raise RuntimeError("matrix boom")

        monkeypatch.setattr("src.python.analysis.correlation.compute_correlation_matrix", _boom)

        result = aux.compute_correlation_data(_holdings(), {}, MagicMock())

        assert result is not None
        assert result["available"] is False
        assert result["status"] == "source_failed"
        assert result["rolling"] is None


class TestMarketSentiment:
    """市场情绪编排的开关与上报。"""

    def test_enabled_reports_progress_and_returns_contract(self, monkeypatch):
        contract = {"available": True, "rows": []}
        monkeypatch.setattr("src.python.config.is_enable_market_sentiment", lambda: True)
        monkeypatch.setattr(
            "src.python.report.market_sentiment.build_market_sentiment_data",
            lambda _holdings, _penetrated, _config: contract,
        )
        reporter = MagicMock()

        result = aux.compute_market_sentiment_data([], {"penetrated_assets": []}, {}, reporter)

        assert result is contract
        reporter.info.assert_called_once()

    def test_switch_off_returns_none_without_reporting(self, monkeypatch):
        monkeypatch.setattr("src.python.config.is_enable_market_sentiment", lambda: False)
        reporter = MagicMock()

        assert aux.compute_market_sentiment_data([], {}, {}, reporter) is None
        reporter.info.assert_not_called()


class TestProsperityFrameworkDegrade:
    """景气度框架各取数环节的独立降级。"""

    def _capture_build(self, monkeypatch) -> dict:
        captured: dict = {}

        def _build(_details, **kwargs):
            captured.update(kwargs)
            return {"available": True, "total_score": 0, "scored_weight": 0, "total_score_pct": 0, "rating_label": ""}

        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda _key: True)
        monkeypatch.setattr("src.python.analysis.liquidity.check_liquidity", lambda *_a, **_k: [])
        monkeypatch.setattr("src.python.report.history_snapshot.load_all", lambda *_a, **_k: [])
        monkeypatch.setattr("src.python.analysis.prosperity_framework.build_prosperity_framework_data", _build)
        return captured

    def test_penetration_failure_degrades_to_no_penetration_data(self, monkeypatch):
        captured = self._capture_build(monkeypatch)

        def _boom(*_a, **_k):
            raise RuntimeError("penetration boom")

        monkeypatch.setattr("src.python.report.penetration.compute_penetration_top10", _boom)

        aux.compute_prosperity_framework_data([], _details(), {}, {})

        assert captured["penetration_data"] is None, "穿透失败不得拖垮诊断其余维度"

    def test_snapshot_failure_degrades_to_no_snapshots(self, monkeypatch):
        captured = self._capture_build(monkeypatch)

        def _boom(*_a, **_k):
            raise RuntimeError("snapshot boom")

        monkeypatch.setattr("src.python.report.history_snapshot.load_all", _boom)

        aux.compute_prosperity_framework_data([], _details(), {}, {})

        assert captured["snapshots"] is None

    def test_fund_roe_estimate_failure_degrades_to_none(self, monkeypatch):
        captured = self._capture_build(monkeypatch)

        def _boom(*_a, **_k):
            raise RuntimeError("roe boom")

        monkeypatch.setattr("src.python.report.fund_roe_estimate.estimate_fund_roe_batch", _boom)
        holdings = [SimpleNamespace(code="005827", name="易方达蓝筹精选混合", account="支付宝", shares=100.0)]

        aux.compute_prosperity_framework_data(holdings, _details(), {}, {})

        assert captured["fund_roe_estimates"] is None, "估算失败时 ②维退回个股口径，不得写占位值"
