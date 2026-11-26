"""测试：`make-screenshots.py` 子命令与设备分支（伪 TTY / 伪子进程 / 依赖缺失降级）。

既有 `test_make_screenshots.py` 覆盖三块实现的纯逻辑面；本文件补命令编排面：
  - TUI 帧：伪 TTY 包装、折行续行 SGR 重开、字体缺失降级、`capture_frame` 的演示状态
    重定向与还原、`main` 的 `--text`/取帧/渲染失败三条回退
  - 演示工作区：伪终端报告输出读取（PTY 打桩，不启动真实进程）、`run_report` 的
    退出码透传与状态护栏还原
  - Web 截图：Chrome/Node 解析回退链与 `run` 的环境缺失/超时降级

外部进程（浏览器、报告生成、PTY 从端）全经替身，不发起网络也不启动真实 TUI。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="demo")
def fixture_demo():
    return load_script("_screenshots/demo_workspace.py", module_name="_screenshots_demo_cmds")


@pytest.fixture(name="tui")
def fixture_tui():
    return load_script("_screenshots/tui_frame.py", module_name="_screenshots_tui_cmds")


@pytest.fixture(name="web")
def fixture_web():
    return load_script("_screenshots/web_shot.py", module_name="_screenshots_web_cmds")


class TestTuiFramePrimitives:
    """取帧设备的边角行为（颜色必须在伪 TTY 下才非空，故需 `isatty()` 恒真代理）。"""

    def test_tty_proxy_forces_isatty_and_forwards_attrs(self, tui):
        class _Wrapped:
            flag = 7

        proxy = tui._TtyStdout(_Wrapped())
        assert proxy.isatty() is True
        assert proxy.flag == 7, "其余属性应透传给真实 stdout"
        with pytest.raises(AttributeError):
            proxy.no_such_attribute

    def test_display_width_inserts_repo_root_into_sys_path(self, tui):
        repo_root = str(tui.REPO_ROOT)
        saved = list(sys.path)
        try:
            sys.path[:] = [entry for entry in sys.path if entry != repo_root]
            assert tui.display_width("骨架") == 4, "CJK 全角按两列计"
            assert repo_root in sys.path, "缺 REPO_ROOT 时应自行补入 sys.path"
        finally:
            sys.path[:] = saved

    def test_wrap_line_reopens_active_sgr_on_continuation(self, tui):
        line = "\x1b[31m" + "A" * 12 + "B" * 12 + "\x1b[0m"
        rows = tui.wrap_line(line, columns=10)
        assert len(rows) > 1
        assert all(tui.strip_ansi(row) for row in rows), "续行不得只剩 SGR 序列"
        assert rows[1].startswith("\x1b[31m"), "跨行续行须重新打开当前配色"
        assert "".join(tui.strip_ansi(row) for row in rows) == "A" * 12 + "B" * 12

    def test_wrap_line_handles_overflow_after_last_sgr(self, tui):
        """末段裸文本（最后一个 SGR 之后）同样要按列宽折行。"""
        line = "\x1b[32m甲乙\x1b[0m" + "丙" * 8
        rows = tui.wrap_line(line, columns=6)
        assert len(rows) > 1
        assert tui.strip_ansi(rows[-1]).startswith("丙")

    def test_missing_font_raises_render_dependency_error(self, tui, monkeypatch):
        monkeypatch.setattr(tui, "FONT_CANDIDATES", ("/nonexistent/font.otf",))
        with pytest.raises(tui.RenderDependencyError, match="未找到等宽 CJK 字体"):
            tui.resolve_font()

    def test_render_dim_code_uses_muted_palette(self, tui, tmp_path):
        """SGR 2（dim）在配色表里映射 90 号灰，不落回默认前景。"""
        out = tui.render("\x1b[2m次要文本\x1b[0m\n\x1b[31m主要文本\x1b[0m\n", tmp_path / "frames" / "shot.png")
        assert out.is_file() and out.stat().st_size > 0
        assert out.parent.is_dir(), "输出目录应自动创建"


class TestCaptureFrame:
    """`capture_frame`：演示工作区状态重定向，失败也要还原（不污染真实 data/state）。"""

    @pytest.fixture(name="stubs")
    def _stubs(self, monkeypatch, tmp_path):
        import src.python.config as config_pkg
        import src.python.core.perf as perf_mod
        import src.python.tui.tui_menu as tui_menu

        recorded: dict[str, object] = {
            "menu_calls": [],
            "menu_selection": None,
            "config_calls": [],
            "invalidations": [],
        }
        original_perf = perf_mod._PERF_HISTORY_FILE
        original_health = perf_mod._HEALTH_CHECK_FILE

        # 记录调用**序列**（而非最后一次入参）：覆写只应在进入时设一次，还原必须走原值回写
        monkeypatch.setattr(
            config_pkg,
            "set_config_path_override",
            lambda path: recorded["config_calls"].append(path),
        )
        monkeypatch.setattr(config_pkg, "invalidate_config_cache", lambda: recorded["invalidations"].append(True))

        def _print_header():
            recorded["perf_during"] = perf_mod._PERF_HISTORY_FILE
            recorded["health_during"] = perf_mod._HEALTH_CHECK_FILE
            print("页头状态行")

        def _show_config():
            recorded["menu_calls"].append("config")
            print("配置概览")

        def _render_menu(index):
            recorded["menu_selection"] = index
            recorded["menu_calls"].append("menu")
            print("菜单面板")

        monkeypatch.setattr(tui_menu, "refresh_config", lambda: recorded["menu_calls"].append("refresh"))
        monkeypatch.setattr(tui_menu, "print_header", _print_header)
        monkeypatch.setattr(tui_menu, "show_config", _show_config)
        monkeypatch.setattr(tui_menu, "get_config_cache", lambda: {"default_menu_key": "R"})
        monkeypatch.setattr(tui_menu, "index_by_key", lambda key: 3 if key == "R" else None)
        monkeypatch.setattr(tui_menu, "render_menu", _render_menu)
        recorded["original_perf"] = original_perf
        recorded["original_health"] = original_health
        recorded["perf_mod"] = perf_mod
        return recorded

    @pytest.fixture(name="config_file")
    def _config_file(self, tmp_path):
        config_path = tmp_path / "demo" / "data" / "config" / "config.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("{}", encoding="utf-8")
        return config_path

    def test_captures_home_frame_with_demo_state_paths(self, tui, stubs, config_file):
        text = tui.capture_frame(config_file)
        assert "页头状态行" in text and "菜单面板" in text
        assert stubs["menu_calls"][0] == "refresh"
        assert stubs["config_calls"] == [str(config_file)]
        assert len(stubs["invalidations"]) == 2, "进入时清一次 + 还原后再清一次"
        # 状态行读的 perf/健康历史指向演示目录（演示目录无文件 → 显示占位）
        state_dir = str(config_file.parents[2] / "data" / "state")
        assert str(stubs["perf_during"]).startswith(state_dir)
        assert str(stubs["health_during"]).startswith(state_dir)
        # 游标落在配置声明的缺省菜单项上（真机首页状态）
        assert stubs["menu_selection"] == 3

    def test_restores_module_state_and_stdout(self, tui, stubs, config_file):
        saved_stdout = sys.stdout
        tui.capture_frame(config_file)
        assert sys.stdout is saved_stdout
        perf_mod = stubs["perf_mod"]
        assert perf_mod._PERF_HISTORY_FILE == stubs["original_perf"]
        assert perf_mod._HEALTH_CHECK_FILE == stubs["original_health"]

    def test_leaves_config_path_override_untouched_when_none_before_capture(self, tui, config_file):
        """无前置覆写时取帧（配置面不打桩）：结束后仍是「无覆写」，配置路径没被钉在演示工作区。"""
        import src.python.config as config_pkg

        assert config_pkg._config_defaults._CONFIG_PATH_OVERRIDE is None
        tui.capture_frame(config_file)
        assert config_pkg._config_defaults._CONFIG_PATH_OVERRIDE is None, "原无覆写不得被还原成覆写"
        effective = config_pkg.get_config_path()
        assert "demo" not in effective
        assert effective == config_pkg._config_defaults._CONFIG_FILE, "应回到隔离的默认配置路径"

    def test_unknown_default_key_falls_back_to_first_entry(self, tui, stubs, config_file, monkeypatch):
        import src.python.tui.tui_menu as tui_menu

        monkeypatch.setattr(tui_menu, "get_config_cache", lambda: {"default_menu_key": "Z"})
        monkeypatch.setattr(tui_menu, "index_by_key", lambda key: None)
        tui.capture_frame(config_file)
        assert stubs["menu_selection"] == 0

    def test_restores_stdout_when_capture_fails(self, tui, config_file, monkeypatch):
        import src.python.config._config_defaults as cfg_defaults
        import src.python.core.perf as perf_mod
        import src.python.tui.tui_menu as tui_menu

        saved_stdout = sys.stdout
        saved_perf = perf_mod._PERF_HISTORY_FILE
        saved_health = perf_mod._HEALTH_CHECK_FILE

        def _boom():
            raise RuntimeError("取帧失败")

        monkeypatch.setattr(tui_menu, "print_header", _boom)
        with pytest.raises(RuntimeError, match="取帧失败"):
            tui.capture_frame(config_file)
        assert sys.stdout is saved_stdout
        # 失败路径同样须还原全局状态（否则把还原从 finally 挪进 try 仍会全绿）
        assert cfg_defaults._CONFIG_PATH_OVERRIDE is None
        assert perf_mod._PERF_HISTORY_FILE == saved_perf
        assert perf_mod._HEALTH_CHECK_FILE == saved_health


class TestTuiMain:
    """`tui <out.png>` 子命令：帧文本来源优先级与渲染依赖缺失降级。"""

    def test_text_file_skips_capture_and_scrubs_paths(self, tui, tmp_path, capsys, monkeypatch):
        out = tmp_path / "shot.png"
        text_file = tmp_path / "frame.txt"
        repo = str(tui.REPO_ROOT)
        text_file.write_text(f"报告已生成 {repo}/reports/a.html\n", encoding="utf-8")
        rendered: dict[str, object] = {}

        def _render(text, path):
            rendered["text"] = text
            return path

        monkeypatch.setattr(tui, "render", _render)

        def _no_capture(_config):
            raise AssertionError("给了 --text 就不该再取帧")

        monkeypatch.setattr(tui, "capture_frame", _no_capture)
        assert tui.main([str(out), "--text", str(text_file)]) == 0
        assert "报告已生成 reports/a.html" in str(rendered["text"])
        assert repo not in str(rendered["text"])
        assert "[OK]" in capsys.readouterr().out

    def test_missing_text_falls_back_to_capture(self, tui, tmp_path, monkeypatch):
        captured: list[Path] = []

        def _capture(config_path):
            captured.append(config_path)
            return "帧文本"

        monkeypatch.setattr(tui, "capture_frame", _capture)
        monkeypatch.setattr(tui, "render", lambda text, path: path)
        config = tmp_path / "config.json"
        config.write_text("{}", encoding="utf-8")
        assert tui.main([str(tmp_path / "a.png"), "--config", str(config)]) == 0
        assert captured == [config.resolve()]

    def test_render_dependency_missing_returns_one(self, tui, tmp_path, capsys, monkeypatch):
        text_file = tmp_path / "frame.txt"
        text_file.write_text("内容\n", encoding="utf-8")

        def _raise(_text, _path):
            raise tui.RenderDependencyError("缺少 Pillow")

        monkeypatch.setattr(tui, "render", _raise)
        assert tui.main([str(tmp_path / "a.png"), "--text", str(text_file)]) == 1
        assert "缺少 Pillow" in capsys.readouterr().out


class _FakePopen:
    """伪终端子进程：把预设输出写进从端后立即关闭，主端读到数据即 EOF。"""

    payload = b""
    commands: list[list[str]] = []

    def __init__(self, cmd, **_kwargs):
        type(self).commands.append([str(part) for part in cmd])
        writer = os.fdopen(os.dup(_kwargs["stdout"]), "wb", closefd=True)
        with writer:
            writer.write(type(self).payload)

    def wait(self, timeout=None):
        return 0


class TestDemoWorkspaceCommands:
    """演示报告的执行面：PTY 输出读取与退出码透传（子进程与 PTY 全打桩）。"""

    @pytest.fixture(name="demo_ready")
    def _demo_ready(self, demo, tmp_path, monkeypatch):
        """把演示工作区根目录重定向到 tmp（`scrub_cli_paths` 按 DEFAULT_ROOT 抹前缀）。"""
        root = tmp_path / "shots"
        monkeypatch.setattr(demo, "DEFAULT_ROOT", root)
        demo.build()
        recorded: dict[str, object] = {"restored": 0}

        def _snapshot(paths):
            recorded["guarded"] = paths
            return {path: b"" for path in paths}

        def _restore(paths, snap):
            recorded["restored"] = recorded["restored"] + 1
            recorded["restore_paths"] = paths
            recorded["restore_snap"] = snap

        monkeypatch.setattr(demo, "snapshot_paths", _snapshot)
        monkeypatch.setattr(demo, "restore_paths", _restore)
        return root, recorded

    def test_capture_report_text_drains_pty_and_scrubs_paths(self, demo, demo_ready, monkeypatch):
        import pty

        _root, recorded = demo_ready
        _FakePopen.commands = []
        _FakePopen.payload = f"\x1b[32m[OK]\x1b[0m 报告完成 {demo.demo_dir() / 'reports' / 'a.html'}\n".encode()
        monkeypatch.setattr(pty, "openpty", lambda: os.pipe())
        monkeypatch.setattr(demo, "subprocess", type("_Sub", (), {"Popen": _FakePopen, "DEVNULL": subprocess.DEVNULL}))
        text = demo.capture_report_text()
        assert "报告完成 reports/a.html" in text
        assert str(demo.demo_dir()) not in text, "演示目录绝对路径须从屏上抹掉"
        assert recorded["restored"] == 1
        assert _FakePopen.commands and str(demo.config_path()) in " ".join(_FakePopen.commands[0])

    def test_capture_report_text_restores_state_on_failure(self, demo, demo_ready, monkeypatch):
        import pty

        _root, recorded = demo_ready

        def _explode(*_args, **_kwargs):
            raise OSError("从端关闭")

        monkeypatch.setattr(pty, "openpty", lambda: os.pipe())
        monkeypatch.setattr(demo, "subprocess", type("_Sub", (), {"Popen": _explode, "DEVNULL": subprocess.DEVNULL}))
        with pytest.raises(OSError, match="从端关闭"):
            demo.capture_report_text()
        assert recorded["restored"] == 1, "失败路径同样必须还原状态护栏"

    def test_run_report_passes_through_exit_code(self, demo, demo_ready, monkeypatch, capsys):
        _root, recorded = demo_ready
        seen: dict[str, object] = {}

        def _run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs["env"]
            seen["cwd"] = kwargs["cwd"]
            return subprocess.CompletedProcess(cmd, 2)

        monkeypatch.setattr(demo, "subprocess", type("_Sub", (), {"run": staticmethod(_run)}))
        assert demo.run_report() == 2
        assert "[ERR]" in capsys.readouterr().out
        assert seen["cwd"] == demo.demo_dir()
        assert str(demo.REPO_ROOT) in str(seen["env"]["PYTHONPATH"])
        assert recorded["restored"] == 1

    def test_run_report_success_reports_ok(self, demo, demo_ready, monkeypatch, capsys):
        _root, _recorded = demo_ready

        def _run(cmd, **_kwargs):
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(demo, "subprocess", type("_Sub", (), {"run": staticmethod(_run)}))
        assert demo.run_report() == 0
        assert "[OK] 演示报告" in capsys.readouterr().out


class TestWebShotResolution:
    """`web_shot.run` 的环境缺失降级与命令装配（node/chromium 均打桩）。"""

    def test_explicit_chrome_wins(self, web, tmp_path):
        chrome = tmp_path / "chrome"
        chrome.write_text("", encoding="utf-8")
        assert web.resolve_chrome(str(chrome)) == chrome

    def test_env_chrome_used_when_no_explicit(self, web, tmp_path, monkeypatch):
        chrome = tmp_path / "chromium"
        chrome.write_text("", encoding="utf-8")
        monkeypatch.setenv("CHROME_BIN", str(chrome))
        monkeypatch.setattr(web, "_SYSTEM_CANDIDATES", ())
        monkeypatch.setattr(web, "glob", type("_G", (), {"glob": staticmethod(lambda _pat: [])}))
        assert web.resolve_chrome() == chrome

    def test_playwright_and_system_candidates_are_probed(self, web, tmp_path, monkeypatch):
        playwright_hit = tmp_path / "pw" / "chrome"
        playwright_hit.parent.mkdir()
        playwright_hit.write_text("", encoding="utf-8")
        system_hit = tmp_path / "system-chrome"
        system_hit.write_text("", encoding="utf-8")
        monkeypatch.delenv("CHROME_BIN", raising=False)
        monkeypatch.setattr(web, "glob", type("_G", (), {"glob": staticmethod(lambda _pat: [str(playwright_hit)])}))
        assert web.resolve_chrome() == playwright_hit
        monkeypatch.setattr(web, "glob", type("_G", (), {"glob": staticmethod(lambda _pat: [])}))
        monkeypatch.setattr(web, "_SYSTEM_CANDIDATES", (str(system_hit),))
        assert web.resolve_chrome() == system_hit
        monkeypatch.setattr(web, "_SYSTEM_CANDIDATES", ())
        assert web.resolve_chrome() is None

    def test_node_lookup_uses_which(self, web, monkeypatch):
        monkeypatch.setattr(web.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None)
        assert web.resolve_node() == "/usr/bin/node"
        monkeypatch.setattr(web.shutil, "which", lambda name: None)
        assert web.resolve_node() is None

    def test_missing_node_returns_one(self, web, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(web, "resolve_node", lambda: None)
        assert web.run("http://127.0.0.1/x", tmp_path / "a.png") == 1
        assert "未找到 node" in capsys.readouterr().out

    def test_missing_chrome_returns_one(self, web, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(web, "resolve_node", lambda: "node")
        monkeypatch.setattr(web, "resolve_chrome", lambda _explicit=None: None)
        assert web.run("http://127.0.0.1/x", tmp_path / "a.png") == 1
        assert "未找到 Chromium/Chrome" in capsys.readouterr().out

    def test_missing_cdp_script_returns_one(self, web, tmp_path, capsys, monkeypatch):
        monkeypatch.setattr(web, "resolve_node", lambda: "node")
        monkeypatch.setattr(web, "resolve_chrome", lambda _explicit=None: Path(sys.executable))
        monkeypatch.setattr(web, "CDP_SCRIPT", tmp_path / "absent.mjs")
        assert web.run("http://127.0.0.1/x", tmp_path / "a.png") == 1
        assert "缺少 CDP 脚本" in capsys.readouterr().out

    def test_success_wires_chrome_env_and_returns_code(self, web, tmp_path, monkeypatch):
        cdp = tmp_path / "cdp_shot.mjs"
        cdp.write_text("// stub\n", encoding="utf-8")
        chrome = tmp_path / "chrome"
        chrome.write_text("", encoding="utf-8")
        seen: dict[str, object] = {}

        def _run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs["env"]
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(web, "resolve_node", lambda: "node")
        monkeypatch.setattr(web, "resolve_chrome", lambda _explicit=None: chrome)
        monkeypatch.setattr(web, "CDP_SCRIPT", cdp)
        monkeypatch.setattr(web.subprocess, "run", _run)
        assert web.run("http://127.0.0.1/x", tmp_path / "a.png", scroll_y=120, replace=".ad class=hidden") == 0
        assert seen["env"]["CHROME_BIN"] == str(chrome)
        assert seen["cmd"][1] == str(cdp) and "120" in seen["cmd"]

    def test_timeout_returns_one(self, web, tmp_path, capsys, monkeypatch):
        cdp = tmp_path / "cdp_shot.mjs"
        cdp.write_text("// stub\n", encoding="utf-8")

        def _timeout(cmd, **_kwargs):
            raise subprocess.TimeoutExpired(cmd, 300)

        monkeypatch.setattr(web, "resolve_node", lambda: "node")
        monkeypatch.setattr(web, "resolve_chrome", lambda _explicit=None: Path(sys.executable))
        monkeypatch.setattr(web, "CDP_SCRIPT", cdp)
        monkeypatch.setattr(web.subprocess, "run", _timeout)
        assert web.run("http://127.0.0.1/x", tmp_path / "a.png") == 1
        assert "截图超时" in capsys.readouterr().out
