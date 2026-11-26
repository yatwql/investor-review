"""circuit_breaker_wrapper 残余分支 — 状态持久化的 TTL 清理与降级容错。

锁住的契约：
  - 构造时加载状态文件：超过 `_CIRCUIT_BREAKER_TTL` 的条目丢弃，未过期条目复原；
  - 保存时同样丢弃过期条目（内存态与文件态一致）；
  - `DegradationTracker` 不可用时只记 debug，断路本身照常生效；
  - `reset()` 删除状态文件失败（OSError）不得抛出。
"""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from src.python.analysis.circuit_breaker_wrapper import (
    _CIRCUIT_BREAKER_TTL,
    _DEFAULT_MAX_FAILURES,
    IndicatorBreaker,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


def _state_file(tmp_path, payload):
    """在临时目录写断路状态 JSON 并返回路径。"""
    path = tmp_path / "metrics_breaker.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestLoadStateTtl:
    """加载时按 TTL 清理过期条目。"""

    def test_expired_entries_dropped_on_load(self, tmp_path):
        """过期条目不入内存态，未过期条目复原。"""
        now = time.time()
        path = _state_file(
            tmp_path,
            {
                "fresh": {"consecutive_failures": 1, "is_broken": False, "_saved_at": now},
                "stale": {"consecutive_failures": 2, "is_broken": False, "_saved_at": now - _CIRCUIT_BREAKER_TTL - 1},
            },
        )
        brk = IndicatorBreaker(persist_path=path)
        assert set(brk.summary()) == {"fresh"}


class TestSaveStateTtl:
    """保存时丢弃过期条目（内存态同步收缩）。"""

    def test_expired_entries_pruned_on_save(self, tmp_path):
        """内存态里的过期条目在保存时被剔除，文件不再含该键。"""
        path = tmp_path / "metrics_breaker.json"
        brk = IndicatorBreaker(persist_path=str(path))
        brk._state["stale"] = {"consecutive_failures": 1, "is_broken": False, "_saved_at": 0}
        brk.record_failure("fresh", "boom")

        persisted = json.loads(path.read_text(encoding="utf-8"))
        assert set(persisted) == {"fresh"}
        assert brk._state.get("stale") is None


class TestDegradationTrackerFault:
    """DegradationTracker 不可用不阻断断路判定。"""

    def test_breaker_still_opens_when_tracker_unavailable(self, tmp_path):
        """降级追踪器构造抛异常 → 仍按连续失败阈值断路。"""
        brk = IndicatorBreaker(persist_path=str(tmp_path / "metrics_breaker.json"))
        with patch("src.python.core.degradation.get_tracker", side_effect=RuntimeError("tracker down")):
            for _ in range(_DEFAULT_MAX_FAILURES):
                brk.record_failure("sharpe_ratio", "compute error")
        assert brk.is_broken("sharpe_ratio") is True


class TestResetRemoveFault:
    """`reset()` 删除状态文件失败不得抛出。"""

    def test_reset_swallows_oserror(self, tmp_path):
        """os.remove 抛 OSError → 状态仍清空且不抛异常。"""
        path = tmp_path / "metrics_breaker.json"
        path.write_text("{}", encoding="utf-8")
        brk = IndicatorBreaker(persist_path=str(path))
        brk.record_failure("indicator_a", "err")

        with patch("src.python.analysis.circuit_breaker_wrapper.os") as mock_os:
            mock_os.path.exists.return_value = True
            mock_os.remove.side_effect = OSError("permission denied")
            brk.reset()

        mock_os.remove.assert_called_once_with(str(path))
        assert brk.summary() == {}
