"""编排层数据的降级与边角分支（`report/_orchestrator_data`）。

贯穿本模块的契约是「**单个数据域失败只降级该域**」：预取失败留给渲染阶段重取、
因子目录算不动写占位、估值编排异常写 source_failed、真实分位取数失败回落价格代理。
本文件逐域注入故障，防止某一路异常把整份报告拖垮。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.python.report import _orchestrator_data as mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _Reporter:
    def __init__(self, *, fail_on_info: bool = False) -> None:
        self.infos: list[str] = []
        self.warns: list[str] = []
        self._fail = fail_on_info

    def info(self, msg: str) -> None:
        if self._fail:
            raise RuntimeError("probe fault")
        self.infos.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def ok(self, msg: str) -> None:
        pass


class TestWarmRenderContracts:
    def test_all_three_steps_fail_but_returns(self, monkeypatch, caplog):
        """三簇预取各自失败 → 均只留 DEBUG，不抛出（渲染阶段会重取）。"""

        def _raise(*args, **kwargs):
            raise RuntimeError("probe fault")

        monkeypatch.setattr("src.python.report.html_builders._build_perf_data", _raise)
        monkeypatch.setattr("src.python.report.html_renderers.prefetch_penetration_side_data", _raise)
        monkeypatch.setattr("src.python.config.is_enable_fund_deep_analysis", lambda config: True)
        monkeypatch.setattr("src.python.report.html_renderers._render_style_analysis", _raise)

        mod._warm_render_contracts([], [], _Reporter(), {})

        assert "基金业绩预取失败" in caplog.text
        assert "穿透附属取数预取失败" in caplog.text
        assert "基金风格预取失败" in caplog.text

    def test_style_prefetch_skipped_when_feature_off(self, monkeypatch):
        """`enable_fund_deep_analysis` 关闭 → 风格预取不执行（避免白取数）。"""
        render = MagicMock()
        monkeypatch.setattr("src.python.config.is_enable_fund_deep_analysis", lambda config: False)
        monkeypatch.setattr("src.python.report.html_renderers._render_style_analysis", render)

        mod._warm_render_contracts([], [], _Reporter(), {})

        render.assert_not_called()


class TestPenetratedTargets:
    def test_non_dict_entries_skipped(self):
        assert mod._penetrated_targets(["bad", 1, None]) == []

    def test_codes_and_sources_are_normalized(self):
        """`code` 与嵌套 `codes` 都展开；`直接持有` 来源被剔除（该标的以持仓身份入列）。"""
        assets = [
            {
                "name": "阳光电源",
                "code": "300274",
                "codes": ["300275", "300276"],
                "sources": ["[ETF] 招商中证电池主题ETF(561910)", "直接持有", "  "],
            }
        ]

        targets = mod._penetrated_targets(assets)

        assert [t["code"] for t in targets] == ["300274", "300275", "300276"]
        assert all(t["sources"] == ["[ETF] 招商中证电池主题ETF(561910)"] for t in targets)
        assert all(t["name"] == "阳光电源" for t in targets)

    def test_asset_without_code_yields_nothing(self):
        assert mod._penetrated_targets([{"name": "无代码", "codes": []}]) == []

    def test_none_input(self):
        assert mod._penetrated_targets(None) == []


class TestFinancialReportDigest:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr("src.python.config.is_enable_stock_fundamentals", lambda: False)

        assert mod.compute_financial_report_digest_data([], [], {}, _Reporter()) is None

    def test_delegates_with_penetrated_targets(self, monkeypatch):
        """开启时把穿透标的（含来源标签）一并交给摘要构建器。"""
        monkeypatch.setattr("src.python.config.is_enable_stock_fundamentals", lambda: True)
        build = MagicMock(return_value={"available": True})
        monkeypatch.setattr("src.python.report.financial_report_digest.build_financial_report_digest", build)
        assets = [{"name": "阳光电源", "code": "300274", "sources": ["[ETF] 561910"]}]

        result = mod.compute_financial_report_digest_data([], assets, {}, _Reporter())

        assert result == {"available": True}
        assert build.call_args.kwargs["penetrated_targets"] == [
            {"code": "300274", "name": "阳光电源", "sources": ["[ETF] 561910"]}
        ]


class TestValuationData:
    def test_disabled_returns_none(self, monkeypatch):
        monkeypatch.setattr("src.python.config.is_enable_valuation_percentile", lambda: False)

        assert mod.compute_valuation_data([], {}, _Reporter()) is None

    def test_orchestration_exception_degrades(self, monkeypatch):
        """编排异常（进度通道故障等）→ source_failed 占位，不把异常抛给报告链。"""
        monkeypatch.setattr("src.python.config.is_enable_valuation_percentile", lambda: True)
        monkeypatch.setattr("src.python.config.datasink_feature_ready", lambda config: False)

        result = mod.compute_valuation_data([], {}, _Reporter(fail_on_info=True))

        assert result["available"] is False
        assert result["status"] == "source_failed"

    def test_no_available_code_writes_placeholder(self, monkeypatch):
        """全部标的无估值 → 明确占位（而不是空章节）。"""
        monkeypatch.setattr("src.python.config.is_enable_valuation_percentile", lambda: True)
        monkeypatch.setattr("src.python.config.datasink_feature_ready", lambda config: False)
        detail = MagicMock()
        detail.code = "600900"
        detail.name = "长江电力"
        monkeypatch.setattr("src.python.core.code_utils.is_a_share_stock", lambda name, code: True)
        monkeypatch.setattr(mod, "_fetch_valuation_for_code", lambda code, name: None)
        reporter = _Reporter()

        result = mod.compute_valuation_data([detail], {}, reporter)

        assert result["available"] is False
        assert reporter.warns, "占位必须上屏提示，不能静默少一节"


class TestFetchValuationForCode:
    def test_none_when_all_sources_unavailable(self, monkeypatch):
        """PE/PB、价格分位、真实分位全不可得 → None（该标的按无估值处理）。"""
        monkeypatch.setattr("src.python.config.datasink_feature_ready", lambda: False)
        monkeypatch.setattr("src.python.fetcher.industry.fetch_valuation_fields", lambda code: {})
        monkeypatch.setattr(mod, "_fetch_holding_bars", lambda code, name, days: [])
        monkeypatch.setattr("src.python.analysis.valuation_percentile.compute_price_percentile", lambda bars: {})

        assert mod._fetch_valuation_for_code("600900", "长江电力") is None

    def test_price_percentile_only_still_returned(self, monkeypatch):
        monkeypatch.setattr("src.python.config.datasink_feature_ready", lambda: False)
        monkeypatch.setattr("src.python.fetcher.industry.fetch_valuation_fields", lambda code: {"pe": 12.3})
        monkeypatch.setattr(mod, "_fetch_holding_bars", lambda code, name, days: [{"close": 1}])
        monkeypatch.setattr(
            "src.python.analysis.valuation_percentile.compute_price_percentile",
            lambda bars: {"available": True, "price_percentile": 42.0, "tier": "合理", "sample_count": 700},
        )

        result = mod._fetch_valuation_for_code("600900", "长江电力")

        assert result["pe"] == pytest.approx(12.3)
        assert result["price_percentile"] == pytest.approx(42.0)
        assert result["percentile_available"] is True
        assert result["real_available"] is False


class TestRealValuation:
    def test_datasink_not_ready_skips_all_fetching(self, monkeypatch):
        """数据底座未就绪 → 零取数、零计算，直接回落价格代理。"""
        fetch = MagicMock()
        monkeypatch.setattr("src.python.config.datasink_feature_ready", lambda: False)
        monkeypatch.setattr("src.python.fetcher.financial_indicator.fetch_indicator_series", fetch)

        result = mod._real_valuation_for_code("600900", [])

        assert result == {"available": False, "reason": "datasink_unavailable"}
        fetch.assert_not_called()

    def test_indicator_fetch_failure_degrades(self, monkeypatch):
        """指标序列取数失败 → 以空记录继续（不伪造历史期）。"""
        monkeypatch.setattr("src.python.config.datasink_feature_ready", lambda: True)

        def _raise(code):
            raise OSError("network down")

        monkeypatch.setattr("src.python.fetcher.financial_indicator.fetch_indicator_series", _raise)
        compute = MagicMock(return_value={"available": False, "reason": "insufficient"})
        monkeypatch.setattr("src.python.analysis.valuation_percentile.compute_real_valuation", compute)

        result = mod._real_valuation_for_code("600900", [{"close": 1}])

        assert result == {"available": False, "reason": "insufficient"}
        assert compute.call_args.args[1] == [], "取数失败后按空记录计算"

    def test_compute_failure_degrades(self, monkeypatch):
        monkeypatch.setattr("src.python.config.datasink_feature_ready", lambda: True)
        monkeypatch.setattr("src.python.fetcher.financial_indicator.fetch_indicator_series", lambda code: [{}])

        def _raise(bars, records):
            raise ValueError("bad shape")

        monkeypatch.setattr("src.python.analysis.valuation_percentile.compute_real_valuation", _raise)

        assert mod._real_valuation_for_code("600900", []) == {"available": False, "reason": "compute_failed"}


class TestPrepareReportDataFactorCatalogDegrade:
    """因子目录（实验开关）算不动时写降级占位，报告其余部分照常组装。"""

    def _stub_stages(self, monkeypatch):
        summary = mod._MarketSummary(
            details=[],
            total_mv=1000.0,
            total_cost=900.0,
            total_profit=100.0,
            total_today_profit=1.0,
            categories={},
        )
        monkeypatch.setattr(mod, "_prepare_market_details", lambda *a, **k: summary)
        monkeypatch.setattr(mod, "_fetch_index_quotes", lambda *a, **k: ({}, {}))
        monkeypatch.setattr(mod, "_compute_penetration", lambda *a, **k: [])
        monkeypatch.setattr(mod, "_compute_style_contracts", lambda *a, **k: ({}, {}))
        monkeypatch.setattr(mod, "_compute_holdings_status", lambda *a, **k: ({}, {}))
        monkeypatch.setattr(mod, "_compute_valuation_contracts", lambda *a, **k: (None, None))
        monkeypatch.setattr(mod, "_compute_financial_contracts", lambda *a, **k: (None, None))
        monkeypatch.setattr(mod, "_compute_purchase_and_cost", lambda *a, **k: (None, None))
        monkeypatch.setattr("src.python.report._holding_detail_rows.build_holding_detail_rows", lambda *a, **k: [])
        monkeypatch.setattr("src.python.analysis.action_advisor.build_action_data", lambda *a, **k: {})
        monkeypatch.setattr("src.python.report.decision_basis.build_decision_basis_data", lambda *a, **k: {})
        monkeypatch.setattr("src.python.config.anonymizer.get_anonymization_mode", lambda: "off")

    def test_builder_failure_yields_unavailable_placeholder(self, monkeypatch, caplog):
        self._stub_stages(monkeypatch)
        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda name: name == "factor_catalog")

        def _raise(codes):
            raise ValueError("bad codes")

        monkeypatch.setattr("src.python.analysis.factor_evaluator.derive_factor_pool", lambda *a, **k: {"codes": []})
        monkeypatch.setattr("src.python.analysis.factor_evaluator.build_factor_catalog_data", _raise)

        data = mod.prepare_report_data([], _Reporter(), {})

        assert data["factor_catalog_data"] == {"available": False, "reason": "计算异常: ValueError"}
        assert "因子目录计算失败" in caplog.text

    def test_feature_disabled_keeps_key_none(self, monkeypatch):
        self._stub_stages(monkeypatch)
        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda name: False)

        data = mod.prepare_report_data([], _Reporter(), {})

        assert data["factor_catalog_data"] is None, "开关关闭时不计算，键为 None 供下游无感"
