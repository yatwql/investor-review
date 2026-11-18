"""账本级共用原语（`core/ledger_common.py`）——开关判定与时间戳口径的唯一实现。

两个账本各留同名薄封装（`is_active` / `_now_iso`），原语本体在此。用例锁：
  - 开关判定确实经 `config.features.is_feature_enabled` 收敛（不是各自读配置）；
  - 时间戳为**秒级** ISO（无微秒）——账本按日期折叠，微秒精度只会让同批记录看起来不同源；
  - 两个账本的薄封装与原语同口径（改口径只动一处）。
"""

from __future__ import annotations

import re

import pytest

from src.python.core.ledger_common import feature_active, now_iso

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

#: 秒级 ISO8601（本地时间，允许 ±HH:MM 偏移）
_ISO_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:\d{2})?$")


class TestFeatureActive:
    def test_delegates_to_feature_registry(self, monkeypatch):
        from src.python.config import features

        seen: list[str] = []

        def _enabled(flag: str) -> bool:
            seen.append(flag)
            return True

        monkeypatch.setattr(features, "is_feature_enabled", _enabled)
        assert feature_active("decision_reflection") is True
        assert seen == ["decision_reflection"]

    def test_passes_through_disabled(self, monkeypatch):
        from src.python.config import features

        monkeypatch.setattr(features, "is_feature_enabled", lambda flag: False)
        assert feature_active("deterministic_signal") is False


class TestNowIso:
    def test_seconds_precision_without_microseconds(self):
        assert _ISO_SECONDS.match(now_iso()), now_iso()

    def test_monotonic_non_decreasing(self):
        first, second = now_iso(), now_iso()
        assert second >= first


class TestLedgerWrappersShareThePrimitive:
    def test_decision_ledger_is_active_uses_shared_gate(self, monkeypatch):
        from src.python.core import decision_ledger, ledger_common

        monkeypatch.setattr(ledger_common, "feature_active", lambda flag: flag == decision_ledger.FEATURE_FLAG)
        assert decision_ledger.is_active() is True

    def test_signal_ledger_is_active_uses_shared_gate(self, monkeypatch):
        from src.python.core import ledger_common, signal_ledger

        monkeypatch.setattr(ledger_common, "feature_active", lambda flag: flag == signal_ledger.FEATURE_FLAG)
        assert signal_ledger.is_active() is True

    @pytest.mark.parametrize("module_name", ["decision_ledger", "signal_ledger"])
    def test_now_iso_wrappers_match_primitive_format(self, module_name):
        module = __import__(f"src.python.core.{module_name}", fromlist=["_now_iso"])
        assert _ISO_SECONDS.match(module._now_iso()), module._now_iso()
