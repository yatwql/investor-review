# -*- coding: utf-8 -*-
"""分页查看器（`tui/pager.py`）：退化口径、翻页/首末、搜索置顶、三种退出键。

退化是硬前提：不足一屏或非 TTY 时整段直打且**不读键**——管道输出与逐行打印
逐字节一致，长输出场景不多出任何击键。
"""

from __future__ import annotations

import pytest

from src.python.tui.pager import FOOTER_KEYS, Pager, view
from src.python.tui.tui_keys import KEY_DOWN, KEY_ESC, KEY_UP

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

_LINES = [f"第 {i:02d} 行内容" for i in range(1, 41)]  # 40 行


def _drive(keys: list[str], lines: list[str] | None = None, *, rows: int = 12) -> list[str]:
    """驱动分页器，返回全部上屏行（原地重绘的清除序列不计入内容断言）。"""
    out: list[str] = []
    seq = iter(keys)

    def _read() -> str:
        return next(seq)

    pager = Pager(
        "标题",
        list(lines if lines is not None else _LINES),
        rows=rows,
        key_reader=_read,
        echo=out.append,
        inplace=False,
    )
    pager.run()
    return out


class TestDegrade:
    """不足一屏 / 非 TTY：整段直打，不读键。"""

    def test_short_output_prints_all_without_reading_keys(self):
        """一屏放得下时整段直打（不读键 ⇒ 不会因为等键卡住）。"""
        out: list[str] = []
        view("标题", ["a", "b"], rows=24, key_reader=lambda: pytest.fail("不应读键"), echo=out.append)
        assert "标题" in out[0], "退化路径也带标题（管道输出要能自解释）"
        assert out[1:] == ["a", "b"]

    def test_non_tty_prints_all(self, monkeypatch):
        """非 TTY（管道/重定向）无论多长都整段直打。"""
        monkeypatch.setattr("src.python.tui.pager._stdout_is_tty", lambda: False)
        out: list[str] = []
        view("标题", _LINES, rows=12, key_reader=lambda: pytest.fail("不应读键"), echo=out.append)
        assert out[1:] == _LINES

    def test_below_min_rows_prints_all(self, monkeypatch):
        """终端过矮（< 8 行）分页无意义：整段直打。"""
        monkeypatch.setattr("src.python.tui.pager._stdout_is_tty", lambda: True)
        out: list[str] = []
        view("标题", _LINES, rows=5, key_reader=lambda: pytest.fail("不应读键"), echo=out.append)
        assert out[1:] == _LINES


class TestPaging:
    """翻页、首末、末屏对齐。"""

    def test_first_page_has_title_body_and_footer(self):
        """首页 = 标题 + 每屏内容 + 页脚（页脚含键位与区间）。"""
        page = _drive(["q"])[:12]
        assert page[0].strip() == "标题"
        assert FOOTER_KEYS in page[-1]
        assert "第 1-10 / 40 行" in page[-1]

    def test_page_down_advances_one_screen(self):
        """空格下翻一屏：第二屏从第 11 行开始。"""
        out = _drive([" ", "q"])
        assert any("第 11-20 / 40 行" in line for line in out)

    def test_page_up_returns(self):
        """b 上翻一屏回到首页区间。"""
        out = _drive([" ", "b", "q"])
        assert out[-1].endswith("第 1-10 / 40 行） ──"), out[-1]

    def test_down_arrow_and_j_behave_like_space(self):
        """↓ 与 j 同空格（一屏），三种键都能翻。"""
        for key in (KEY_DOWN, "j"):
            out = _drive([key, "q"])
            assert any("第 11-20 / 40 行" in line for line in out), key

    def test_last_page_aligned_to_bottom(self):
        """末屏对齐到底部，不留半屏空行。"""
        out = _drive(["G", "q"])
        assert any("第 31-40 / 40 行" in line for line in out)

    def test_g_returns_to_top(self):
        """G 到末屏后 g 回首屏。"""
        out = _drive(["G", "g", "q"])
        assert out[-1].endswith("第 1-10 / 40 行） ──"), out[-1]

    def test_up_key_at_top_is_noop(self):
        """首页按上翻不移动也不重绘（避免无意义闪烁）。"""
        out = _drive([KEY_UP, "q"])
        assert len([line for line in out if "第 1-10" in line]) == 1


class TestQuitKeys:
    """q / Esc / 0 三键都退出（与面板「0 返回」同向）。"""

    @pytest.mark.parametrize("key", ["q", KEY_ESC, "0"])
    def test_each_quit_key_exits(self, key):
        """任一退出键都结束视图（不读下一次键）。"""
        page = _drive([key])
        assert page, "至少渲染过一屏"
        assert key not in page


class TestSearch:
    """搜索：命中行置顶 + 命中计数，不做反色高亮。"""

    def _drive_search(self, keyword: str) -> list[str]:
        out: list[str] = []
        seq = iter(["/", "q"])

        def _read() -> str:
            return next(seq)

        pager = Pager(
            "标题",
            _LINES,
            rows=12,
            key_reader=_read,
            line_reader=lambda _prompt="": keyword,
            echo=out.append,
            inplace=False,
        )
        pager.run()
        return out

    def test_hit_brings_line_to_page_and_counts(self):
        """命中行出现在当前屏，页脚给出命中共计。"""
        out = self._drive_search("第 25 行")
        assert any("第 25 行内容" in line for line in out)
        assert any("命中 1/1" in line for line in out)

    def test_miss_reports_no_hit(self):
        """未命中：页脚给出「未命中」，不移动位置。"""
        out = self._drive_search("不存在的词")
        assert any("未命中" in line for line in out)

    def test_cancelled_search_keeps_view(self):
        """搜索被 Esc 取消（返回 None）时不改变当前屏。"""
        out: list[str] = []
        seq = iter(["/", "q"])
        pager = Pager(
            "标题",
            _LINES,
            rows=12,
            key_reader=lambda: next(seq),
            line_reader=lambda _prompt="": None,
            echo=out.append,
            inplace=False,
        )
        pager.run()
        assert out[-1].endswith("第 1-10 / 40 行） ──"), out[-1]


class TestViewEntryPaths:
    """`view()` 的入口分支：一屏放得下 / 空内容 / 原地重绘判定。"""

    def test_content_fitting_one_screen_prints_all(self, monkeypatch):
        """TTY 且一屏放得下：整段直打（不进分页状态机）。"""
        monkeypatch.setattr("src.python.tui.pager._stdout_is_tty", lambda: True)
        out: list[str] = []
        view("标题", ["a", "b", "c"], rows=12, key_reader=lambda: pytest.fail("不应读键"), echo=out.append)
        assert out[1:] == ["a", "b", "c"]

    def test_empty_content_returns_without_output(self, monkeypatch):
        """空内容直接返回（不发标题、不读键）。"""
        monkeypatch.setattr("src.python.tui.pager._stdout_is_tty", lambda: True)
        out: list[str] = []
        view("标题", [], rows=12, key_reader=lambda: pytest.fail("不应读键"), echo=out.append)
        assert out == []

    def test_tty_probe_failure_treated_as_non_tty(self, monkeypatch):
        """`isatty()` 异常按非 TTY 处理（退化直打，不因探测失败崩）。"""

        def _boom():
            raise OSError("no stdout")

        monkeypatch.setattr("sys.stdout.isatty", _boom)
        out: list[str] = []
        view("标题", _LINES, rows=12, key_reader=lambda: pytest.fail("不应读键"), echo=out.append)
        assert out[1:] == _LINES

    def test_inplace_defaults_to_posix_tty(self, monkeypatch):
        """POSIX + TTY：默认原地重绘（上移清屏序列可见）。"""
        import os

        monkeypatch.setattr("src.python.tui.pager._stdout_is_tty", lambda: True)
        monkeypatch.setattr(os, "name", "posix")
        out: list[str] = []
        seq = iter([" ", "q"])
        view("标题", _LINES, rows=12, key_reader=lambda: next(seq), echo=out.append)
        assert any(line.startswith("\x1b[12A") for line in out), "POSIX+TTY 应默认原地重绘"

    def test_inplace_defaults_to_append_on_non_posix(self, monkeypatch):
        """非 POSIX（Windows）：逐页追加，不输出光标上移序列。"""
        import os

        monkeypatch.setattr("src.python.tui.pager._stdout_is_tty", lambda: True)
        monkeypatch.setattr(os, "name", "nt")
        out: list[str] = []
        seq = iter([" ", "q"])
        view("标题", _LINES, rows=12, key_reader=lambda: next(seq), echo=out.append)
        assert not any(line.startswith("\x1b[") for line in out), "非 POSIX 不得原地重绘"


class TestSearchInterrupt:
    """搜索输入被中断 / 留空时的状态口径。"""

    def _drive(self, line_reader) -> list[str]:
        out: list[str] = []
        seq = iter(["/", "q"])
        Pager(
            "标题",
            _LINES,
            rows=12,
            key_reader=lambda: next(seq),
            line_reader=line_reader,
            echo=out.append,
            inplace=False,
        ).run()
        return out

    def test_search_input_interrupted_keeps_view(self):
        """读取搜索词时 EOF/中断：回到分页视图，不抛不退出。"""

        def _raise(_prompt=""):
            raise EOFError

        out = self._drive(_raise)
        assert out[-1].endswith("第 1-10 / 40 行） ──"), out[-1]

    def test_blank_keyword_clears_hit_note(self):
        """空关键词：清除上一次命中提示，位置不变。"""
        out = self._drive(lambda _prompt="": "   ")
        assert not any("命中" in line for line in out)
        assert out[-1].endswith("第 1-10 / 40 行） ──"), out[-1]


class TestScrollGuards:
    """已在边界时的翻页/跳转键不重绘（避免无意义闪烁）。"""

    @pytest.mark.parametrize("key", [" ", KEY_UP, "g"])
    def test_boundary_keys_do_not_redraw(self, key):
        """首页按 空格/b/g 均不产生第二屏。"""
        out = _drive([key, "q"])
        assert len([line for line in out if "第 1-10" in line]) == 1

    def test_space_on_last_page_does_not_redraw(self):
        """末屏按下翻：停在末屏，不重绘、不越界。"""
        out = _drive(["G", " ", "q"])
        assert len([line for line in out if "第 31-40 / 40 行" in line]) == 1, "末屏再下翻不应重绘（无第二屏）"

    def test_G_on_last_page_does_not_redraw(self):
        """已在末屏再按 G：不重绘。"""
        out = _drive(["G", "G", "q"])
        assert len([line for line in out if "第 31-40 / 40 行" in line]) == 1
