"""历史增量链路的失败/降级分支单元测试。

覆盖既有重叠判定用例之外的路径：
  - 重叠段比较的空输入与非数值价格（跳过而非计为修正）；
  - 连续性校验抛异常时不阻断按日合并；检出修正后的全量刷新成功分支；
  - 数据跳空的告警口径；
  - provider 惰性导入失败 / 未实现函数 / 展示名解析失败三种降级；
  - 缓存清空出口。
"""

from __future__ import annotations


from unittest.mock import MagicMock

import pytest

from src.python.fetcher import chain_incremental as ci
from src.python.fetcher.chain_incremental import (
    _call_history_provider,
    _history_provider_label,
    _overlap_values_changed,
    _validate_continuity,
    clear_incremental_cache,
    fetch_with_incremental_fallback,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_fetcher,
    pytest.mark.usefixtures("offline_external_sources"),
]

_CACHE_KEY = "history_stock_600000"


def _bars(dates: list[str], close: float = 10.0) -> list[dict]:
    return [{"date": d, "open": close, "close": close, "high": close, "low": close} for d in dates]


_CACHED = _bars(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"])
_NEW = _bars(["2026-01-09", "2026-01-12"])


class TestOverlapComparisonEdges:
    """重叠段比较的否弃路径：无输入、缺行、非数值价格都按「无修正证据」处理。"""

    def test_empty_input_reports_no_change(self):
        assert _overlap_values_changed([], _NEW) is False
        assert _overlap_values_changed(_CACHED, []) is False

    def test_date_missing_on_cached_side_skipped(self):
        """新数据日期在缓存中不存在（缓存有缺口）→ 该行跳过，不误判为修正。"""
        new = _bars(["2025-12-31"]) + _bars(["2026-01-09"])

        assert _overlap_values_changed(_CACHED, new) is False

    def test_non_numeric_price_skipped(self):
        """非数值价格不参与比较：无可比数值即按「无重叠证据」处理。"""
        cached = _bars(["2026-01-05"], close="—")
        new = _bars(["2026-01-05"], close="10.0")

        assert _overlap_values_changed(cached, new) is False


class TestContinuityGapWarning:
    """新股数据与缓存之间缺失交易日超过上限即告警（部分历史不可达）。"""

    def test_gap_beyond_limit_warns(self, caplog):
        cached = _bars(["2026-01-05"])
        new = _bars(["2026-03-02"])

        with caplog.at_level("WARNING", logger="invest"):
            changed = _validate_continuity(cached, new, _CACHE_KEY)

        assert changed is False, "跳空不是修正信号，不触发全量刷新"
        assert any("数据跳空" in rec.getMessage() for rec in caplog.records)


class TestFetchFallbackDegradations:
    """取数主流程的异常降级：校验异常不阻断合并、检出修正后全量刷新成功。"""

    def test_continuity_exception_does_not_block_merge(self, monkeypatch, caplog):
        monkeypatch.setattr(ci, "cache_get", lambda key, ttl, **_kw: list(_CACHED))
        monkeypatch.setattr(ci, "cache_set", lambda key, data: None)
        monkeypatch.setattr(ci, "_read_correction_streak", lambda key: 0)
        monkeypatch.setattr(ci, "_try_providers", lambda *a, **kw: list(_NEW))

        def _boom(*_a, **_kw):
            raise RuntimeError("校验器故障")

        monkeypatch.setattr(ci, "_validate_continuity", _boom)
        ci._RUN_HISTORY_MEMO.clear()

        with caplog.at_level("WARNING", logger="invest"):
            result = fetch_with_incremental_fallback("history_stock", "600000", days=4)

        assert [r["date"] for r in result] == [r["date"] for r in (_CACHED + _NEW)[-4:]], "校验异常仍须按日合并"
        assert any("连续性校验异常" in rec.getMessage() for rec in caplog.records)

    def test_revision_triggers_successful_full_refresh(self, monkeypatch):
        """检出修正 → 清缓存后全量重取成功，直接返回全量结果。"""
        full = _bars(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"])
        cleared: list[str] = []
        monkeypatch.setattr(ci, "cache_get", lambda key, ttl, **_kw: list(_CACHED))
        monkeypatch.setattr(ci, "cache_set", lambda key, data: None)
        monkeypatch.setattr(ci, "cache_clear", cleared.append)
        monkeypatch.setattr(ci, "_validate_continuity", lambda *a: True)
        monkeypatch.setattr(ci, "_read_correction_streak", lambda key: 0)
        calls: list[str | None] = []

        def _try(*args, **kwargs):
            start_from = args[5]
            calls.append(start_from)
            return list(_NEW) if start_from else list(full)

        monkeypatch.setattr(ci, "_try_providers", _try)
        ci._RUN_HISTORY_MEMO.clear()

        result = fetch_with_incremental_fallback("history_stock", "600000", days=4)

        assert calls == ["2026-01-08", None], "修正后须清缓存并全量重取"
        assert cleared == [_CACHE_KEY]
        assert [r["date"] for r in result] == [r["date"] for r in full[-4:]]


class TestTryProvidersDiagnostics:
    """空结果与连续空跳过都要进诊断收集器（错误即 UX：失败原因不能只落日志）。"""

    @staticmethod
    def _registry():
        reg = MagicMock()
        reg.is_circuit_broken.return_value = False
        return reg

    def test_empty_result_reason_collected(self, monkeypatch):
        monkeypatch.setattr(ci, "_EMPTY_STREAK", {})
        monkeypatch.setattr(ci, "_call_history_provider", lambda *a, **kw: [])
        diagnostics = MagicMock()

        assert ci._try_providers(["fake"], self._registry(), "history_stock", "600000", 30, None, diagnostics) == []
        diagnostics.add.assert_called_once_with("fake", "返回空")

    def test_skip_after_repeated_empty_collected(self, monkeypatch, caplog):
        monkeypatch.setattr(ci, "_EMPTY_STREAK", {("history_stock", "fake"): ci._EMPTY_STREAK_SKIP})
        monkeypatch.setattr(ci, "_EMPTY_SKIP_LOGGED", set())
        fetched: list[str] = []
        monkeypatch.setattr(ci, "_call_history_provider", lambda *a, **kw: fetched.append(a[0]) or [])
        diagnostics = MagicMock()

        with caplog.at_level("WARNING", logger="invest"):
            result = ci._try_providers(["fake"], self._registry(), "history_stock", "600000", 30, None, diagnostics)

        assert result == [] and fetched == [], "连续空结果本行不再尝试（结构性不覆盖，非网络故障）"
        diagnostics.add.assert_called_once_with("fake", "连续空结果，本轮跳过")
        assert any("连续" in rec.getMessage() for rec in caplog.records)


class TestProviderCallDegradations:
    """provider 惰性导入/函数缺失/展示名解析的降级口径。"""

    def test_missing_module_warns_and_returns_empty(self, monkeypatch, caplog):
        monkeypatch.setitem(ci._HISTORY_PROVIDER_MAP, "broken", "src.python.providers.不存在的模块")

        with caplog.at_level("WARNING", logger="invest"):
            result = _call_history_provider("broken", "history_stock", "600000", 30, None)

        assert result == []
        assert any("导入" in rec.getMessage() and "失败" in rec.getMessage() for rec in caplog.records)

    def test_module_without_history_function_warns_and_returns_empty(self, monkeypatch, caplog):
        monkeypatch.setitem(ci._HISTORY_PROVIDER_MAP, "stdlib", "json")

        with caplog.at_level("WARNING", logger="invest"):
            result = _call_history_provider("stdlib", "history_fund_otc", "000001", 30, None)

        assert result == []
        assert any("无 fetch_fund_nav_history 函数" in rec.getMessage() for rec in caplog.records)

    def test_label_resolution_failure_falls_back(self, monkeypatch, caplog):
        monkeypatch.setitem(ci._HISTORY_PROVIDER_MAP, "broken", "src.python.providers.不存在的模块")

        with caplog.at_level("DEBUG", logger="invest"):
            label = _history_provider_label("broken")

        assert label == "broken", "解析失败回退到标识本身（不中断取数）"

    def test_clear_incremental_cache_uses_shared_key(self, monkeypatch):
        cleared: list[str] = []
        monkeypatch.setattr(ci, "cache_clear", cleared.append)

        clear_incremental_cache("history_fund_otc", "000001")

        assert cleared == [ci.history_cache_key("history_fund_otc", "000001")]
