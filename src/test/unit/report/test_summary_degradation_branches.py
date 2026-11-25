"""汇总页签的降级渲染（`report/summary`）。

三处「不能装作一切正常」的渲染契约：
  - 有成本但市值全零（非交易时段/限速）→ 顶部警示条，别让用户把 0 市值当真实亏损；
  - 市场温度字段不全 → 分数与三因子行分别降级（不是整块不写、也不是显示 0）；
  - 指数走了备用源/过期缓存 → 数据源状态脚注登记降级项，供数据源矩阵与用户对账。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook

from src.python.report import summary as mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _all_texts(ws) -> list[str]:
    """页签内全部非空单元格文本（标签在 A 列、数值在 B 列，只看 A 列会漏值）。"""
    return [str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None]


def _sheet():
    wb = Workbook()
    ws = wb.active
    if ws is None:  # pragma: no cover - openpyxl 至少一个 sheet
        ws = wb.create_sheet()
    return ws


class TestProfitSummaryDataUnavailable:
    def test_warning_banner_when_market_value_is_zero(self):
        """市值全零但有成本 → 顶部黄色警示条（防把「取数失败」读成「亏光了」）。"""
        ws = _sheet()

        mod._write_profit_summary(ws, 3, total_mv=0.0, total_cost=1000.0, total_profit=-1000.0, today_profit=0.0)

        texts = _all_texts(ws)
        assert any("行情数据全部不可用" in t for t in texts)

    def test_no_banner_when_market_value_present(self):
        ws = _sheet()

        mod._write_profit_summary(ws, 3, total_mv=1200.0, total_cost=1000.0, total_profit=200.0, today_profit=0.0)

        texts = _all_texts(ws)
        assert not any("行情数据全部不可用" in t for t in texts)


class TestMarketTemperature:
    def test_unavailable_is_silently_omitted(self):
        """不可用或缺失 → 不写任何行（用户未主动要求的功能不留降级痕迹）。"""
        ws = _sheet()

        assert mod._write_market_temperature(ws, 1, {"available": False}) == 1
        assert mod._write_market_temperature(ws, 1, None) == 1

    def test_missing_score_shows_placeholder(self):
        """分数缺失 → 温度值写 `--（档位）`，档位文案仍保留。"""
        ws = _sheet()

        mod._write_market_temperature(ws, 1, {"available": True, "tier": "偏热"})

        texts = _all_texts(ws)
        assert any("--（偏热）" in t for t in texts)

    def test_incomplete_factors_show_explicit_note(self):
        """分位/偏离/波动率任一缺失 → 三因子行明确写「因子数据不完整」。"""
        ws = _sheet()

        mod._write_market_temperature(ws, 1, {"available": True, "score": 72, "price_percentile": 40.0})

        texts = _all_texts(ws)
        assert any("因子数据不完整" in t for t in texts)

    def test_valuation_percentile_preferred_over_price_percentile(self):
        """有估值分位时优先展示（口径更贴近「贵不贵」），否则回落价格分位。"""
        ws = _sheet()

        mod._write_market_temperature(
            ws,
            1,
            {
                "available": True,
                "score": 60,
                "valuation_percentile": 33.3,
                "price_percentile": 88.8,
                "ma_deviation": 0.02,
                "volatility": 0.18,
            },
        )

        rows = [" | ".join(str(c.value) for c in row if c.value is not None) for row in ws.iter_rows()]
        factor_row = next(row for row in rows if "三因子" in row)
        assert "33.3%" in factor_row
        assert "88.8%" not in factor_row


class TestIndexDataStatus:
    def _degraded_record(self):
        return (True, None, None)

    def test_degraded_a_share_index_recorded(self):
        """A 股指数来自备用源/过期缓存 → 登记 index_a 降级项。"""
        tracker = MagicMock()
        tracker.return_value.record.return_value = self._degraded_record()
        with (
            patch.object(mod, "_tracker", tracker),
            patch.object(mod, "get_cache_age_by_data_type", return_value=7200.0),
            patch.object(mod, "get_ttl", return_value=43200.0),
        ):
            status = mod.build_index_data_status({"sh000001": {"_source": "sina"}}, None)

        assert "index_a" in status
        assert status["index_a"]["available"] is False
        assert status["index_a"]["tier"] == "T2"

    def test_degraded_us_index_recorded(self):
        tracker = MagicMock()
        tracker.return_value.record.return_value = self._degraded_record()
        with (
            patch.object(mod, "_tracker", tracker),
            patch.object(mod, "get_cache_age_by_data_type", return_value=None),
            patch.object(mod, "get_ttl", return_value=None),
        ):
            status = mod.build_index_data_status(None, {"gb_dji": {"_source": "stale_cache"}})

        assert "index_us" in status
        assert tracker.return_value.record.call_args.kwargs["cache_ttl_hours"] == 24

    def test_primary_sources_produce_no_status(self):
        tracker = MagicMock()
        with patch.object(mod, "_tracker", tracker):
            status = mod.build_index_data_status({"sh000001": {"_source": "tencent"}}, {"gb_dji": {"_source": "sina"}})

        assert status == {}
        tracker.return_value.record.assert_not_called()

    def test_not_yet_degraded_keeps_status_empty(self):
        """熔断未触发（未达连续失败阈值）→ 只计数不登记（避免单次抖动就报降级）。"""
        tracker = MagicMock()
        tracker.return_value.record.return_value = (False, None, None)
        with (
            patch.object(mod, "_tracker", tracker),
            patch.object(mod, "get_cache_age_by_data_type", return_value=0),
            patch.object(mod, "get_ttl", return_value=0),
        ):
            status = mod.build_index_data_status({"sh000001": {"_source": "stale_cache"}}, None)

        assert status == {}


class TestSummarySheetWiring:
    def test_market_temperature_section_written(self):
        """市场温度契约非 None 时写入汇总页签（开关关闭时为 None，不写）。"""
        ws = _sheet()

        mod.write_summary_sheet(
            ws,
            total_mv=0.0,
            total_cost=0.0,
            total_profit=0.0,
            today_profit=0.0,
            categories={"股票": 1},
            a_indices={"sh000001": {"name": "上证指数", "price": 3000.0, "_source": "tencent"}},
            us_indices=None,
            market_temperature_data={
                "available": True,
                "score": 55,
                "tier": "中性",
                "price_percentile": 50.0,
                "ma_deviation": 0.01,
                "volatility": 0.2,
            },
        )

        texts = _all_texts(ws)
        assert any("市场温度" in t for t in texts)
