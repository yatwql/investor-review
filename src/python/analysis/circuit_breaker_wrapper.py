"""指标级断路包装器 — 为每个风险指标计算函数包裹断路逻辑。

设计目标：
  单个指标连续失败 N 次后静默 24h，不阻塞其他指标计算，
  避免一次波动性失败污染全管线。

与 provider_registry 的边界：
  provider_registry（传输层熔断）：
    管 HTTP 层面的快速跳过（超时/断连/5xx），per-provider 粒度。
  IndicatorBreaker（指标层断路）：
    管指标计算层面的异常（除零/空数据/置信度不足），per-indicator 粒度。
    不关心底层是哪个数据源——只关心指标算不算得出来。

与功能开关的关系：
  断路只看指标自身的连续失败次数——指标始终计算、始终计数。
  量化指标展示不再提供关闭开关（显示开关曾与失败计数联动，属跨层副作用，已移除）。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable

from src.python.core.atomic_write import write_json_atomic
from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

__all__ = [
    "IndicatorBreaker",
    "get_indicator_breaker",
    "reset_indicator_breaker",
]

# ── 常量 ────────────────────────────────────────────────

_METRICS_BREAKER_FILE = os.path.join(PROJECT_ROOT, "data/state/metrics_breaker.json")
"""指标断路状态持久化文件路径（data/state/ 运行时状态目录，不随缓存清理）。"""

_DEFAULT_MAX_FAILURES = 3
"""单个指标连续失败多少次后触发断路。"""

_DEFAULT_COOLDOWN_SECS = 86400
"""断路后冷却时间（秒，默认 24h）。"""

_CIRCUIT_BREAKER_TTL = 86400 * 7
"""持久化记录的超时 TTL（秒，默认 7 天），超过此时间的条目在加载时自动清理。"""


class IndicatorBreaker:
    """指标级断路器 — 为单个指标计算函数提供断路保护。

    用法：
        breaker = IndicatorBreaker()
        result = breaker.guard("sharpe_ratio", compute_fn, *args, **kwargs)

    或者显式调用：
        if breaker.is_broken("sharpe_ratio"):
            return None
        try:
            result = compute_fn(...)
            breaker.record_success("sharpe_ratio")
            return result
        except Exception:
            breaker.record_failure("sharpe_ratio")
            return None
    """

    def __init__(self, persist_path: str | None = None) -> None:
        self._persist_path = persist_path or _METRICS_BREAKER_FILE
        # {indicator_name: {"consecutive_failures": int, "broken_until": float, ...}}
        self._state: dict[str, dict[str, Any]] = {}
        self._load_state()

    # ── 持久化 ──────────────────────────────────────

    def _state_path(self) -> str:
        return self._persist_path

    def _load_state(self) -> None:
        """从 JSON 加载持久化的断路状态，超过 TTL 的条目自动清理。"""
        path = self._state_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.debug("[breaker] 状态文件损坏，跳过加载")
            return

        now = time.time()
        loaded = 0
        expired = 0
        for name, st in data.items():
            saved_at = st.get("_saved_at", 0)
            if now - saved_at > _CIRCUIT_BREAKER_TTL:
                expired += 1
                continue
            self._state[name] = st
            loaded += 1
        if loaded:
            logger.debug("[breaker] 已加载 %d 个指标断路状态（%d 条已过期）", loaded, expired)

    def _save_state(self) -> None:
        """持久化当前断路状态到 JSON。"""
        path = self._state_path()
        now = time.time()
        # 清理过期条目，并添加时间戳
        clean: dict[str, dict[str, Any]] = {}
        for name, st in self._state.items():
            saved_at = st.get("_saved_at", 0)
            if now - saved_at > _CIRCUIT_BREAKER_TTL:
                continue
            st["_saved_at"] = now
            clean[name] = st
        self._state = clean
        # 原子写：半写的状态文件会让下次启动读不出断路记录（断路器"失忆"，
        # 已熔断的指标被立即重试）
        write_json_atomic(path, clean, log_tag="breaker", noun="断路状态")

    # ── 断路判定 ────────────────────────────────────

    def is_broken(self, indicator_name: str) -> bool:
        """检查指定指标是否处于断路状态。

        冷却期满时自动解除断路（返回 False 并允许一次试探）。
        """
        st = self._state.get(indicator_name)
        if st is None:
            return False
        broken_until = st.get("broken_until", 0)
        if time.time() >= broken_until:
            # 冷却期满 → 解除断路
            if st.get("is_broken", False):
                logger.info("[breaker] %s 冷却期满，解除断路", indicator_name)
            self._state.pop(indicator_name, None)
            self._save_state()
            return False
        return st.get("is_broken", False)

    # ── 记录成功/失败 ────────────────────────────────

    def record_success(self, indicator_name: str) -> None:
        """记录一次指标计算成功，重置该指标的所有计数。"""
        old = self._state.pop(indicator_name, None)
        if old is not None:
            logger.debug("[breaker] %s 计算成功，重置断路状态", indicator_name)
            self._save_state()

    def record_failure(self, indicator_name: str, context: str = "") -> None:
        """记录一次指标计算失败，达到阈值时触发断路（指标失败始终计数）。"""
        st = self._state.setdefault(
            indicator_name,
            {
                "consecutive_failures": 0,
                "is_broken": False,
                "broken_until": 0,
                "last_context": "",
                "_saved_at": time.time(),
            },
        )

        st["consecutive_failures"] = st.get("consecutive_failures", 0) + 1
        st["last_context"] = context

        if st["consecutive_failures"] >= _DEFAULT_MAX_FAILURES and not st.get("is_broken", False):
            st["is_broken"] = True
            st["broken_until"] = time.time() + _DEFAULT_COOLDOWN_SECS
            logger.warning(
                "[breaker] %s 连续 %d 次失败（最新: %s），断路 %ds（~24h）",
                indicator_name,
                st["consecutive_failures"],
                context or "未知错误",
                _DEFAULT_COOLDOWN_SECS,
            )
            # 记录到 DegradationTracker
            try:
                from src.python.report.data_status import get_tracker

                tracker = get_tracker()
                tracker.record(
                    source_key=f"breaker_{indicator_name}",
                    tier="T2",
                    success=False,
                    failure_type="unreachable",
                )
            except Exception:
                logger.debug("[breaker] DegradationTracker 不可用，跳过失败记录", exc_info=True)

        self._save_state()

    def get_breaker_status(self, indicator_name: str) -> dict[str, Any]:
        """查询指定指标的断路状态。"""
        st = self._state.get(indicator_name, {})
        is_broken = self.is_broken(indicator_name)
        if not is_broken:
            return {"indicator": indicator_name, "circuit_broken": False, "consecutive_failures": 0}
        return {
            "indicator": indicator_name,
            "circuit_broken": True,
            "consecutive_failures": st.get("consecutive_failures", 0),
            "cooldown_remaining": round(max(0, st.get("broken_until", 0) - time.time()), 1),
            "last_context": st.get("last_context", ""),
        }

    def summary(self) -> dict[str, dict[str, Any]]:
        """返回所有指标的断路状态摘要。"""
        result: dict[str, dict[str, Any]] = {}
        for name in list(self._state.keys()):
            result[name] = self.get_breaker_status(name)
        return result

    def guard(
        self,
        indicator_name: str,
        compute_fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """包裹执行：先查断路 → 执行 → 记录结果。

        Args:
            indicator_name: 指标名称（用于断路状态跟踪）
            compute_fn: 指标计算函数
            *args, **kwargs: 传给 compute_fn 的参数

        Returns:
            compute_fn 的返回值，或 None（断路/异常）
        """
        # 1. 检查断路状态
        if self.is_broken(indicator_name):
            logger.debug("[breaker] %s 断路中，跳过计算", indicator_name)
            return None

        # 3. 执行计算
        try:
            result = compute_fn(*args, **kwargs)
            self.record_success(indicator_name)
            return result
        except Exception as e:
            context = f"{type(e).__name__}: {e}"
            self.record_failure(indicator_name, context)
            return None

    def reset(self) -> None:
        """清空全部断路状态（测试用）。"""
        self._state.clear()
        if os.path.exists(self._state_path()):
            try:
                os.remove(self._state_path())
            except OSError:
                pass


# ── 单例工厂 ────────────────────────────────────────────

_breaker_instance: IndicatorBreaker | None = None
_breaker_instance_lock = __import__("threading").Lock()


def get_indicator_breaker() -> IndicatorBreaker:
    """获取全局单例。"""
    global _breaker_instance
    if _breaker_instance is None:
        with _breaker_instance_lock:
            if _breaker_instance is None:
                _breaker_instance = IndicatorBreaker()
    return _breaker_instance


def reset_indicator_breaker() -> None:
    """重置单例（测试用）。"""
    global _breaker_instance
    with _breaker_instance_lock:
        if _breaker_instance is not None:
            _breaker_instance.reset()
        _breaker_instance = None


def _register_to_core_gateway() -> None:
    """把指标断路器实例注册进 core 网关（模块导入时执行一次，core 不反向 import 上层）。"""
    from src.python.core.circuit_breaker import register_breaker_status

    register_breaker_status("indicator", get_indicator_breaker)


_register_to_core_gateway()
