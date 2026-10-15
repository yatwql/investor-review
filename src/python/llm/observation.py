"""LLM 运行观测汇聚 —— 把调用链上的等待/选路/用量事实汇入本次运行的 perf 记录。

设计意图（见 `docs/plan/perf-observability-design.md`）：回答「时间花在白等还是真推理」
「换 provider 或关 thinking 省多少」「缓存冷热影响多大」这类问题，需要把分散在
重试骨架（`core/retry.py` 退避）、端点节流（`llm/pacing.py` 等待）、会话用量
（`llm/session.py` 逐模块 model/tokens/cost）三处的事实，按**本次运行**归集。

归集方式：模块级 sink（`bind_llm_observation` / `current_llm_observation`），由报告
管线在运行开始时绑定、结束时取走并写入 `PerfCollector`。未绑定（如单测直调 LLM 层）
时所有记录调用为空操作，行为零变化。

线程安全：LLM 四模块在线程池中并发调用，内部以 `threading.Lock` 保护。
"""

from __future__ import annotations

import threading
from typing import Any

__all__ = [
    "LlmObservation",
    "bind_llm_observation",
    "current_llm_observation",
    "clear_llm_observation",
]

_sink_lock = threading.Lock()
_current: "LlmObservation | None" = None


class LlmObservation:
    """一次报告运行内的 LLM 观测汇聚器（线程安全）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._retry_count = 0
        self._retry_wait_seconds = 0.0
        self._pacing_wait_seconds = 0.0
        self._fallbacks = 0
        self._providers: dict[str, int] = {}
        self._models: dict[str, int] = {}
        self._thinking_calls = 0
        self._cache_hits = 0
        self._cache_misses = 0

    # ── 等待与重试 ──

    def note_retry(self, delay_seconds: float) -> None:
        """记录一次重试及其退避等待秒数（白等时间的主要来源）。"""
        with self._lock:
            self._retry_count += 1
            self._retry_wait_seconds += max(0.0, float(delay_seconds))

    def note_pacing_wait(self, seconds: float) -> None:
        """记录端点节流门的等待秒数（间隔/并发约束造成的排队）。"""
        with self._lock:
            self._pacing_wait_seconds += max(0.0, float(seconds))

    def note_fallback(self) -> None:
        """记录一次 provider 链降级（当前 provider 失败后切下一家）。"""
        with self._lock:
            self._fallbacks += 1

    # ── 选路与缓存 ──

    def note_call(self, provider: str = "", model: str = "", thinking: bool = False) -> None:
        """记录一次实际调用（provider/model/thinking 档）。"""
        with self._lock:
            if provider:
                self._providers[provider] = self._providers.get(provider, 0) + 1
            if model:
                self._models[model] = self._models.get(model, 0) + 1
            if thinking:
                self._thinking_calls += 1

    def note_cache(self, hit: bool) -> None:
        """记录一次模块级缓存命中/未命中。"""
        with self._lock:
            if hit:
                self._cache_hits += 1
            else:
                self._cache_misses += 1

    # ── 输出 ──

    def snapshot(self) -> dict[str, Any]:
        """观测快照（仅含非零项，避免记录膨胀）。"""
        with self._lock:
            data: dict[str, Any] = {
                "retry_count": self._retry_count,
                "retry_wait_seconds": round(self._retry_wait_seconds, 3),
                "pacing_wait_seconds": round(self._pacing_wait_seconds, 3),
                "fallbacks": self._fallbacks,
                "thinking_calls": self._thinking_calls,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
            }
            if self._providers:
                data["providers"] = dict(sorted(self._providers.items()))
            if self._models:
                data["models"] = dict(sorted(self._models.items()))
        return {k: v for k, v in data.items() if v not in (0, 0.0, {}, None)}


def bind_llm_observation(sink: LlmObservation | None) -> None:
    """绑定本次运行的观测汇聚器（None = 解绑）。"""
    global _current
    with _sink_lock:
        _current = sink


def current_llm_observation() -> LlmObservation | None:
    """取当前绑定的观测汇聚器（未绑定时 None，调用方据此跳过记录）。"""
    with _sink_lock:
        return _current


def clear_llm_observation() -> None:
    """解绑（运行收尾调用，避免跨运行串味）。"""
    bind_llm_observation(None)
