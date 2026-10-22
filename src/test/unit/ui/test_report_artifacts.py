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

    def test_default_opener_failure_is_swallowed(self, tmp_path, monkeypatch):
        """系统命令缺失/无图形环境 → 返回 False，不抛异常（平台分派在 core.artifacts）。"""
        from src.python.core import artifacts as core_artifacts

        def _boom(*_a, **_k):
            raise FileNotFoundError("xdg-open")

        monkeypatch.setattr(core_artifacts.subprocess, "run", _boom)
        monkeypatch.setattr(core_artifacts.sys, "platform", "linux")
        assert core_artifacts.open_path(tmp_path) is False


class TestPromptOpenArtifacts:
    def _run(self, tmp_path, key, *, opener_ok=True, tty=True):
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
            ra.prompt_open_artifacts(artifacts, key_reader=lambda: "KEY_CTRL_C", opener=lambda p: True)
        mock_exit.assert_called_once()

    def test_open_failure_reports_manual_path(self, tmp_path):
        result, calls, lines = self._run(tmp_path, "y", opener_ok=False)
        assert result == "failed"
        assert any("打开失败" in line and "手动访问" in line for line in lines)

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
            result = ra.prompt_open_artifacts(artifacts, key_reader=_reader, opener=lambda p: True, echo=lines.append)
        assert result == "skipped" and asked["n"] == 0
        assert any("产物文件" in line for line in lines)

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
