"""Web 启动防护的进程/端口/锁探测分支单元测试（web/server.py）。

锁住的契约：
  - Windows 上 pid 存活判定走 `OpenProcess` 句柄（成功即关句柄再报存活；
    打不开即判已退出），绝不用 `os.kill(pid, 0)`（该 API 在 Windows 等于系进程）
  - 非 Windows 上 `PermissionError` 视为「进程存在但属其它用户」→ 仍占用
  - 陈旧锁清理后仍抢占失败 → 返回 None（不把输出目录判为已获取）
  - 端口占用探测：能 bind 即未占用，bind 抛 OSError 即已占用
  - 模块重载时若项目根不在 `sys.path`，自动补入（支持直接执行本文件）
"""

from __future__ import annotations

import importlib.util
import socket
import sys
from types import SimpleNamespace

import pytest

from src.python.web import server

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


class _FakeKernel32:
    """最小 kernel32 替身：只关心 OpenProcess/CloseHandle 的句柄语义。"""

    def __init__(self, handle: int) -> None:
        self._handle = handle
        self.closed: list[int] = []

    def OpenProcess(self, _access: int, _inherit: bool, _pid: int) -> int:
        return self._handle

    def CloseHandle(self, handle: int) -> None:
        self.closed.append(handle)


def _install_fake_ctypes(monkeypatch, kernel32: _FakeKernel32) -> None:
    module = SimpleNamespace(windll=SimpleNamespace(kernel32=kernel32))
    monkeypatch.setitem(sys.modules, "ctypes", module)


class TestPidAlive:
    def test_windows_handle_missing_reports_dead(self, monkeypatch):
        monkeypatch.setattr(server, "os", SimpleNamespace(name="nt"))
        _install_fake_ctypes(monkeypatch, _FakeKernel32(0))

        assert server._pid_alive(4321) is False

    def test_windows_openable_handle_closed_and_reported_alive(self, monkeypatch):
        monkeypatch.setattr(server, "os", SimpleNamespace(name="nt"))
        kernel32 = _FakeKernel32(42)
        _install_fake_ctypes(monkeypatch, kernel32)

        assert server._pid_alive(4321) is True
        assert kernel32.closed == [42], "探测后必须关句柄，不能泄漏"

    def test_permission_denied_treated_as_alive(self, monkeypatch):
        def _deny(_pid: int, _sig: int) -> None:
            raise PermissionError("属其它用户")

        monkeypatch.setattr(server.os, "kill", _deny)

        assert server._pid_alive(4321) is True


class TestStaleLockRecovery:
    def test_returns_none_when_stale_lock_cannot_be_reacquired(self, tmp_path, monkeypatch):
        lock_path = server._output_dir_lock_path(str(tmp_path))
        with open(lock_path, "w", encoding="utf-8") as handle:
            handle.write("{}")

        def _raise(*_a, **_k):
            raise OSError("打不开")

        monkeypatch.setattr(server, "_lock_staleness", lambda _path: "陈旧锁")
        monkeypatch.setattr(server.os, "open", _raise)

        assert server._acquire_output_dir_lock(str(tmp_path)) is None


class TestPortInUse:
    def test_free_port_reported_unused(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        assert server._port_in_use("127.0.0.1", port) is False

    def test_bound_port_reported_in_use(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]

            assert server._port_in_use("127.0.0.1", port) is True


class TestProjectRootOnSysPath:
    def test_fresh_module_load_reinserts_project_root(self, monkeypatch):
        """项目根不在 sys.path 时，模块导入期自行补入（直接执行本文件的情形）。"""
        root = server._project_root
        monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != root])

        probe_name = "_server_project_root_probe"
        spec = importlib.util.spec_from_file_location(probe_name, server.__file__)
        assert spec is not None and spec.loader is not None
        probe = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(probe)

            assert probe._project_root == root
            assert root in sys.path, "直接执行本文件（项目根不在 sys.path）时须自动补入"
        finally:
            sys.modules.pop(probe_name, None)
            while root in sys.path:
                sys.path.remove(root)
