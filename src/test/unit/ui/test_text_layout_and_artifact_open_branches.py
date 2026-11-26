"""TUI 产物打开/读键的延迟导入与非终端分支。

覆盖点：
  - ``_stdin_isatty`` 在 stdin 替身抛异常时按非 TTY 处理
  - 产物打开/读键的延迟导入出口取到真实实现（不复制判定逻辑）

``text_layout`` 的硬切/空段落兜底行（``wrap_display`` 的 ``current.strip()``
分支、``wrap_hanging``/``wrap_with_prefix`` 的空折行与 ``find`` 失败分支）不可达：
``wrap_display`` 恒至少返回一行且返回行必为入参子串，故这些防御分支无输入可触发。
"""

from __future__ import annotations

import pytest

import src.python.tui.report_artifacts as report_artifacts

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestStdinIsattyFallbacks:
    """stdin 替身无 isatty 或 isatty 抛异常 → 按非 TTY 处理。"""

    def test_isatty_exception_returns_false(self, monkeypatch):
        class _BrokenStdin:
            def isatty(self):
                raise OSError("无控制终端")

        monkeypatch.setattr(report_artifacts.sys, "stdin", _BrokenStdin())

        assert report_artifacts._stdin_isatty() is False


class TestLazyImportExits:
    """延迟导入出口必须取到真实实现（而不是复制一份判定逻辑）。"""

    def test_local_open_supported_delegates_to_core(self, monkeypatch):
        monkeypatch.setattr("src.python.core.artifacts.local_open_supported", lambda: True)

        assert report_artifacts._local_open_supported() is True

    def test_get_key_delegates_to_keys_module(self, monkeypatch):
        monkeypatch.setattr("src.python.tui.tui_keys.get_key", lambda: "q")

        assert report_artifacts._get_key() == "q"
