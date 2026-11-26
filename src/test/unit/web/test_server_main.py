"""Web 服务主入口 `server.main()` 的启动硬闸与锁释放时序。

覆盖点：
  - 解释器预检失败 → 退出码 1（缺重依赖时给可读错误，而不是跑到取数阶段才崩）
  - 端口占用 → 退出码 2
  - 局域网监听（0.0.0.0）必须留安全告警
  - 正常启动：清理残留上传 → 启动调度 → app.run；退出时**必然**释放 output_dir 写锁
  - 启动过程抛异常：写锁同样释放（finally 语义），异常继续上抛
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from src.python.web import server

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


def _patch_runtime(monkeypatch, *, release_sink: list[str]) -> dict[str, object]:
    """把 main() 触及的外部依赖全部换成记录桩，返回调用记录。"""
    calls: dict[str, object] = {"order": []}

    class _Scheduler:
        def __init__(self, run_manager) -> None:
            calls["scheduler_with"] = run_manager

        def start(self) -> None:
            calls["order"].append("scheduler.start")

    app = SimpleNamespace(run=lambda **kwargs: calls["order"].append(("app.run", kwargs)))

    monkeypatch.setattr("src.python.core.logger.setup_logger", lambda: None)
    monkeypatch.setattr("src.python.core.logger.log_app_boundary", lambda *a, **k: None)
    monkeypatch.setattr("src.python.core.doctor.interpreter_preflight_error", lambda: None)
    monkeypatch.setattr("src.python.config.init_config", lambda config_path=None: calls.update(config_path=config_path))
    monkeypatch.setattr(server, "resolve_output_dir", lambda: "/tmp/out")
    monkeypatch.setattr(server, "ensure_output_dir_lock", lambda _d: calls.setdefault("lock", None))
    monkeypatch.setattr(server, "_release_output_dir_lock", lambda p: release_sink.append(p))
    monkeypatch.setattr(server, "_port_in_use", lambda host, port: False)
    monkeypatch.setattr("src.python.web.app.create_app", lambda rm: app)
    monkeypatch.setattr("src.python.web.runs.get_run_manager", lambda: "run-manager")
    monkeypatch.setattr("src.python.web.upload.cleanup_all", lambda: calls["order"].append("cleanup_all"))
    monkeypatch.setattr("src.python.web.scheduler.SchedulerService", _Scheduler)
    return calls


class TestMainGates:
    def test_preflight_error_exits_1(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        monkeypatch.setattr("src.python.core.logger.setup_logger", lambda: None)
        monkeypatch.setattr("src.python.core.logger.log_app_boundary", lambda *a, **k: None)
        monkeypatch.setattr("src.python.core.doctor.interpreter_preflight_error", lambda: "缺 pandas")

        assert server.main() == 1

    def test_port_in_use_exits_2(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "--port", "8123"])
        monkeypatch.setattr("src.python.core.logger.setup_logger", lambda: None)
        monkeypatch.setattr("src.python.core.logger.log_app_boundary", lambda *a, **k: None)
        monkeypatch.setattr("src.python.core.doctor.interpreter_preflight_error", lambda: None)
        monkeypatch.setattr("src.python.config.init_config", lambda config_path=None: None)
        monkeypatch.setattr(server, "_port_in_use", lambda host, port: True)

        assert server.main() == 2

    def test_config_path_forwarded(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog", "--config", "data/config/other.json"])
        sink: list[str] = []
        calls = _patch_runtime(monkeypatch, release_sink=sink)

        assert server.main() == 0
        assert calls["config_path"] == "data/config/other.json"


class TestMainStartupAndLockRelease:
    def test_happy_path_order_and_lock_released(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        sink: list[str] = []
        calls = _patch_runtime(monkeypatch, release_sink=sink)
        monkeypatch.setattr(server, "ensure_output_dir_lock", lambda _d: "/tmp/out/.lock")

        assert server.main() == 0
        assert calls["order"] == [
            "cleanup_all",
            "scheduler.start",
            ("app.run", {"host": "127.0.0.1", "port": 8000, "threaded": True}),
        ]
        assert calls["scheduler_with"] == "run-manager"
        assert sink == ["/tmp/out/.lock"], "退出时必须释放 output_dir 写锁"

    def test_no_lock_means_release_skipped(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        sink: list[str] = []
        _patch_runtime(monkeypatch, release_sink=sink)

        assert server.main() == 0
        assert sink == []

    def test_lan_host_logs_security_warning(self, monkeypatch, caplog):
        import logging

        monkeypatch.setattr(sys, "argv", ["prog", "--host", "0.0.0.0"])
        sink: list[str] = []
        _patch_runtime(monkeypatch, release_sink=sink)

        with caplog.at_level(logging.WARNING, logger="invest"):
            server.main()

        assert any("局域网" in r.getMessage() for r in caplog.records)

    def test_exception_during_startup_still_releases_lock(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["prog"])
        sink: list[str] = []
        _patch_runtime(monkeypatch, release_sink=sink)
        monkeypatch.setattr(server, "ensure_output_dir_lock", lambda _d: "/tmp/out/.lock")
        monkeypatch.setattr("src.python.web.upload.cleanup_all", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

        with pytest.raises(RuntimeError, match="boom"):
            server.main()

        assert sink == ["/tmp/out/.lock"], "启动失败也必须释放写锁，否则下次启动被判占用"


class TestLockHelpersNearMisses:
    def test_read_lock_payload_tolerates_non_object_json(self, tmp_path):
        path = tmp_path / ".lock"
        path.write_text("[1, 2, 3]", encoding="utf-8")

        assert server._read_lock_payload(str(path)) == {}

    def test_read_lock_payload_tolerates_broken_json(self, tmp_path):
        path = tmp_path / ".lock"
        path.write_text("{not json", encoding="utf-8")

        assert server._read_lock_payload(str(path)) == {}

    def test_staleness_empty_when_mtime_unreadable(self, monkeypatch):
        monkeypatch.setattr(server.os.path, "getmtime", lambda _p: (_ for _ in ()).throw(OSError("gone")))

        assert server._lock_staleness("/nonexistent/.lock") == ""

    def test_acquire_returns_none_when_dir_creation_fails(self, monkeypatch, tmp_path):
        monkeypatch.setattr(server.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(OSError("denied")))

        assert server._acquire_output_dir_lock(str(tmp_path)) is None
