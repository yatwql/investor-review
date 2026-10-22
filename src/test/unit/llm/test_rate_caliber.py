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


class TestSchemaVersionEntersFingerprint:
    def test_version_change_changes_fingerprint(self, monkeypatch):
        base = build_llm_fingerprint(total_mv=1000, total_cost=900, total_profit=100)
        monkeypatch.setattr("src.python.llm.fingerprint.PROMPT_SCHEMA_VERSION", "another-version")
        assert build_llm_fingerprint(total_mv=1000, total_cost=900, total_profit=100) != base

    def test_fingerprint_still_12_hex(self):
        assert len(build_llm_fingerprint()) == 12
