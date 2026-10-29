# -*- coding: utf-8 -*-
"""分页查看器边缘（`@pytest.mark.edge`）：极矮终端、超长行、未知键、原地重绘。"""

from __future__ import annotations

import pytest

from src.python.tui.pager import Pager, view

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui, pytest.mark.edge]


class TestDegenerateTerminal:
    def test_min_rows_page_size_keeps_footer_visible(self):
        """终端刚好等于下限（8 行）：每屏 6 行内容 + 标题 + 页脚，不越界。"""
        pager = Pager("标题", [f"行{i}" for i in range(20)], rows=8, echo=lambda _l: None, inplace=False)
        assert pager.page_size == 6
        assert len(pager.page_lines()) == 8

    def test_rows_below_min_prints_everything(self, monkeypatch):
        """低于下限且是 TTY：仍整段直打（分页只会让用户看不见内容）。"""
        monkeypatch.setattr("src.python.tui.pager._stdout_is_tty", lambda: True)
        out: list[str] = []
        view("标题", ["a", "b", "c"], rows=4, key_reader=lambda: pytest.fail("不应读键"), echo=out.append)
        assert out[1:] == ["a", "b", "c"]


class TestLongLines:
    def test_over_wide_line_is_kept_intact(self):
        """超宽单行不做二次折行：分页按渲染前行数计，页脚位置仍准。"""
        lines = ["x" * 500, "短行"]
        pager = Pager("标题", lines, rows=8, echo=lambda _l: None, inplace=False)
        assert lines[0] in pager.page_lines()

    def test_empty_body_still_shows_title_and_footer(self):
        """空内容不崩：标题与页脚仍在（调用方通常已挡空，这里是兜底）。"""
        pager = Pager("标题", [], rows=10, echo=lambda _l: None, inplace=False)
        assert len(pager.page_lines()) == 2


class TestUnknownKeys:
    def test_unknown_key_does_not_exit_or_redraw(self):
        """未识别键：既不退出也不重绘（不制造无意义闪烁）。"""
        out: list[str] = []
        seq = iter(["x", "?", "q"])
        Pager(
            "标题", [f"行{i}" for i in range(40)], rows=12, key_reader=lambda: next(seq), echo=out.append, inplace=False
        ).run()
        assert len(out) == 12, "只应有首页一屏（12 行）"


class TestInplaceRedraw:
    def test_redraw_emits_cursor_up_sequence(self):
        """原地重绘模式：第二次绘制先上移并清屏，避免整屏堆积。"""
        out: list[str] = []
        seq = iter([" ", "q"])
        Pager(
            "标题", [f"行{i}" for i in range(40)], rows=12, key_reader=lambda: next(seq), echo=out.append, inplace=True
        ).run()
        assert any(line.startswith("\x1b[12A\x1b[0J") for line in out), out[:3]


class TestStateInitialised:
    """D2 回归：分页器状态在构造期初始化（不靠 run() 首次赋值兜底）。"""

    def test_start_rendered_initialised_in_constructor(self):
        pager = Pager("标题", ["a", "b"], rows=10, echo=lambda _l: None, inplace=True)
        assert pager._start_rendered is False

    def test_draw_before_run_does_not_raise(self):
        out: list[str] = []
        pager = Pager("标题", ["a", "b"], rows=10, echo=out.append, inplace=True)
        pager._draw()  # 首次绘制不应依赖 run() 先跑
        assert out, "至少要画出一屏"
