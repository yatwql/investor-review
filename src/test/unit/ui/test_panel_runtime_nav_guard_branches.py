"""panel_runtime / text_layout / symbols 的守卫分支单测。

覆盖三处「降级路径」契约：
  - ``panel_runtime.NavState.move`` 无谓词时按筛选态回绕、谓词全拒时返回 False；
  - ``panel_runtime.panel_loop`` 未注入 read 时回落 ``input_choice``、pick 收集
    命中 return 项执行闭包、无 ``on_text`` 时给单源无效反馈；
  - ``text_layout`` 列宽非正时的原样返回/空串降级；
  - ``symbols`` ASCII 代理的 ``flush`` 透传与 ``install_ascii_stream`` 就地替换 stdout。

运行：
  pytest src/test/unit/ui/test_panel_runtime_nav_guard_branches.py -v
"""

from __future__ import annotations

import io

import pytest

from src.python.tui import symbols as sym_mod
from src.python.tui import text_layout
from src.python.tui.panel_runtime import NavState, PanelItem, _apply_panel_filter, _emit_nav_feedback, panel_loop
from src.python.tui.tui_keys import KEY_DOWN

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _reader(sequence: list[str | None]):
    """可控行输入桩：按序弹出预设输入（耗尽后返回 None 结束循环）。"""
    it = iter(sequence)

    def _read(prompt: str, arrows: bool = False) -> str | None:  # noqa: ARG001
        return next(it, None)

    return _read


def _render_blank(nav: NavState) -> list[str]:
    return []


class TestNavStateMoveGuards:
    """``move`` 无谓词/谓词全拒两条分支。"""

    def test_move_without_predicate_follows_filter_state(self):
        """筛选态下无谓词的 move 只在可见项之间回绕。"""
        nav = NavState(count=3, cursor=0)
        nav.apply_filter([2], keyword="丙")
        assert nav.move(KEY_DOWN) is True
        assert nav.cursor == 2
        assert nav.engaged is True

    def test_move_returns_false_when_predicate_rejects_all(self):
        """可导航谓词对所有项返回 False 时 move 报「未移动」。"""
        nav = NavState(count=3, cursor=0)
        assert nav.move(KEY_DOWN, navigable=lambda _i: False) is False
        assert nav.cursor == 0
        assert nav.engaged is False


class TestPanelLoopGuardBranches:
    """``panel_loop`` 的回落与无回调分支。"""

    def test_read_falls_back_to_input_choice(self, monkeypatch, capsys):
        """未注入 read 时回落模块级 ``input_choice``（Esc 返回即退出）。"""
        seen: list[str] = []

        def _fake_input_choice(prompt: str, arrows: bool = False) -> str | None:  # noqa: ARG001
            seen.append(prompt)
            return None

        monkeypatch.setattr("src.python.tui.panel_runtime.input_choice", _fake_input_choice)
        panel_loop([PanelItem("1", "甲")], render=_render_blank, prompt="选择: ")
        assert seen == ["选择: "]
        capsys.readouterr()

    def test_pick_return_item_runs_action(self, capsys):
        """pick>1 收集态键入 return 项键：执行闭包后退出。"""
        calls: list[str] = []
        items = [
            PanelItem("1", "甲"),
            PanelItem("0", "返回", kind="return", action=lambda: calls.append("return")),
        ]
        panel_loop(items, render=_render_blank, prompt="选择: ", read=_reader(["0"]), pick=2)
        assert calls == ["return"]
        capsys.readouterr()

    def test_pick_without_on_text_emits_invalid(self, capsys):
        """pick>1 且无 on_text：未命中 return 的输入给无效反馈后继续循环。"""
        items = [PanelItem("1", "甲"), PanelItem("0", "返回", kind="return")]
        panel_loop(items, render=_render_blank, prompt="选择: ", read=_reader(["9", None]), pick=2)
        assert "无效选择" in capsys.readouterr().out

    def test_unmatched_choice_without_on_text_emits_invalid(self, capsys):
        """单键非项键且无 on_text：落单源无效反馈。"""
        panel_loop([PanelItem("1", "甲")], render=_render_blank, prompt="选择: ", read=_reader(["z", None]))
        assert "无效选择" in capsys.readouterr().out


class TestNavFeedbackAndFilterGuards:
    """空清单位置反馈静默、筛选读取的 EOF 兜底。"""

    def test_nav_feedback_silent_on_empty_items(self, capsys):
        """无项时不打印位置反馈（避免空面板出现 ▸ 提示行）。"""
        _emit_nav_feedback(NavState(count=0), [])
        assert capsys.readouterr().out == ""

    def test_panel_filter_returns_on_eof(self, capsys):
        """筛选行输入抛 EOFError 时保持原筛选并返回。"""
        nav = NavState(count=2, cursor=1)
        nav.apply_filter([0], keyword="甲")

        def _eof(_prompt: str) -> str:
            raise EOFError

        _apply_panel_filter(nav, [PanelItem("1", "甲"), PanelItem("2", "乙")], _eof)
        assert nav.keyword == "甲"
        assert nav.cursor == 0
        capsys.readouterr()


class TestTextLayoutNarrowGuards:
    """列宽非正时的降级口径。"""

    def test_wrap_display_zero_columns_returns_single_line(self):
        """columns≤0 时 wrap_display 原样返回单行（不抛异常、不切字）。"""
        assert text_layout.wrap_display("甲乙丙", 0) == ["甲乙丙"]

    def test_truncate_display_zero_columns_returns_empty(self):
        """columns≤0 时 truncate_display 返回空串（窄到不可显示的极端档）。"""
        assert text_layout.truncate_display("甲乙丙", 0) == ""

    def test_truncate_display_budget_exhausted_by_ellipsis(self):
        """省略号自身宽度吃掉全部列宽时返回空串而非超宽串。"""
        assert text_layout.truncate_display("abcdef", 1) == ""


class TestAsciiStreamFlushAndInstall:
    """ASCII 代理的 flush 透传与 stdout 就地替换。"""

    def test_flush_passes_through(self):
        """``AsciiStream.flush`` 作用于被代理流。"""
        buf = io.StringIO()
        wrapper = sym_mod.AsciiStream(buf)
        buf.write("残留")
        wrapper.flush()
        assert buf.getvalue() == "残留"

    def test_install_ascii_stream_replaces_stdout(self, monkeypatch):
        """请求 ASCII 降级且未指定流时，代理装到 ``sys.stdout``。"""
        buf = io.StringIO()
        monkeypatch.setenv("TUI_ASCII", "1")
        monkeypatch.setattr("sys.stdout", buf)
        installed = sym_mod.install_ascii_stream()
        assert isinstance(installed, sym_mod.AsciiStream)
        installed.write("…")
        assert buf.getvalue() == "~"
