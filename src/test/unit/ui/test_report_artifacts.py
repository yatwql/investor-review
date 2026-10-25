"""报告产物收尾（`tui/report_artifacts`）单元测试。

判定口径：
- 只列**已存在**的产物（HTML 优先、Excel 次之），空清单不问、不阻塞；
- 键语义：仅 `y`/`Y` 为是，其余任何键（`n` / 回车 / Esc / 未知键）都走**默认 N**；
- Esc 只跳过（不退出程序），`Ctrl+C` 沿用 TUI 约定退出程序；
- 打开失败（无图形环境/命令缺失）不抛异常，降级为「手动访问路径」提示。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.python.core.constants import LATEST_HTML_NAME, LATEST_XLSX_NAME
from src.python.tui import report_artifacts as ra

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


@pytest.fixture(autouse=True)
def _reset_open_failure_latch(monkeypatch):
    """每次用例从「本会话未失败」开张（失败latch 是模块级会话状态）。"""
    monkeypatch.setattr(ra, "_OPEN_FAILED_IN_SESSION", False)


def _svc(tmp_path: Path, names: tuple[str, ...] = (LATEST_HTML_NAME, LATEST_XLSX_NAME)):
    for name in names:
        (tmp_path / name).write_text("x", encoding="utf-8")
    return {"output_dir": str(tmp_path)}


class TestCollectArtifacts:
    def test_collects_existing_only(self, tmp_path):
        config = _svc(tmp_path, (LATEST_HTML_NAME,))
        paths = ra.collect_artifacts(config)
        assert paths == (tmp_path / LATEST_HTML_NAME,)

    def test_empty_when_none_generated(self, tmp_path):
        assert ra.collect_artifacts({"output_dir": str(tmp_path)}) == ()

    def test_ignores_missing_output_dir_key(self):
        """配置缺 `output_dir` 时回落到 `reports`，不抛异常（路径绝对化由配置层统一负责）。"""
        assert ra.collect_artifacts({}) == () or all(p.is_file() for p in ra.collect_artifacts({}))


class TestOpenArtifacts:
    def test_returns_only_successful_opens(self, tmp_path):
        first, second = tmp_path / "a", tmp_path / "b"
        opened = ra.open_artifacts((first, second), opener=lambda p: p == second)
        assert opened == [second]

    def test_open_path_keeps_child_output_off_terminal(self, tmp_path, monkeypatch):
        """`xdg-open` 转发器的报错不得写回 TUI（逐行刷新界面会被打乱）。"""
        from src.python.core import artifacts as core_artifacts

        seen: dict = {}

        def _run(command, **kwargs):
            seen.update(command=command, **kwargs)
            return core_artifacts.subprocess.CompletedProcess(command, 3)

        monkeypatch.setattr(core_artifacts.subprocess, "run", _run)
        monkeypatch.setattr(core_artifacts.sys, "platform", "linux")
        assert core_artifacts.open_path(tmp_path) is False
        assert seen["stdout"] is core_artifacts.subprocess.DEVNULL
        assert seen["stderr"] is core_artifacts.subprocess.DEVNULL

    def test_default_opener_failure_is_swallowed(self, tmp_path, monkeypatch):
        """系统命令缺失/无图形环境 → 返回 False，不抛异常（平台分派在 core.artifacts）。"""
        from src.python.core import artifacts as core_artifacts

        def _boom(*_a, **_k):
            raise FileNotFoundError("xdg-open")

        monkeypatch.setattr(core_artifacts.subprocess, "run", _boom)
        monkeypatch.setattr(core_artifacts.sys, "platform", "linux")
        assert core_artifacts.open_path(tmp_path) is False


class TestLocalOpenSupported:
    def _linux_env(self, monkeypatch, artifacts):
        monkeypatch.delenv("SSH_CONNECTION", raising=False)
        monkeypatch.delenv("SSH_TTY", raising=False)
        monkeypatch.delenv("MOSH_CONNECTION", raising=False)
        for key in artifacts._BRIDGED_SESSION_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setattr(artifacts.sys, "platform", "linux")

    def test_bridged_remote_session_disables_local_open(self, monkeypatch):
        """手机/云桌面桥接会话（Catlink / Xpra 类）不算本机桌面：服务端 `xdg-open`
        只是转发到客户端，实测会直接报错——应直接给路径与传输指引。"""
        from src.python.core import artifacts

        self._linux_env(monkeypatch, artifacts)
        monkeypatch.setenv("DISPLAY", ":100")
        monkeypatch.setattr(artifacts, "_x11_socket_present", lambda display: True)
        monkeypatch.setattr(artifacts, "_opener_present", lambda: True)
        assert artifacts.local_open_supported() is True
        monkeypatch.setenv("CATLINK_SESSION_DIR", "/run/catlink/sessions/100")
        assert artifacts.local_open_supported() is False

    def test_remote_ssh_disables_local_open(self, monkeypatch):
        from src.python.core import artifacts

        self._linux_env(monkeypatch, artifacts)
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setattr(artifacts, "_x11_socket_present", lambda display: True)
        monkeypatch.setattr(artifacts, "_opener_present", lambda: True)
        assert artifacts.local_open_supported() is True
        monkeypatch.setenv("SSH_CONNECTION", "1.2.3.4 1 5.6.7.8 22")
        assert artifacts.local_open_supported() is False

    def test_linux_without_display_disables_local_open(self, monkeypatch):
        from src.python.core import artifacts

        self._linux_env(monkeypatch, artifacts)
        monkeypatch.delenv("DISPLAY", raising=False)
        assert artifacts.local_open_supported() is False

    def test_stale_display_without_x_socket_disables_local_open(self, monkeypatch):
        """残留 `DISPLAY`（tmux/screen 继承的旧桌面环境）不算可开：手机远端场景下
        只凭环境变量会去跑 xdg-open 然后失败，用户看到「打开失败」后跳回主菜单。"""
        from src.python.core import artifacts

        self._linux_env(monkeypatch, artifacts)
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setattr(artifacts, "_x11_socket_present", lambda display: False)
        monkeypatch.setattr(artifacts, "_opener_present", lambda: True)
        assert artifacts.local_open_supported() is False

    def test_missing_xdg_open_disables_local_open(self, monkeypatch):
        """有桌面但没 xdg-open 时同样不问（问了必然失败）。"""
        from src.python.core import artifacts

        self._linux_env(monkeypatch, artifacts)
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setattr(artifacts, "_x11_socket_present", lambda display: True)
        monkeypatch.setattr(artifacts, "_opener_present", lambda: False)
        assert artifacts.local_open_supported() is False

    def test_x11_socket_probe_reads_display_number(self, monkeypatch, tmp_path):
        """socket 探测按 `:N` 取编号；远端 X（host:N）由客户端承载不查本地。"""
        from src.python.core import artifacts

        monkeypatch.setattr(artifacts.Path, "exists", lambda self: str(self).endswith("X7"))
        assert artifacts._x11_socket_present(":7") is True
        assert artifacts._x11_socket_present(":0") is False
        assert artifacts._x11_socket_present("localhost:7") is True
        assert artifacts._x11_socket_present("nonsense") is False


class TestPromptOpenArtifacts:
    def _run(self, tmp_path, key, *, opener_ok=True, tty=True, supported=True):
        config = _svc(tmp_path)
        artifacts = ra.collect_artifacts(config)
        lines: list[str] = []
        calls: list[Path] = []

        def _opener(path):
            calls.append(path)
            return opener_ok

        with patch.object(ra.sys.stdin, "isatty", lambda: tty):
            result = ra.prompt_open_artifacts(
                artifacts,
                key_reader=lambda: key,
                opener=_opener,
                echo=lines.append,
                open_supported=lambda: supported,
            )
        return result, calls, lines

    @pytest.mark.parametrize("key", ["Y", "y"])
    def test_yes_opens_directory_then_files(self, tmp_path, key):
        result, calls, lines = self._run(tmp_path, key)
        assert result == "opened"
        assert calls[0] == tmp_path  # 先目录、后产物
        assert len(calls) == 3
        assert any("[OK] 已打开" in line for line in lines)

    @pytest.mark.parametrize("key", ["N", "n", "KEY_ENTER", "KEY_ESC", "KEY_UNKNOWN"])
    def test_other_keys_take_default_no(self, tmp_path, key):
        """除 y/Y 外任何键都等于默认 N（含 Esc：只跳过、不退出程序）。"""
        result, calls, lines = self._run(tmp_path, key)
        assert result == "skipped"
        assert calls == []
        assert any("未打开" in line for line in lines)

    def test_ctrl_c_exits_program(self, tmp_path):
        """Ctrl+C 沿用 TUI 既有约定（退出程序），不与 Esc 混为一谈。"""
        config = _svc(tmp_path)
        artifacts = ra.collect_artifacts(config)
        with (
            patch.object(ra.sys.stdin, "isatty", lambda: True),
            patch("src.python.tui.tui_menu.exit_app") as mock_exit,
        ):
            ra.prompt_open_artifacts(
                artifacts, key_reader=lambda: "KEY_CTRL_C", opener=lambda p: True, open_supported=lambda: True
            )
        mock_exit.assert_called_once()

    def test_open_failure_reports_manual_path(self, tmp_path):
        result, calls, lines = self._run(tmp_path, "y", opener_ok=False)
        assert result == "failed"
        assert any("打开失败" in line for line in lines)
        assert any("scp/sftp" in line for line in lines)

    def test_open_failure_latches_for_session(self, tmp_path):
        """一次打开失败后本会话不再询问（手机远端反复跑报告时不重复撞壁）。"""
        first, _, _ = self._run(tmp_path, "y", opener_ok=False)
        assert first == "failed"
        asked = {"n": 0}
        lines: list[str] = []

        def _reader():
            asked["n"] += 1
            return "y"

        second = ra.prompt_open_artifacts(
            ra.collect_artifacts(_svc(tmp_path)),
            key_reader=_reader,
            opener=lambda p: True,
            echo=lines.append,
            open_supported=lambda: True,
        )
        assert second == "unsupported" and asked["n"] == 0
        assert any("scp/sftp" in line for line in lines)

    def test_non_tty_skips_asking(self, tmp_path):
        """非 TTY（脚本/管道）只打印清单、不问，避免阻塞。"""
        config = _svc(tmp_path)
        artifacts = ra.collect_artifacts(config)
        asked = {"n": 0}
        lines: list[str] = []

        def _reader():
            asked["n"] += 1
            return "y"

        with patch.object(ra.sys.stdin, "isatty", lambda: False):
            result = ra.prompt_open_artifacts(
                artifacts, key_reader=_reader, opener=lambda p: True, echo=lines.append, open_supported=lambda: True
            )
        assert result == "skipped" and asked["n"] == 0
        assert any("产物文件" in line for line in lines)

    def test_remote_or_headless_skips_open_with_guidance(self, tmp_path):
        """远程/无图形会话无法在客户端打开服务器文件管理器，应展示路径指引。"""
        config = _svc(tmp_path)
        artifacts = ra.collect_artifacts(config)
        asked = {"n": 0}
        calls: list[Path] = []
        lines: list[str] = []

        def _reader():
            asked["n"] += 1
            return "y"

        result = ra.prompt_open_artifacts(
            artifacts,
            key_reader=_reader,
            opener=lambda p: calls.append(p) or True,
            echo=lines.append,
            open_supported=lambda: False,
        )
        assert result == "unsupported"
        assert asked["n"] == 0
        assert calls == []
        assert any("远程/无图形" in line for line in lines)
        assert any("scp/sftp" in line for line in lines)

    def test_remote_session_gates_before_returning_to_menu(self, tmp_path):
        """远程/无图形会话没有 y/N 询问，须先停屏再回菜单——否则产物路径被随后重绘顶出。"""
        config = _svc(tmp_path)
        artifacts = ra.collect_artifacts(config)
        reads = {"n": 0}
        lines: list[str] = []

        def _reader():
            reads["n"] += 1
            return "KEY_UNKNOWN"

        with patch.object(ra.sys.stdin, "isatty", lambda: True):
            result = ra.prompt_open_artifacts(
                artifacts,
                key_reader=_reader,
                opener=lambda p: True,
                echo=lines.append,
                open_supported=lambda: False,
            )
        assert result == "unsupported"
        assert reads["n"] == 1  # 恰好一次：按一下即回菜单
        assert any("按任意键返回菜单" in line for line in lines)

    def test_remote_session_without_tty_does_not_wait(self, tmp_path):
        """非 TTY（脚本/管道）在远程分支也不阻塞：只打印清单与指引。"""
        config = _svc(tmp_path)
        artifacts = ra.collect_artifacts(config)
        reads = {"n": 0}
        lines: list[str] = []

        def _reader():
            reads["n"] += 1
            return "KEY_UNKNOWN"

        with patch.object(ra.sys.stdin, "isatty", lambda: False):
            result = ra.prompt_open_artifacts(
                artifacts,
                key_reader=_reader,
                opener=lambda p: True,
                echo=lines.append,
                open_supported=lambda: False,
            )
        assert result == "unsupported" and reads["n"] == 0
        assert any("scp/sftp" in line for line in lines)

    def test_open_failure_gates_before_returning_to_menu(self, tmp_path):
        """打开失败后同样停屏：先读完失败原因与传输指引再回菜单。"""
        result, _calls, lines = self._run(tmp_path, "y", opener_ok=False, tty=True)
        assert result == "failed"
        assert any("按任意键返回菜单" in line for line in lines)

    def test_empty_artifacts_do_nothing(self):
        lines: list[str] = []
        assert ra.prompt_open_artifacts((), echo=lines.append) == "skipped"
        assert lines == []

    def test_prompt_uses_yn_confirmation_form(self, tmp_path):
        """上屏提示必须是 `(y/N)` 形态（DESIGN-TUI 二选一确认：大写一侧为默认）。"""
        _result, _calls, lines = self._run(tmp_path, "n")
        prompt_lines = [line for line in lines if "是否打开" in line]
        assert prompt_lines and "(y/N)" in prompt_lines[0]
        assert "Enter" not in prompt_lines[0]  # 契约：屏上只写「回车」
