"""多币种计价口径：原生币种展示、配置币种优先、跨币种分组、预算内部折算。

锁定四条纪律：
  - 展示的金额按模型生效币种出符号（Claude/GPT/Gemini 出 `$`，DeepSeek/Kimi 出 `¥`）；
  - 厂商同时提供多币种价时以配置币种为主（条目 `alt` 子表）；
  - 聚合一律按币种分组，跨币种**不相加**；
  - 唯一的折算点是日预算判定，折算结果不进展示金额。
"""

from __future__ import annotations

from datetime import date

import pytest

from src.python.llm import pricing
from src.python.llm.pricing import (
    add_cost,
    convert_amount,
    estimate_cost,
    format_costs,
    merge_costs,
    model_currency,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestNativeCurrencyDisplay:
    """费用符号跟随模型原生币种。"""

    def test_cny_vendor_uses_yuan(self):
        assert pricing.estimate_cost("deepseek-flash", 1_000_000, 1_000_000).startswith("¥")

    def test_usd_vendor_uses_dollar(self):
        assert pricing.estimate_cost("claude-sonnet-5-5", 1_000_000, 1_000_000).startswith("$")

    def test_unknown_model_is_not_priced(self):
        assert model_currency("no-such-model") == pricing.PRICING_CURRENCY
        assert estimate_cost("no-such-model", 1000, 500) == "-"


class TestConfiguredCurrencyPriority:
    """条目提供配置币种价时以配置币种计费与显示。"""

    def test_alt_subtable_switches_currency(self, monkeypatch):
        pricing.reload_pricing()  # 定表，避免首次计费懒加载覆盖注入的条目
        entry = dict(pricing.PRICING_MERGED["gpt-6.1-sol"])
        entry["alt"] = {"CNY": {"input": 15.0, "output": 75.0, "input_cache_hit": 0.75}}
        monkeypatch.setitem(pricing.PRICING_MERGED, "gpt-6.1-sol", entry)

        assert model_currency("gpt-6.1-sol") == "CNY"
        assert estimate_cost("gpt-6.1-sol", 1_000_000, 1_000_000) == "¥90.000"

    def test_native_currency_kept_when_config_not_offered(self, monkeypatch):
        """只提供原生币种时按原生币种显示（配置币种不强行套用）。"""
        pricing.reload_pricing()
        monkeypatch.setattr(pricing, "PRICING_CURRENCY", "EUR")
        assert model_currency("claude-sonnet-5-5") == "USD"


class TestDefaultCurrency:
    """缺省币种（本地主币种）单点定义，默认 CNY。"""

    def test_constant_defaults_to_cny(self):
        from src.python.core.constants import PRICING_DEFAULT_CURRENCY

        assert PRICING_DEFAULT_CURRENCY == "CNY"

    def test_runtime_and_reference_template_agree(self):
        from src.python.config._llm_pricing import _default_policy, render_default_pricing_ref
        from src.python.core.constants import PRICING_DEFAULT_CURRENCY

        assert pricing.PRICING_CURRENCY == PRICING_DEFAULT_CURRENCY
        assert _default_policy()["currency"] == PRICING_DEFAULT_CURRENCY
        assert f'"currency": "{PRICING_DEFAULT_CURRENCY}"' in render_default_pricing_ref()

    def test_entries_without_currency_fall_back_to_default(self):
        assert model_currency("deepseek-flash") == pricing.PRICING_CURRENCY


class TestCostBuckets:
    """多币种金额桶：分组并存、格式化并列、空桶为短横线。"""

    def test_buckets_are_not_summed_across_currencies(self):
        buckets: dict[str, float] = {}
        add_cost(buckets, "CNY", 0.02)
        add_cost(buckets, "USD", 0.005)
        add_cost(buckets, "CNY", 0.03)
        assert buckets == pytest.approx({"CNY": 0.05, "USD": 0.005})

    def test_merge_keeps_currencies_separate(self):
        merged = merge_costs({"CNY": 0.1}, {"USD": 0.2}, {"CNY": 0.3})
        assert merged == pytest.approx({"CNY": 0.4, "USD": 0.2})

    def test_format_joins_sorted_currencies(self):
        assert format_costs({"USD": 0.0045, "CNY": 0.0123}) == "¥0.0123 + $0.0045"

    def test_format_empty_buckets(self):
        assert format_costs({}) == "-"
        assert format_costs({"CNY": 0.0}) == "-"


class TestBudgetConversion:
    """预算判定允许内部汇率折算，但折算只影响判定。"""

    def test_convert_amount_uses_internal_table(self):
        assert convert_amount(1.0, "USD", "CNY") == pytest.approx(pricing.FX_TO_CNY["USD"])
        assert convert_amount(1.0, "CNY", "CNY") == pytest.approx(1.0)

    def test_unknown_currency_returns_none(self):
        assert convert_amount(1.0, "XYZ", "CNY") is None

    def test_budget_compares_across_currencies_without_touching_display(self):
        from src.python.llm.cost_forecast import budget_status

        today = date.today().isoformat()
        history = [{"timestamp": today, "llm": {"cost_by_currency": {"USD": 0.2}}}]
        status = budget_status({"daily_cost_limit": 2.0}, history)

        # 判定：$0.2 折算后仍低于 ¥2.0 → 未超限
        assert status["exceeded"] is False
        # 展示：原生桶保持美元，不被折成人民币
        assert status["spent"] == pytest.approx({"USD": 0.2})
        assert "$0.2000" in status["display"]

    def test_budget_exceeded_after_conversion(self):
        """上限是本币单值：外币支出折算后超限即触发（判定用汇率，展示仍原生）。"""
        from src.python.llm.cost_forecast import budget_status

        today = date.today().isoformat()
        history = [{"timestamp": today, "llm": {"cost_by_currency": {"USD": 2.0}}}]
        status = budget_status({"daily_cost_limit": 1.0}, history)
        assert status["exceeded"] is True
        assert status["currency"] == pricing.PRICING_CURRENCY
        assert status["spent"] == pytest.approx({"USD": 2.0})

    def test_unconvertible_currency_is_surfaced(self):
        """缺内部汇率的币种不得静默按 0 计：列入 unconvertible 并在摘要里点名。"""
        from src.python.llm.cost_forecast import budget_status

        today = date.today().isoformat()
        history = [{"timestamp": today, "llm": {"cost_by_currency": {"XYZ": 9.0}}}]
        status = budget_status({"daily_cost_limit": 1.0}, history)
        assert status["unconvertible"] == ["XYZ"]
        assert "无法折算" in status["display"]
