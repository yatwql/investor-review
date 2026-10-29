# -*- coding: utf-8 -*-
"""首页 `?` 键位速查：主菜单投影复用面板帮助渲染，且不改任何状态。

与面板内 `?` 的关系：同一句话（「这一屏能按什么」），只是把「这一屏」换成主菜单。
因此实现上是**投影**（`menu_help_items` → `keys_help_lines`），不是另写一套帮助。
"""

from __future__ import annotations

import contextlib
import io
from unittest.mock import MagicMock, patch

import pytest

from src.python.tui.tui_menu import MENU_GROUPS, MENU_ITEMS, menu_help_items

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestMenuHelpProjection:
    """投影：键与菜单一一对应，详情带上所属分组。"""

    def test_keys_match_menu_items(self):
        """投影出的键与主菜单按键逐一对应（不增不减，顺序一致）。"""
        assert [item.key for item in menu_help_items()] == [key for key, _l, _c, _e in MENU_ITEMS]

    def test_detail_carries_group_name(self):
        """每项详情以所属分组开头（帮助屏因此能看到分组归属）。"""
        groups = {title for title, _keys in MENU_GROUPS}
        items = menu_help_items()
        grouped = [item for item in items if any(item.detail.startswith(g) for g in groups)]
        assert grouped, "至少有一项的详情带上分组名"
        assert all(item.kind == "info" for item in items), "投影项是只读信息项，不承载动作"

    def test_help_lines_cover_all_groups(self):
        """帮助文本含全部分组标题与全部菜单键（键一览 + 分组索引两段合一）。"""
        from src.python.tui.prompt_text import keys_help_lines
        from src.python.tui.tui_menu import menu_group_lines

        text = "\n".join([*keys_help_lines(menu_help_items(), columns=100), *menu_group_lines(columns=100)])
        for title, _keys in MENU_GROUPS:
            assert title in text, f"帮助缺少分组：{title}"
        for key, _label, _cb, _is_exit in MENU_ITEMS:
            assert f"    {key} — " in text, f"帮助缺少菜单键：{key}"


class TestHomeHelpKey:
    """主循环里按 `?`：出速查、不动游标、不派发任何菜单项。"""

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
        """`?` 后接 `0` 退出：期间没有任何菜单项被执行。"""
        fired, executed, out, _renders = self._drive(["?", "0"])
        assert fired == ["exit"]
        assert executed == [], "按 ? 不得误触任何菜单项"
        assert "可用键：" in out

    def test_help_then_menu_redrawn(self):
        """帮助后重绘一帧菜单（帮助留在上方可继续读）。"""
        _fired, _executed, _out, renders = self._drive(["?", "0"])
        assert renders == 2, "初帧 + 帮助后重绘"

    def test_help_lists_common_paths(self):
        """帮助屏给出三条常用动线（速查要能直接当入口用）。"""
        _fired, _executed, out, _renders = self._drive(["?", "0"])
        for word in ("生成报告 B", "改配置 G", "筛选"):
            assert word in out, f"帮助缺少动线提示：{word}"
