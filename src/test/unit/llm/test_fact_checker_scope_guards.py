"""事实核对数值步骤的语境守卫单元测试（fact_checker/_numerical.py）。

锁住的契约：
  - 市场口径且主体定位失败 → 判为市场涨跌（宁漏改不误改），不改写正文
  - 带符号收益声称必须紧邻持仓代码且有原值文本；缺原值直接不认
  - 同句多持仓代码且无贴身主体 → 按收益率最近者归因（不按位置）
  - 无主体且与全局最近邻参考值在容差内 → 视为已核实（不产出告警）
  - 句中只有指数代码、无持仓代码且数值对不上 → 跳过（指数涨跌不属持仓收益率）
  - 非持仓语义段（贡献/归因、金融基准）与叙述性语境（仓位占比、假设情景、
    调仓目标、币种敞口）一律让位给后续步骤，不产出告警
"""

from __future__ import annotations

import pytest

from src.python.llm.fact_checker import _numerical as mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]

_HOLDINGS: dict[str, float] = {"601398": 20.0, "600900": 5.0}


def _ctx(sentence: str, value: float, *, value_str: str | None = None, **overrides) -> mod.PercentContext:
    """构造单条百分比上下文（anchor 取原值首次出现处，缺省排到句首）。"""
    kwargs: dict = {
        "value": value,
        "value_str": value_str if value_str is not None else f"{value}",
        "sentence": sentence,
        "stock_rates_abs": dict(_HOLDINGS),
        "holding_codes": set(_HOLDINGS),
        "profit_rate": 9.0,
        "profit_sign": "盈利",
        "tolerance_pct": 0.1,
        "anchor": max(0, sentence.find(f"{value}")),
    }
    kwargs.update(overrides)
    return mod.PercentContext(**kwargs)


class TestMarketScopeSubjectFailure:
    def test_subject_lookup_failure_treated_as_market_scope(self, monkeypatch):
        """市场名词在场但主体定位失败：不能拿别的持仓收益率去改写。"""
        sentence = "600900 与大盘同涨 1.18%"
        monkeypatch.setattr(mod, "_locate_subject_in", lambda *_a, **_k: None)

        assert mod._is_market_scope_no_subject(sentence, sentence.find("1.18"), set(_HOLDINGS), None) is True


class TestSignedReturnAfterCode:
    def test_missing_value_text_is_not_a_signed_return_claim(self):
        ctx = _ctx("601398（+20.0%）", 20.0, value_str="   ")

        assert mod._is_signed_return_after_code(ctx) is False


class TestSubjectAttribution:
    def test_multiple_holding_codes_attribute_to_nearest_rate(self, monkeypatch):
        """主体定位失败但句中有多代码时，按收益率最近者归因（不按出现顺序）。"""
        sentence = "601398 与 600900 分别录得 5.0%，差异明显。"
        ctx = _ctx(sentence, 5.0, stock_rates_abs={"600900": 5.0})
        attr = mod._Attribution()
        monkeypatch.setattr(mod, "_locate_subject_code", lambda *_a, **_k: None)

        mod._step_subject_rates(ctx, attr)

        assert attr.best_code == "600900", "多代码无贴身主体时按收益率最近者归因，不按出现顺序"

    def test_no_subject_within_tolerance_counts_as_verified(self):
        sentence = "组合整体持仓收益率为 9.0%。"
        ctx = _ctx(sentence, 9.0, name_to_code=None)

        assert mod._step_subject_rates(ctx, mod._Attribution()) == (None, None)

    def test_index_only_sentence_is_skipped(self):
        sentence = "000300 今日 99.0%。"
        ctx = _ctx(sentence, 99.0, stock_rates_abs={"601398": 20.0}, profit_rate=5.0, holding_codes={"601398"})

        assert mod._step_subject_rates(ctx, mod._Attribution()) == (None, None)


class TestNonHoldingScopes:
    @pytest.mark.parametrize(
        "sentence",
        ["盈利来源统计：贡献占比 12.3%。", "10 年期国债收益率 2.3%。"],
    )
    def test_contribution_and_benchmark_sentences_yield_no_issue(self, sentence):
        assert mod._step_non_holding_scopes(_ctx(sentence, 12.3), mod._Attribution()) == (None, None)

    def test_plain_return_sentence_is_not_claimed_by_this_step(self):
        sentence = "601398 的持仓收益率 20.0%。"

        assert mod._step_non_holding_scopes(_ctx(sentence, 20.0), mod._Attribution()) is None


class TestNarrativeScopes:
    @pytest.mark.parametrize(
        "sentence",
        ["最大持仓仓位 12.3%。", "假设未来上涨 12.3%。", "建议降至 12.3%。", "美元敞口 12.3%。"],
    )
    def test_narrative_contexts_yield_no_issue(self, sentence):
        assert mod._step_narrative_scopes(_ctx(sentence, 12.3), mod._Attribution()) == (None, None)

    def test_plain_return_sentence_is_not_claimed_by_this_step(self):
        sentence = "601398 的持仓收益率 20.0%。"

        assert mod._step_narrative_scopes(_ctx(sentence, 20.0), mod._Attribution()) is None
