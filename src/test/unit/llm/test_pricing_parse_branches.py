"""LLM 计价模块的解析与降级分支：时段解析、时区换算、峰谷判定、单价聚合。

覆盖四组契约：
  一、`_parse_clock` / `_parse_periods`：HH:MM 与 HH:MM-HH:MM 的合法/非法输入
  二、`_load_timezone`：非法 IANA 名称降级为 None（回落本地时间，不影响计价）
  三、`_effective_minute` / `_is_weekend` / `_is_holiday`：aware datetime 先折算定价时区
  四、`_is_peak_minute` 三分支（闲时日 / 峰谷皆空 / 仅闲时段）+ `add_cost` 零额短路 +
     `reload_pricing` 加载异常时保留内置定价
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from src.python.llm import pricing

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]

_SHANGHAI = ZoneInfo("Asia/Shanghai")


# ── 一、时段解析 ────────────────────────────────────────


class TestParseClock:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("09:30", 570), (" 9:03 ", 543), ("00:00", 0), ("23:59", 1439)],
    )
    def test_valid_clocks(self, text, expected):
        assert pricing._parse_clock(text) == expected

    @pytest.mark.parametrize("text", ["24:00", "09:60", "-1:30", "0930", "09:xx", ""])
    def test_invalid_clocks_return_none(self, text):
        assert pricing._parse_clock(text) is None


class TestParsePeriods:
    def test_valid_list(self):
        assert pricing._parse_periods(["09:00-12:00", "14:00-18:00"]) == [(540, 720), (840, 1080)]

    def test_empty_list_is_legal(self):
        assert pricing._parse_periods([]) == []

    @pytest.mark.parametrize(
        "value",
        [
            "09:00-12:00",  # 非 list
            ["09:00-12:00", 5],  # 项非字符串
            ["09:00"],  # 缺连字符 → 段数不足
            ["09:00-12:00-15:00"],  # 段数过多
            ["09:00-24:00"],  # 时钟非法
        ],
    )
    def test_invalid_inputs_return_none(self, value):
        assert pricing._parse_periods(value) is None


# ── 二、时区加载降级 ────────────────────────────────────


class TestLoadTimezone:
    def test_valid_name_returns_zoneinfo(self):
        assert pricing._load_timezone("Asia/Shanghai") is not None

    def test_invalid_name_degrades_to_none(self):
        assert pricing._load_timezone("Not/A_Real_Zone") is None


# ── 三、时区换算 ────────────────────────────────────────


class TestTimezoneConversion:
    def test_effective_minute_converts_aware_datetime(self, monkeypatch):
        monkeypatch.setattr(pricing, "PRICING_TZ", _SHANGHAI)
        # UTC 01:30 = 北京 09:30
        assert pricing._effective_minute(datetime(2026, 11, 6, 1, 30, tzinfo=UTC)) == 570

    def test_effective_minute_naive_treated_as_pricing_zone(self, monkeypatch):
        monkeypatch.setattr(pricing, "PRICING_TZ", _SHANGHAI)
        assert pricing._effective_minute(datetime(2026, 11, 6, 14, 5)) == 845

    def test_is_weekend_converts_aware_datetime(self, monkeypatch):
        monkeypatch.setattr(pricing, "PRICING_TZ", _SHANGHAI)
        # 北京 2026-11-07 是周六；UTC 时间仍是 11-06（周五）→ 必须按折算后的时区判周末
        assert pricing._is_weekend(datetime(2026, 11, 6, 20, 0, tzinfo=UTC)) is True
        assert pricing._is_weekend(datetime(2026, 11, 6, 1, 0, tzinfo=UTC)) is False

    def test_is_holiday_converts_aware_datetime(self, monkeypatch):
        monkeypatch.setattr(pricing, "PRICING_TZ", _SHANGHAI)
        monkeypatch.setattr(
            "src.python.core.trading_calendar.cached_trading_days",
            lambda: ["2026-11-05"],
        )
        # 2026-11-06（周五）不在缓存交易日历中 → 认定为节假日
        assert pricing._is_holiday(datetime(2026, 11, 6, 1, 0, tzinfo=UTC)) is True

    def test_is_holiday_weekend_is_false(self, monkeypatch):
        monkeypatch.setattr(pricing, "PRICING_TZ", _SHANGHAI)
        assert pricing._is_holiday(datetime(2026, 11, 7, 12, 0)) is False


# ── 四、峰谷判定 ────────────────────────────────────────


class TestIsPeakMinute:
    def test_idle_day_always_off_peak(self):
        assert pricing._is_peak_minute(600, idle_day=True) is False

    def test_no_periods_configured_is_never_peak(self, monkeypatch):
        monkeypatch.setattr(pricing, "PRICING_PEAK_PERIODS", [])
        monkeypatch.setattr(pricing, "PRICING_IDLE_PERIODS", [])
        assert pricing._is_peak_minute(600) is False

    def test_idle_periods_invert_meaning(self, monkeypatch):
        """仅配闲时段时（官方方案）：闲时段内非高峰，其余为高峰。"""
        monkeypatch.setattr(pricing, "PRICING_PEAK_PERIODS", [])
        monkeypatch.setattr(pricing, "PRICING_IDLE_PERIODS", [(540, 720)])
        assert pricing._is_peak_minute(600) is False
        assert pricing._is_peak_minute(800) is True


class TestCostBuckets:
    def test_add_cost_ignores_zero_amount(self):
        buckets: dict[str, float] = {}
        pricing.add_cost(buckets, "CNY", 0.0)
        assert buckets == {}

    def test_add_cost_accumulates_per_currency(self):
        buckets: dict[str, float] = {}
        pricing.add_cost(buckets, "cny", 1.5)
        pricing.add_cost(buckets, "CNY", 2.5)
        assert buckets == {"CNY": pytest.approx(4.0)}


class TestReloadPricingFallback:
    def test_load_failure_keeps_builtin_pricing(self, monkeypatch):
        """计价参考加载抛错 → 只记 debug，内置价仍在且标记为已加载（不再二次读取）。"""

        def _boom():
            raise RuntimeError("参考文件损坏")

        monkeypatch.setattr("src.python.config.load_pricing_config", _boom)
        before = dict(pricing.PRICING_MERGED)
        pricing.reload_pricing()
        assert dict(pricing.PRICING_MERGED) == before
        assert pricing._PRICING_LOADED is True
