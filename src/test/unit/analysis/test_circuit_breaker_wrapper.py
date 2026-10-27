"""IndicatorBreaker 断路器与单例工厂单元测试。"""

from __future__ import annotations

import os
import tempfile as _tf

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


class TestCircuitBreakerWrapper:
    """IndicatorBreaker 断路器和单例工厂测试。"""

    def test_get_indicator_breaker_singleton(self):
        """get_indicator_breaker() 返回同一实例。"""
        from src.python.analysis.circuit_breaker_wrapper import (
            get_indicator_breaker,
            reset_indicator_breaker,
        )

        reset_indicator_breaker()
        b1 = get_indicator_breaker()
        b2 = get_indicator_breaker()
        assert b1 is b2

    def test_reset_indicator_breaker_clear(self):
        """reset_indicator_breaker() 后获取新实例。"""
        from src.python.analysis.circuit_breaker_wrapper import (
            get_indicator_breaker,
            reset_indicator_breaker,
        )

        reset_indicator_breaker()
        b1 = get_indicator_breaker()
        b1.record_failure("test_indicator", "test error")
        reset_indicator_breaker()
        b2 = get_indicator_breaker()
        assert b2 is not b1
        assert b2.is_broken("test_indicator") is False

    def test_record_success(self):
        """record_success 重置失败计数。"""
        from src.python.analysis.circuit_breaker_wrapper import get_indicator_breaker

        with _tf.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        brk = get_indicator_breaker().__class__(persist_path=tmp_path)
        brk.record_failure("indicator_a", "err")
        brk.record_success("indicator_a")
        st = brk.get_breaker_status("indicator_a")
        assert st["circuit_broken"] is False
        assert st["consecutive_failures"] == 0
        os.unlink(tmp_path)

    def test_record_failure_triggers_breaker(self):
        """连续失败达到阈值 → 断路。"""
        from src.python.analysis.circuit_breaker_wrapper import IndicatorBreaker

        with _tf.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        brk = IndicatorBreaker(persist_path=tmp_path)
        for i in range(3):
            brk.record_failure("indicator_b", f"error_{i}")
        st = brk.get_breaker_status("indicator_b")
        assert st["circuit_broken"] is True
        assert st["consecutive_failures"] == 3
        os.unlink(tmp_path)

    def test_is_broken_after_cooldown(self):
        """冷却期满后 is_broken 自动解除。"""
        import time as _t

        from src.python.analysis.circuit_breaker_wrapper import IndicatorBreaker

        with _tf.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        brk = IndicatorBreaker(persist_path=tmp_path)
        brk.record_failure("indicator_c", "err")
        brk.record_failure("indicator_c", "err")
        brk.record_failure("indicator_c", "err")
        brk._state["indicator_c"]["broken_until"] = _t.time() - 1
        assert brk.is_broken("indicator_c") is False
        os.unlink(tmp_path)

    def test_guard_returns_fn_result(self):
        """guard 正常执行并返回结果。"""
        from src.python.analysis.circuit_breaker_wrapper import get_indicator_breaker

        with _tf.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        brk = get_indicator_breaker().__class__(persist_path=tmp_path)
        result = brk.guard("test_guard", lambda x: x + 1, 41)
        assert result == 42
        os.unlink(tmp_path)

    def test_guard_returns_none_on_exception(self):
        """guard 遇到异常 → 返回 None。"""
        from src.python.analysis.circuit_breaker_wrapper import get_indicator_breaker

        with _tf.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        brk = get_indicator_breaker().__class__(persist_path=tmp_path)
        result = brk.guard("test_ex", lambda: 1 / 0)
        assert result is None
        os.unlink(tmp_path)


class TestMetricsBreakerPersistencePath:
    """指标熔断器持久化路径（data/state/ 迁移）。"""

    def test_default_path_under_state_dir(self):
        """默认持久化路径应位于 data/state/ 而非 data/cache/。"""
        from src.python.analysis import circuit_breaker_wrapper as _cbw

        path = _cbw._METRICS_BREAKER_FILE
        # 跨平台路径规范化：Windows 分隔符为 \，统一转 / 再匹配（源码/conftest 均用 os.path/pathlib 构造）
        path_posix = path.replace(os.sep, "/")
        assert "data/state/metrics_breaker.json" in path_posix, (
            f"默认路径应指向 data/state/metrics_breaker.json，实际 {path}"
        )
        assert "data/cache" not in path_posix, f"不应再指向 data/cache，实际 {path}"


class TestIndicatorBreakerNoFeatureFlag:
    """指标断路只看自身失败计数——量化指标显示开关已内置为恒开，不再联动熔断。

    回归背景：显示开关曾并联「关闭期不计失败」「关闭即解熔」「开回清残留」三条语义，
    属跨层副作用（改报告观感却影响熔断统计）；开关移除后这些语义一并删除。
    """

    @staticmethod
    def _make_breaker(tmp_path):
        from src.python.analysis.circuit_breaker_wrapper import IndicatorBreaker

        return IndicatorBreaker(persist_path=str(tmp_path / "breaker.json"))

    def test_failures_always_count_to_break(self, tmp_path, monkeypatch):
        """无任何功能开关参与：连续失败达阈值即断路。"""
        from src.python.analysis.circuit_breaker_wrapper import _DEFAULT_MAX_FAILURES
        from src.python.config import features as feat

        monkeypatch.setattr(feat, "FEATURE_FLAGS", {})
        brk = self._make_breaker(tmp_path)
        for _ in range(_DEFAULT_MAX_FAILURES):
            brk.record_failure("sharpe_ratio", "err")

        assert brk.is_broken("sharpe_ratio") is True

    def test_guard_runs_without_any_feature_flags(self, tmp_path, monkeypatch):
        """FEATURE_FLAGS 为空时 guard 照常执行计算（不再有开关门控）。"""
        from src.python.config import features as feat

        monkeypatch.setattr(feat, "FEATURE_FLAGS", {})
        brk = self._make_breaker(tmp_path)
        calls: list[int] = []

        assert brk.guard("sharpe_ratio", lambda: calls.append(1) or 7) == 7
        assert calls == [1]

    def test_all_metric_indicators_counted(self, tmp_path):
        """原七个联动指标现在全部照常计数（逐项断言，避免漏改某一名）。"""
        from src.python.analysis.circuit_breaker_wrapper import _DEFAULT_MAX_FAILURES

        names = (
            "sharpe_ratio",
            "calmar_ratio",
            "hhi",
            "win_rate",
            "turnover_rate",
            "risk_contribution",
            "beta",
        )
        for name in names:
            brk = self._make_breaker(tmp_path / name)
            brk.persist_path = str(tmp_path / f"{name}.json")
            for _ in range(_DEFAULT_MAX_FAILURES):
                brk.record_failure(name, "err")
            assert brk.is_broken(name) is True, f"{name} 未计数"

    def test_broken_state_blocks_guard(self, tmp_path):
        """断路后 guard 返回 None（唯一跳过原因只剩断路本身）。"""
        from src.python.analysis.circuit_breaker_wrapper import _DEFAULT_MAX_FAILURES

        brk = self._make_breaker(tmp_path)
        for _ in range(_DEFAULT_MAX_FAILURES):
            brk.record_failure("beta", "err")
        calls: list[int] = []

        assert brk.guard("beta", lambda: calls.append(1) or 1) is None
        assert calls == []
