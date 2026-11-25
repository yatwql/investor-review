# -*- coding: utf-8 -*-
"""因子目录备数探针（factor_catalog_loader.probe_*）与备数成功分支。

既有测试覆盖校验与注入式备数（probes=...）的失败分支；本文件补齐**缺省实现**
（probe_* 四条真实链路入口）的成功/异常两条路径，以及注入式备数的成功落库
（指数序列、财务指标 dict）。

取数入口一律 patch 调用点所在模块，零网络。
"""

from __future__ import annotations

import pytest

from src.python.fetcher import factor_catalog_loader as loader

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestProbeBars:
    def test_success_passes_code_and_lookback(self, monkeypatch):
        seen = {}

        def fake_chain(chain_name, code, days):
            seen.update(chain=chain_name, code=code, days=days)
            return [{"date": "2026-10-29", "close": 20.0}]

        monkeypatch.setattr("src.python.fetcher.chain_incremental.fetch_with_incremental_fallback", fake_chain)
        bars = loader.probe_bars("600900")
        assert bars == [{"date": "2026-10-29", "close": 20.0}]
        assert seen == {"chain": "history_stock", "code": "600900", "days": loader.LOOKBACK_DAYS}

    def test_exception_degrades_to_empty(self, monkeypatch, caplog):
        def boom(*_a, **_kw):
            raise RuntimeError("日K链路熔断")

        monkeypatch.setattr("src.python.fetcher.chain_incremental.fetch_with_incremental_fallback", boom)
        with caplog.at_level("WARNING"):
            assert loader.probe_bars("600900") == []
        assert any("日K失败" in rec.message for rec in caplog.records)


class TestProbeIndex:
    def test_success_uses_benchmark_index(self, monkeypatch):
        seen = {}

        def fake_index(code, days):
            seen.update(code=code, days=days)
            return [{"date": "2026-10-29", "close": 3900.0}]

        monkeypatch.setattr("src.python.fetcher.index.fetch_index_history", fake_index)
        from src.python.schemas.factor_catalog import BENCHMARK_INDEX

        bars = loader.probe_index()
        assert bars[0]["close"] == pytest.approx(3900.0)
        assert seen["code"] == BENCHMARK_INDEX

    def test_exception_degrades_to_empty(self, monkeypatch, caplog):
        monkeypatch.setattr(
            "src.python.fetcher.index.fetch_index_history",
            lambda *_a: (_ for _ in ()).throw(RuntimeError("指数源超时")),
        )
        with caplog.at_level("WARNING"):
            assert loader.probe_index() == []
        assert any("指数历史失败" in rec.message for rec in caplog.records)


class TestProbeValuationAndFin:
    def test_valuation_success_and_exception(self, monkeypatch, caplog):
        monkeypatch.setattr("src.python.fetcher.industry.fetch_valuation_fields", lambda code: {"pe": 8.5})
        assert loader.probe_valuation("600900") == {"pe": 8.5}

        monkeypatch.setattr(
            "src.python.fetcher.industry.fetch_valuation_fields",
            lambda code: (_ for _ in ()).throw(RuntimeError("push2 超时")),
        )
        with caplog.at_level("WARNING"):
            assert loader.probe_valuation("600900") is None
        assert any("估值失败" in rec.message for rec in caplog.records)

    def test_fin_indicator_success_and_exception(self, monkeypatch, caplog):
        monkeypatch.setattr("src.python.fetcher.financial_indicator.fetch_latest_indicator", lambda code: {"roe": 0.15})
        assert loader.probe_fin_indicator("600900") == {"roe": 0.15}

        monkeypatch.setattr(
            "src.python.fetcher.financial_indicator.fetch_latest_indicator",
            lambda code: (_ for _ in ()).throw(RuntimeError("财报源 404")),
        )
        with caplog.at_level("WARNING"):
            assert loader.probe_fin_indicator("600900") is None
        assert any("财务指标失败" in rec.message for rec in caplog.records)


class TestLoadInputsSuccess:
    def test_index_and_fin_success_are_stored(self):
        def fin(code):
            return {"roe": 0.15} if code == "600900" else {"roe": None}

        inputs = loader.load_factor_inputs(
            ["600900", "000001"],
            probes={
                "index": lambda: [{"date": "2026-10-29", "close": 3900.0}],
                "bars": lambda code: [{"date": "2026-10-29", "close": 20.0}],
                "valuation": lambda code: {"pb": 1.2},
                "fin": fin,
            },
        )
        assert inputs["index_bars"] == [{"date": "2026-10-29", "close": 3900.0}]
        assert inputs["fin_by_code"] == {"600900": {"roe": 0.15}}
        # 全空财务指标进 unavailable，不进 fin_by_code
        assert inputs["unavailable"]["fin_indicator"] == {"000001": "财务指标不可得"}
        assert inputs["valuation_by_code"]["000001"] == {"pb": 1.2}

    def test_valuation_and_fin_exceptions_record_reason(self):
        def boom(*_a, **_kw):
            raise RuntimeError("网关拒答")

        inputs = loader.load_factor_inputs(
            ["600900"],
            probes={
                "index": lambda: [{"date": "2026-10-29", "close": 3900.0}],
                "bars": lambda code: [{"date": "2026-10-29", "close": 20.0}],
                "valuation": boom,
                "fin": boom,
            },
        )
        assert inputs["valuation_by_code"] == {}
        assert inputs["fin_by_code"] == {}
        assert inputs["unavailable"]["valuation"] == {"600900": "估值字段不可得"}
        assert inputs["unavailable"]["fin_indicator"] == {"600900": "财务指标不可得"}
