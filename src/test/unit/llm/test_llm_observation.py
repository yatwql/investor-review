"""LLM 运行观测汇聚单元测试（llm/observation.py）。

测试目标：
  - 等待/重试/降级/缓存/选路计数累加与快照裁剪（零值不写入）
  - 线程安全：并发记录不丢更新
  - 绑定生命周期：bind/current/clear，未绑定时调用方跳过记录

运行：
  pytest src/test/unit/llm/test_llm_observation.py -v
"""

from __future__ import annotations

import threading

import pytest

from src.python.llm.observation import (
    LlmObservation,
    bind_llm_observation,
    clear_llm_observation,
    current_llm_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


class TestLlmObservation:
    """汇聚器：累加、快照裁剪、并发安全。"""

    def test_retry_and_wait_accumulate(self):
        sink = LlmObservation()
        sink.note_retry(1.0)
        sink.note_retry(3.0)
        snap = sink.snapshot()
        assert snap["retry_count"] == 2
        assert snap["retry_wait_seconds"] == pytest.approx(4.0)

    def test_pacing_wait_accumulates(self):
        sink = LlmObservation()
        sink.note_pacing_wait(0.5)
        sink.note_pacing_wait(1.5)
        assert sink.snapshot()["pacing_wait_seconds"] == pytest.approx(2.0)

    def test_negative_waits_ignored(self):
        sink = LlmObservation()
        sink.note_retry(-5.0)
        sink.note_pacing_wait(-1.0)
        snap = sink.snapshot()
        assert snap.get("retry_wait_seconds", 0.0) == 0.0
        assert snap.get("pacing_wait_seconds", 0.0) == 0.0

    def test_fallback_and_cache_counters(self):
        sink = LlmObservation()
        sink.note_fallback()
        sink.note_cache(True)
        sink.note_cache(True)
        sink.note_cache(False)
        snap = sink.snapshot()
        assert snap["fallbacks"] == 1
        assert snap["cache_hits"] == 2
        assert snap["cache_misses"] == 1

    def test_note_call_records_provider_model_thinking(self):
        sink = LlmObservation()
        sink.note_call(provider="deepseek-main", model="deepseek-v4-flash", thinking=True)
        sink.note_call(provider="deepseek-main", model="deepseek-v4-flash")
        snap = sink.snapshot()
        assert snap["providers"] == {"deepseek-main": 2}
        assert snap["models"] == {"deepseek-v4-flash": 2}
        assert snap["thinking_calls"] == 1

    def test_snapshot_omits_zero_valued_keys(self):
        """零值不写入：记录不因空字段膨胀。"""
        snap = LlmObservation().snapshot()
        assert "providers" not in snap
        assert "models" not in snap
        assert "retry_count" not in snap
        assert "retry_wait_seconds" not in snap

    def test_concurrent_records_do_not_lose_updates(self):
        """四模块在线程池中并发记录：计数不得丢更新。"""
        sink = LlmObservation()
        threads = [
            threading.Thread(target=lambda: [sink.note_retry(0.1) or sink.note_cache(True) for _ in range(200)])
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        snap = sink.snapshot()
        assert snap["retry_count"] == 800
        assert snap["cache_hits"] == 800


class TestBindingLifecycle:
    """绑定生命周期：未绑定时调用方跳过记录。"""

    def test_unbound_returns_none(self):
        clear_llm_observation()
        assert current_llm_observation() is None

    def test_bind_then_clear(self):
        sink = LlmObservation()
        bind_llm_observation(sink)
        try:
            assert current_llm_observation() is sink
        finally:
            clear_llm_observation()
        assert current_llm_observation() is None

    def test_bind_none_clears(self):
        bind_llm_observation(LlmObservation())
        bind_llm_observation(None)
        assert current_llm_observation() is None
