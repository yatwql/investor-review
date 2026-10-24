"""test_handlers 兄弟分片（runs）：运行事件流与短缓存并发。"""

from __future__ import annotations
import threading
import time
from unittest.mock import patch
import pytest
from src.python.web.app import create_app
from src.python.web import handlers_health
from src.python.web.runs import RunManager

from src.test.unit.web.test_handlers import (
    _fake_executor,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_web, pytest.mark.usefixtures("offline_external_sources")]


@pytest.fixture()
def weak_app():
    """仅建 app（不 redirect 产物目录），供短缓存用例 test_request_context 使用。"""
    from src.python.web.runs import RunManager

    return create_app(RunManager(executor=lambda *a, **k: 0))


class TestShortCacheConcurrency:
    """/api/runs/history 与 /api/health 的两级短缓存并发与命中语义。"""

    def test_history_cache_hit_skips_reload(self, weak_app):
        """两次连续调用（5s TTL 内）→ load_history 只执行一次，返回一致载荷。"""
        from src.python.web import handlers as h

        calls: list[int] = []
        payload = [{"seq": 1}]

        def fake_load_history():
            calls.append(1)
            return payload

        with (
            patch("src.python.core.perf.load_history", fake_load_history),
            patch.dict(h._history_cache, {"ts": 0.0, "data": None}),
        ):
            with weak_app.test_request_context("/api/runs/history"):
                r1 = h._handle_run_history()
                r2 = h._handle_run_history()
            assert r1["data"] is payload and r2["data"] is payload
            assert len(calls) == 1  # 命中缓存不再读盘
            h._history_cache["ts"] = 0.0
            h._history_cache["data"] = None

    def test_history_cache_respects_ttl_expiry(self, weak_app):
        """超过 5s TTL → 重新执行 load_history。"""
        from src.python.web import handlers as h

        calls: list[int] = []
        with (
            patch("src.python.core.perf.load_history", lambda: calls.append(1) or []),
            patch.dict(h._history_cache, {"ts": 0.0, "data": []}),
        ):
            with weak_app.test_request_context("/api/runs/history"):
                h._handle_run_history()  # ts=0 → now 远大于 5s → 必 miss
            assert len(calls) == 1
            h._history_cache["ts"] = 0.0
            h._history_cache["data"] = None

    def test_health_fresh_bypasses_cache(self, weak_app):
        """?fresh=1 → 跳过缓存直接真实探测。"""
        from src.python.web import handlers as h

        probe_calls: list[int] = []

        def fake_probe(**kwargs):
            probe_calls.append(1)
            assert kwargs.get("max_timeout") == 12.0  # 预算口径不因 bypass 改变
            return [{"name": "x"}]

        with (
            patch("src.python.core.check_sources.run_health_checks", fake_probe),
            patch.dict(handlers_health._health_cache, {"ts": time.time(), "data": [{"name": "cached"}]}),
        ):
            with weak_app.test_request_context("/api/health?fresh=1"):
                rv = h._handle_health()
            assert len(probe_calls) == 1
            assert rv["data"] == [{"name": "x"}]
            handlers_health._health_cache["ts"] = 0.0
            handlers_health._health_cache["data"] = None

    def test_cache_writes_are_thread_safe(self, weak_app):
        """多线程并发写缓存 dict（盲写不崩、终态单一）。"""
        from src.python.web import handlers as h

        def worker(_idx: int) -> None:
            for _ in range(50):
                with h._render_cache_lock:
                    h._history_cache["ts"] = time.time()
                    h._history_cache["data"] = [1, 2, 3]

        with patch.dict(h._history_cache, {"ts": 0.0, "data": None}):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert h._history_cache["data"] == [1, 2, 3]
        h._history_cache["ts"] = 0.0
        h._history_cache["data"] = None


class TestRunEventsFirstSeqPayload:
    """first_seq 下发：缓冲淘汰后客户端可识别缺口（不静默跳号）。"""

    def test_events_payload_carries_first_seq_after_eviction(self, tmp_path, monkeypatch):
        """事件缓冲淘汰后，events 载荷的 first_seq 等于仍保留的最小序号。"""
        monkeypatch.setattr("src.python.web.runs._EVENT_LIMIT", 2)
        rm = RunManager(executor=_fake_executor(tmp_path))
        app = create_app(rm)
        app.config["TESTING"] = True
        client = app.test_client()
        run_id = rm.submit({"report_type": "basic"})
        # 等 worker 完成（fake executor 推 2 条事件）后再灌入超额事件，避免交错
        for _ in range(200):
            if rm.get(run_id).status in ("done", "failed"):
                break
            time.sleep(0.01)
        state = rm.get(run_id)
        for i in range(5):
            state.push_event("info", f"补录事件 {i + 1}")
        data = client.get(f"/api/runs/{run_id}/events?after=0").get_json()["data"]
        # 共 7 条事件、上限 2 → 仅保留 6/7
        assert data["first_seq"] == 6
        assert [e["seq"] for e in data["events"]] == [6, 7]
