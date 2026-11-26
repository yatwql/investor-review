"""report/_debate_utils.py 的标签提取与开关降级分支。

锁住的契约：
  - ``debate_info`` 自带的 ``mode_label`` / ``mode_combination`` 原样返回（LLM 缓存命中优先）；
  - 缺标签时按 feature flag 回退：``llm_debate_procon`` → 「辩论模式」+「正反辩论」。
"""

from __future__ import annotations

import pytest

from src.python.report import _debate_utils as du

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _stub_flags(monkeypatch: pytest.MonkeyPatch, enabled: set[str]) -> None:
    """把 ``is_feature_enabled`` 换成本次开关集合的查表（生产侧为函数内导入）。"""
    from src.python.config import features

    monkeypatch.setattr(features, "is_feature_enabled", lambda name: name in enabled)


def test_debate_info_labels_are_used_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_flags(monkeypatch, set())
    label, combination = du.detect_debate_mode({"mode_label": "缓存标签", "mode_combination": "缓存组合"})
    assert (label, combination) == ("缓存标签", "缓存组合")


def test_procon_feature_falls_back_to_label_and_combination(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_flags(monkeypatch, {"llm_debate_procon"})
    label, combination = du.detect_debate_mode()
    assert label == "辩论模式"
    assert combination == "正反辩论"
