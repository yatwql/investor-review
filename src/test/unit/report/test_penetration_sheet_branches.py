# -*- coding: utf-8 -*-
"""穿透页签分支覆盖：EPS/股息文本、取数降级、行业状态判定、估值列整表输出。

测试目标：
  - `_get_eps_text` / `_get_dividend_text` 的命中与缺省两态
  - `_load_profit_forecast_safe` / `_load_dividend_data_safe` 的异常降级（返回空 + False）
  - `build_penetration_data_status` 的行业失败类型分支（no_a_share 不记降级）
  - `write_penetration_sheet` 在 valuation_data 非 None 时的 11 列写入（估值列 + 免责声明）
  - `_num_formats` 的 11 列表头分支
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from openpyxl import Workbook

from src.python.report import penetration_sheet as ps

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _penetration_result(**overrides) -> dict:
    result = {
        "top10": [
            {
                "rank": 1,
                "name": "长江电力",
                "codes": ["600900"],
                "mv": 12345.6,
                "ratio_pct": 12.5,
                "sector": "公用事业",
                "concepts": ["水电"],
                "sources": ["易方达蓝筹精选"],
            },
            {
                "rank": 2,
                "name": "某境外标的",
                "codes": [],
                "mv": 1000.0,
                "ratio_pct": 1.0,
                "sources": ["某QDII"],
            },
        ],
        "summary": {
            "total_funds": 2,
            "total_stocks": 2,
            "fund_breakdown": "主动2",
            "merged_count": 2,
            "top10_coverage_pct": 55.0,
            "unknown_mv": 0.0,
            "failed_funds": 0,
            "failed_fund_details": [],
            "stale_funds": 0,
            "stale_fund_details": [],
            "report_periods": [],
        },
    }
    result.update(overrides)
    return result


def _sheet_text(ws) -> str:
    return "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)


class TestTextHelpers:
    def test_eps_text_hit_and_miss(self):
        forecast = {"600900": {"eps_2026e": 1.234}, "000001": {"eps_2026e": None}}
        assert ps._get_eps_text(forecast, ["600900"]) == "¥1.23"
        # 命中代码但 EPS 为 None → 继续遍历，最终 "--"
        assert ps._get_eps_text(forecast, ["000001"]) == "--"
        assert ps._get_eps_text(forecast, ["999999"]) == "--"
        assert ps._get_eps_text({}, ["600900"]) == "--"

    def test_dividend_text_hit_and_miss(self):
        data = {"600900": {"avg_dividend": 0.8512}, "000001": {"avg_dividend": 0}}
        assert ps._get_dividend_text(data, ["600900"]) == "0.8512元/年"
        assert ps._get_dividend_text(data, ["000001"]) == "--"
        assert ps._get_dividend_text({}, ["600900"]) == "--"


class TestSafeLoaders:
    def test_profit_forecast_exception_degrades(self, caplog):
        with patch("src.python.fetcher.akshare.get_profit_forecast", side_effect=RuntimeError("akshare 断连")):
            with caplog.at_level("WARNING"):
                data, ok = ps._load_profit_forecast_safe()
        assert (data, ok) == ({}, False)
        assert any("盈利预测获取失败" in rec.message for rec in caplog.records)

    def test_profit_forecast_success(self):
        with patch("src.python.fetcher.akshare.get_profit_forecast", return_value={"600900": {"eps_2026e": 1.0}}):
            assert ps._load_profit_forecast_safe() == ({"600900": {"eps_2026e": 1.0}}, True)

    def test_dividend_exception_degrades(self, caplog):
        with patch("src.python.fetcher.akshare.get_dividend_data", side_effect=RuntimeError("akshare 断连")):
            with caplog.at_level("WARNING"):
                data, ok = ps._load_dividend_data_safe(_penetration_result())
        assert (data, ok) == ({}, False)
        assert any("分红数据获取失败" in rec.message for rec in caplog.records)

    def test_dividend_no_a_share_codes_skips_call(self):
        result = _penetration_result(
            top10=[{"rank": 1, "name": "港股", "codes": ["00700"], "mv": 1.0, "ratio_pct": 1.0, "sources": ["x"]}]
        )
        with patch("src.python.fetcher.akshare.get_dividend_data") as fetch:
            assert ps._load_dividend_data_safe(result) == ({}, True)
        fetch.assert_not_called()


class TestDataStatus:
    def test_industry_no_a_share_is_not_degraded(self):
        """全为非 A 股穿透资产属预期行为，不记降级项。"""
        tracker = Mock()
        with patch.object(ps, "_tracker", return_value=tracker):
            status = ps.build_penetration_data_status(
                _penetration_result(industry_success=False, industry_failure_type="no_a_share")
            )
        assert status == {}
        tracker.record.assert_not_called()

    def test_industry_unreachable_records_cache_age(self):
        tracker = Mock()
        tracker.record.return_value = (True, "龙", 2)
        with (
            patch.object(ps, "_tracker", return_value=tracker),
            patch.object(ps, "get_cache_age_by_data_type", return_value=7200.0),
            patch.object(ps, "get_ttl", return_value=86400),
        ):
            status = ps.build_penetration_data_status(
                _penetration_result(industry_success=False, industry_failure_type="unreachable")
            )
        kwargs = tracker.record.call_args.kwargs
        assert kwargs["failure_type"] == "unreachable"
        assert kwargs["cache_age_hours"] == pytest.approx(2.0)
        assert kwargs["cache_ttl_hours"] == pytest.approx(24.0)
        assert status["industry"]["available"] is False
        assert status["industry"]["tier"] == "T3"
        assert status["industry"]["message"] == ps.STATUS_MESSAGES["industry_unavailable"]


class TestValuationColumn:
    def test_num_formats_wide(self):
        assert ps._num_formats() == [
            "",
            "",
            "",
            ps.FMT_MONEY,
            ps.FMT_PERCENT,
            "",
            "",
            "",
            "",
            "",
        ]
        assert ps._num_formats(ps._NCOLS + 1)[-1] == ""
        assert len(ps._num_formats(ps._NCOLS + 1)) == ps._NCOLS + 1

    def test_sheet_with_valuation_column(self):
        wb = Workbook()
        ws = wb.active
        valuation = {
            "basis_mode": "proxy_price",
            "by_code": {
                "600900": {
                    "pe": 18.5,
                    "pb": 2.31,
                    "percentile_available": True,
                    "price_percentile": 42.0,
                    "tier": "合理",
                }
            },
        }
        with (
            patch.object(ps, "_load_profit_forecast_safe", return_value=({}, True)),
            patch.object(ps, "_load_dividend_data_safe", return_value=({}, True)),
        ):
            ps.write_penetration_sheet(ws, [], [], _penetration_result(), valuation)
        text = _sheet_text(ws)
        assert ps._VALUATION_HEADER in text
        assert "PE 18.5 · PB 2.31 · 分位 42%（合理）" in text
        # 无代码行 → "--"（估值列与 EPS/股息列同口径）
        assert text.count("--") >= 2
        # 免责声明在表尾之后单列一行
        assert ps.valuation_footer_note(valuation) in text
