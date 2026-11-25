"""降级追踪器的状态持久化与配置读取容错测试。

覆盖契约（`core/degradation.py`）：
  - `_default_persist_path` 落在 `data/state/`（跨会话状态，不进缓存清理域）
  - `mark_provider_used` 缺参数直接返回、内部异常不外抛（观测副作用不影响取数）
  - `report_degradation_summary` 跳过缺 `source_key` 的事件
  - 持久化状态加载失败按空状态；落盘失败不推进节流时间戳
  - `record` 拒绝非法 tier（ValueError）
  - `_adjust` 在「正常过期」（ttl < 缓存年龄 ≤ 3×ttl）时维持基础阈值
  - `_get_tier_config` 对非字典配置退化为空字典，并对 ≤0 配置值告警
"""

from __future__ import annotations

from unittest import mock

import pytest

from src.python.core import degradation

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture(autouse=True)
def _clean_provider_usage():
    """用例前后清空 provider 归属登记表（模块级全局状态）。"""
    degradation.reset_provider_usage()
    yield
    degradation.reset_provider_usage()


# ── 持久化状态加载 ─────────────────────────────────────
# 注：`_default_persist_path` 在 pytest 内被测试隔离 fixture 替换为 tmp_path 版本
# （`conftest.seed_sensitive_path_isolation`），故其函数体在单元环境不可达，不在此断言。


class TestPersistPathAndLoad:
    def test_corrupt_state_file_yields_empty_state(self, tmp_path):
        """状态文件 JSON 损坏时按空状态加载（不抛异常）。"""
        persist = tmp_path / ".degradation_state.json"
        persist.write_text("{not json", encoding="utf-8")

        tracker = degradation.DegradationTracker(persist_path=str(persist))

        assert tracker._last_success == {}

    def test_write_failure_keeps_throttle_timestamp(self, tmp_path, monkeypatch):
        """原子写失败时不推进节流时间戳，下次仍会尝试落盘。"""
        tracker = degradation.DegradationTracker(persist_path=str(tmp_path / "state.json"))
        monkeypatch.setattr(degradation, "write_json_atomic", mock.Mock(return_value=False))

        tracker._persist_state(force=True)

        assert tracker._last_persist_ts == 0.0


# ── Provider 归属登记 ──────────────────────────────────


class TestMarkProviderUsed:
    def test_missing_arguments_register_nothing(self):
        """缺数据类别或 provider 标识时不登记（观测表保持空）。"""
        degradation.mark_provider_used("", "tencent")
        degradation.mark_provider_used("price_stock", "")

        assert degradation.get_provider_usage() == {}

    def test_internal_error_is_swallowed(self, monkeypatch):
        """登记表内部异常被吞掉，不打断取数主链路。"""

        class _BrokenBucket(dict):
            def setdefault(self, *_args, **_kwargs):
                raise RuntimeError("registry broken")

        monkeypatch.setattr(degradation, "_provider_usage", _BrokenBucket())

        degradation.mark_provider_used("price_stock", "tencent")

        assert degradation.get_provider_usage() == {}


# ── 降级汇总 ────────────────────────────────────────────


class TestReportDegradationSummary:
    def test_events_without_source_key_skipped(self, monkeypatch):
        """缺 source_key 的降级事件不计入汇总。"""
        tracker = mock.Mock()
        tracker.get_log.return_value = [
            {"degraded": True, "source_key": ""},
            {"degraded": True, "source_key": "industry", "failure_type": "empty"},
        ]
        monkeypatch.setattr(degradation, "get_tracker", mock.Mock(return_value=tracker))

        summary = degradation.report_degradation_summary()

        assert summary["count"] == 1
        assert summary["events"] == 1
        assert "industry" in summary["text"]


# ── record / 阈值调节 / 层级配置 ────────────────────────


class TestRecordTierValidation:
    def test_invalid_tier_raises_value_error(self, tmp_path):
        """非法 tier 直接 ValueError（配置错误须暴露，不静默降级）。"""
        tracker = degradation.DegradationTracker(persist_path=str(tmp_path / "state.json"))

        with pytest.raises(ValueError, match="无效的 tier"):
            tracker.record("industry", "T9", success=False)

    def test_normal_expiry_keeps_base_threshold(self):
        """缓存年龄介于 ttl 与 3×ttl 之间属「正常过期」，阈值不做自适应调整。"""
        assert degradation.DegradationTracker._adjust(3, 20.0, 10.0) == 3

    def test_non_dict_tier_config_falls_back_to_empty(self, tmp_path):
        """层级配置不是字典时退化为空字典，调用方按默认阈值处理。"""
        tracker = degradation.DegradationTracker(persist_path=str(tmp_path / "state.json"))
        tracker._degradation_config = {"t3": ["bad"]}

        assert tracker._get_tier_config("T3") == {}

    def test_non_positive_tier_config_is_reported(self, tmp_path, caplog):
        """≤0 的配置值记告警（会被夹紧逻辑静默限制，需让用户自查）。"""
        tracker = degradation.DegradationTracker(persist_path=str(tmp_path / "state.json"))
        tracker._degradation_config = {"t3": {"unreachable": 0}}

        with caplog.at_level("WARNING", logger=degradation.logger.name):
            result = tracker._get_tier_config("T3")

        assert result == {"unreachable": 0}
        assert any("unreachable" in record.getMessage() for record in caplog.records)
