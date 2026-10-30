# -*- coding: utf-8 -*-
"""首页 `?` 速查：固定几行摘要（键位 + 分组索引 + 首用待配置项），不动任何状态。

设计约束：首页帮助**不得**把菜单顶出可视区——只打固定几行，详细键位在手册里。
"""

from __future__ import annotations

import contextlib
import io
from unittest.mock import MagicMock, patch

import pytest

from src.python.tui.tui_menu import MENU_GROUPS, menu_group_lines

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestGroupLines:
    """分组索引行：每个分组都在，键为人民可读的菜单键。"""

    def test_covers_every_group(self):
        text = "\n".join(menu_group_lines(columns=100))
        missing = [title for title, _keys in MENU_GROUPS if title not in text]
        assert missing == [], f"分组索引缺少：{missing}"

    def test_wraps_within_width(self):
        """窄屏下按列宽折行，不越界。"""
        from src.python.tui.text_layout import display_width

        for columns in (40, 60, 100):
            for line in menu_group_lines(columns=columns):
                assert display_width(line) <= columns, (columns, line)


class TestHomeHelpKey:
    """主循环里按 `?`：出摘要、不动游标、不派发任何菜单项。"""

    @staticmethod
    def _drive(keys: list[str]):
        import src.python.tui.tui as tui_mod

        executed: list[int] = []
        fired: list[str] = []
        seq = iter(keys)

        def _fake_key() -> str:
            try:
                return next(seq)
            except StopIteration:
                raise SystemExit from None

        def _fake_exit() -> None:
            fired.append("exit")
            raise SystemExit

        render_mock = MagicMock()
        out = io.StringIO()
        with (
            patch.object(tui_mod, "get_key", _fake_key),
            patch.object(tui_mod, "exit_app", _fake_exit),
            patch.object(tui_mod, "terminal_columns", return_value=100),
            patch.object(tui_mod, "init_config"),
            patch.object(tui_mod, "_apply_feature_gates"),
            patch.object(tui_mod, "_bind_callbacks"),
            patch.object(tui_mod, "execute_item", executed.append),
            patch.object(tui_mod, "print_header"),
            patch.object(tui_mod, "show_config"),
            patch.object(tui_mod, "render_menu", render_mock),
        ):
            try:
                with contextlib.redirect_stdout(out):
                    tui_mod.main()
            except SystemExit:
                pass
        return fired, executed, out.getvalue(), render_mock.call_count

    def test_help_does_not_dispatch_or_move(self):
        fired, executed, out, _renders = self._drive(["?", "0"])
        assert fired == ["exit"]
        assert executed == [], "按 ? 不得误触任何菜单项"
        assert "键位：" in out

    def test_help_lines_are_few(self):
        """摘要只占固定几行（不把菜单顶出屏）。"""
        _fired, _executed, out, _renders = self._drive(["?", "0"])
        summary = [line for line in out.splitlines() if line.strip() and ("键位：" in line or "分组：" in line)]
        assert 1 <= len(summary) <= 4, summary

    def test_help_mentions_key_discoveries(self):
        """摘要里点明 j/k、筛选、帮助与退出（用户不必翻手册即可上手）。"""
        _fired, _executed, out, _renders = self._drive(["?", "0"])
        for token in ("j k", "/ 筛选", "? 帮助", "Esc×2"):
            assert token in out, f"摘要缺少：{token}"

    def test_help_then_menu_redrawn(self):
        _fired, _executed, _out, renders = self._drive(["?", "0"])
        assert renders == 2, "初帧 + 帮助后重绘"
