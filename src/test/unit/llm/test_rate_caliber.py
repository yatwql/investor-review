"""收益率口径标签与「提示词文本版本进指纹」单元测试。

判定口径：
- 所有标签都含「收益率」，避免模型无法把百分比归入口径；
- 口径说明必须点明三种口径**不可混用**（这是本次修正的动机）；
- 静态文案改动不进结构化指纹 ⇒ 必须由 `PROMPT_SCHEMA_VERSION` 换键，否则复用旧口径结论。
"""

from __future__ import annotations

import pytest

from src.python.llm import rate_caliber as rc
from src.python.llm.fingerprint import build_llm_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestLabels:
    def test_all_labels_contain_rate_word(self):
        for name in ("LABEL_POSITION", "LABEL_POSITION_SHORT", "LABEL_PORTFOLIO", "LABEL_INTERVAL"):
            value = getattr(rc, name)
            assert value and "收益率" in value, f"{name} 缺失「收益率」字样: {value!r}"

    def test_caliber_note_distinguishes_three_calibers(self):
        note = rc.CALIBER_NOTE
        for caliber in ("持仓收益率", "区间收益率", "累计收益率"):
            assert caliber in note
        assert "不可" in note or "不得" in note  # 明确禁止混用

    def test_schema_version_is_declared(self):
        assert isinstance(rc.PROMPT_SCHEMA_VERSION, str) and rc.PROMPT_SCHEMA_VERSION


class TestMoneySignNote:
    """金额列符号口径：绝对值 + 方向由操作列承担（禁正负号充当买卖方向）。

    回归背景：模型自拟「金额」列时用现金流口径（减仓回款写 +7600、加仓支出写 -22000），
    读者按「交易金额」读就觉得符号反了；机械建议表（`rebalance_advisor`）一直是绝对值，
    两处口径不一致。
    """

    def test_note_requires_absolute_value(self):
        assert "绝对值" in rc.MONEY_SIGN_NOTE
        assert "不得用正负号" in rc.MONEY_SIGN_NOTE

    def test_both_action_prompts_carry_note(self):
        from src.python.llm.prompts_action import _build_expert_review_prompt, _build_health_check_prompt

        details = [
            {
                "name": "长江电力",
                "code": "600900",
                "market_value": 10000.0,
                "cost": 9000.0,
                "profit": 1000.0,
                "profit_rate": 11.11,
                "shares": 100,
                "price": 100.0,
                "channel": "场内",
            }
        ]
        kwargs = dict(
            total_mv=250000.0,
            total_cost=205000.0,
            total_profit=45000.0,
            total_today_profit=1000.0,
            holdings_count=1,
            categories={"股票": 1},
            penetrated_assets=None,
            holdings_details=details,
        )
        assert rc.MONEY_SIGN_NOTE in _build_expert_review_prompt(**kwargs)
        assert rc.MONEY_SIGN_NOTE in _build_health_check_prompt(**kwargs)


class TestSchemaVersionEntersFingerprint:
    def test_version_change_changes_fingerprint(self, monkeypatch):
        base = build_llm_fingerprint(holdings_details=[{"name": "A", "code": "000001", "cost": 100}])
        monkeypatch.setattr("src.python.llm.fingerprint.PROMPT_SCHEMA_VERSION", "another-version")
        assert build_llm_fingerprint(holdings_details=[{"name": "A", "code": "000001", "cost": 100}]) != base

    def test_fingerprint_still_12_hex(self):
        assert len(build_llm_fingerprint()) == 12
