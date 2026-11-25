"""持仓变更检测的关联缓存刷新分支测试。

覆盖契约（`cache/services/holdings_tracker.py`）：
  - `_clear_holdings_related_caches` 只在对应缓存存在时列入清除清单，
    一项都没有时记「无需清除」并返回空列表
  - `check_and_refresh_caches` 指纹相同时不清缓存、不改跟踪数据，直接返回空列表
  - 上一轮跟踪数据缺 `codes` 字段时按「全部代码为新增」处理（宁多刷不漏刷）
"""

from __future__ import annotations

import pytest

from src.python.cache.services import holdings_tracker

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class _MockHolding:
    """模拟持仓记录的最小结构。"""

    def __init__(self, code: str, shares: float = 100, cost_price: float = 10.0, account: str = "主账户"):
        self.code = code
        self.shares = shares
        self.cost_price = cost_price
        self.account = account


# ── 关联缓存清除 ────────────────────────────────────────


class TestClearHoldingsRelatedCaches:
    def test_existing_caches_are_reported(self, monkeypatch):
        """基准缓存存在且行业缓存有条目时，两项都进清除清单。"""
        monkeypatch.setattr(holdings_tracker, "_cache_path", lambda name: f"/tmp/cache/{name}.json")
        monkeypatch.setattr(holdings_tracker.os.path, "exists", lambda path: True)
        monkeypatch.setattr(holdings_tracker, "clear", lambda name: None)
        monkeypatch.setattr(holdings_tracker, "clear_by_prefix", lambda prefix: 3)

        cleared = holdings_tracker._clear_holdings_related_caches()

        assert cleared[0] == "fund_benchmarks"
        assert any(item.startswith("industry_(") for item in cleared)

    def test_nothing_to_clear_returns_empty(self, monkeypatch):
        """基准缓存不存在且行业缓存为空时返回空列表（不误报已清理）。"""
        monkeypatch.setattr(holdings_tracker, "_cache_path", lambda name: f"/tmp/cache/{name}.json")
        monkeypatch.setattr(holdings_tracker.os.path, "exists", lambda path: False)
        monkeypatch.setattr(holdings_tracker, "clear_by_prefix", lambda prefix: 0)

        assert holdings_tracker._clear_holdings_related_caches() == []


# ── 持仓未变 ────────────────────────────────────────────


class TestCheckAndRefreshCaches:
    def test_matching_fingerprint_skips_refresh(self, monkeypatch):
        """上一轮指纹与当前一致时不触碰关联缓存，也不重写跟踪数据。"""
        holdings = [_MockHolding("600519"), _MockHolding("000001")]
        fingerprint = holdings_tracker.compute_holdings_fingerprint(holdings)
        monkeypatch.setattr(
            holdings_tracker,
            "_read_holdings_tracking",
            lambda key: {"fingerprint": fingerprint, "codes": ["000001", "600519"]},
        )
        clear_calls: list[str] = []
        monkeypatch.setattr(holdings_tracker, "_clear_holdings_related_caches", lambda: clear_calls.append("cleared"))
        monkeypatch.setattr(holdings_tracker, "set", lambda key, value: clear_calls.append("stored"))

        assert holdings_tracker.check_and_refresh_caches(holdings) == []
        assert clear_calls == [], "指纹未变不得清缓存或重写跟踪数据"

    def test_previous_tracking_without_codes_treats_all_as_new(self, monkeypatch):
        """上一轮跟踪数据缺 codes 字段时，本轮全部代码都算新增。"""
        holdings = [_MockHolding("600519"), _MockHolding("000001")]
        monkeypatch.setattr(
            holdings_tracker,
            "_read_holdings_tracking",
            lambda key: {"fingerprint": "stale-fingerprint"},
        )
        monkeypatch.setattr(holdings_tracker, "_clear_holdings_related_caches", lambda: [])
        stored: dict = {}
        monkeypatch.setattr(holdings_tracker, "set", lambda key, value: stored.update(value))

        new_codes = holdings_tracker.check_and_refresh_caches(holdings)

        assert new_codes == ["000001", "600519"]
        assert stored["codes"] == ["000001", "600519"], "跟踪数据须更新为本轮代码集合"
