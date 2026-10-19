"""TUI 统一交互运行时（panel_runtime）单元测试。

覆盖设计 §3.6 退出/取消语义矩阵与运行时动作表：方向键游标回绕、Enter 防误触、
直达键游标同步不置 engaged、Esc 返回、pick 收集、on_text 词法、无效反馈单源。
read 注入用可控桩，不依赖真实终端。
"""

from __future__ import annotations

from typing import Callable

import pytest

from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
from src.python.tui.tui_keys import KEY_DOWN, KEY_UP

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _reader(sequence: list[str | None]) -> Callable[..., str | None]:
    """可控行输入桩：按序弹出预设输入（None 模拟 Esc）；忽略 arrows 参数。"""
    it = iter(sequence)

    def _read(prompt: str, arrows: bool = False) -> str | None:  # noqa: ARG001
        return next(it, None)

    return _read


def _simple_items(calls: list[str]) -> list[PanelItem]:
    """三项 + 一 return 项的样例清单，动作记录被调 key。"""
    return [
        PanelItem("1", "甲", action=lambda: calls.append("1")),
        PanelItem("2", "乙", action=lambda: calls.append("2")),
        PanelItem("3", "丙", action=lambda: calls.append("3")),
        PanelItem("0", "返回", kind="return"),
    ]


def _render_blank(nav: NavState) -> list[str]:
    return ["<frame>"]


class TestNavState:
    """NavState 游标语义：回绕、engaged、marker、同步不置 engaged。"""

    def test_move_down_wraps_and_engages(self):
        nav = NavState(count=3)
        assert nav.move(KEY_DOWN) is True
        assert nav.cursor == 1 and nav.engaged is True
        nav.move(KEY_DOWN)
        nav.move(KEY_DOWN)  # 回绕
        assert nav.cursor == 0

    def test_move_up_wraps_to_last(self):
        nav = NavState(count=3, cursor=0)
        assert nav.move(KEY_UP) is True
        assert nav.cursor == 2 and nav.engaged is True

    def test_move_empty_list_returns_false(self):
        nav = NavState(count=0)
        assert nav.move(KEY_DOWN) is False
        assert nav.engaged is False

    def test_sync_does_not_engage(self):
        nav = NavState(count=5)
        nav.sync(3)
        assert nav.cursor == 3 and nav.engaged is False, "直达同步游标但不进入导航态"

    def test_marker_only_when_engaged_and_current(self):
        nav = NavState(count=3)
        assert nav.marker(0) == " ", "未导航不显 ▸"
        nav.engage(1)
        assert nav.marker(1) == "▸"
        assert nav.marker(0) == " ", "非当前行不显 ▸"


class TestPanelLoopDispatch:
    """派发主链路：直达键、Enter 防误触、Esc 返回、return 项退出。"""

    def test_direct_key_dispatches_and_syncs_cursor(self):
        calls: list[str] = []
        panel_loop(
            _simple_items(calls),
            render=_render_blank,
            prompt="> ",
            read=_reader(["2", "0"]),
        )
        assert calls == ["2"], "键入直达派发对应项"

    def test_letter_key_case_insensitive(self):
        calls: list[str] = []
        items = [
            PanelItem("C", "持仓", action=lambda: calls.append("C")),
            PanelItem("B", "返回", kind="return"),
        ]
        panel_loop(items, render=_render_blank, prompt="> ", read=_reader(["c", "B"]))
        assert calls == ["C"], "小写键命中大写项（大小写不敏感）"

    def test_enter_without_navigation_uses_default_key(self):
        calls: list[str] = []
        panel_loop(
            _simple_items(calls),
            render=_render_blank,
            prompt="> ",
            read=_reader(["", "0"]),
            default_key="1",
        )
        assert calls == ["1"], "未导航裸回车派发 default_key"

    def test_enter_without_navigation_no_default_goes_on_text(self):
        seen: list[str] = []
        panel_loop(
            _simple_items([]),
            render=_render_blank,
            prompt="> ",
            read=_reader(["", "0"]),
            on_text=seen.append,
        )
        assert seen == [""], "无 default_key 时裸回车交 on_text（空串）"

    def test_enter_without_navigation_invalid_feedback(self, capsys):
        panel_loop(
            _simple_items([]),
            render=_render_blank,
            prompt="> ",
            read=_reader(["", "0"]),
        )
        assert "无效选择" in capsys.readouterr().out, "无 on_text/default 时统一无效反馈"

    def test_escalways_returns(self):
        calls: list[str] = []
        panel_loop(_simple_items(calls), render=_render_blank, prompt="> ", read=_reader([None]))
        assert calls == [], "Esc 不派发任何项"

    def test_return_item_action_then_exit(self):
        calls: list[str] = []
        items = [
            PanelItem("1", "甲", action=lambda: calls.append("1")),
            PanelItem("0", "返回", kind="return", action=lambda: calls.append("ret")),
        ]
        panel_loop(items, render=_render_blank, prompt="> ", read=_reader(["0"]))
        assert calls == ["ret"], "return 项先执行动作再退出循环"


class TestPanelLoopNav:
    """方向键导航：Enter 派发选中项、feedback 单行反馈、on_nav_moved 回调。"""

    def test_arrow_then_enter_dispatches_selected(self):
        calls: list[str] = []
        panel_loop(
            _simple_items(calls),
            render=_render_blank,
            prompt="> ",
            read=_reader([KEY_DOWN, KEY_DOWN, "", "0"]),  # ↓↓ 到「丙」，Enter 派发
        )
        assert calls == ["3"], "导航后 Enter 按选中项派发"

    def test_arrow_up_wraps_then_enter(self):
        calls: list[str] = []
        items = [
            PanelItem("1", "甲", action=lambda: calls.append("1")),
            PanelItem("2", "乙", action=lambda: calls.append("2")),
            PanelItem("3", "丙", action=lambda: calls.append("3")),
        ]
        panel_loop(
            items,
            render=_render_blank,
            prompt="> ",
            read=_reader([KEY_UP, "", None]),  # ↑ 回绕到「丙」，Enter 派发，Esc 退出
        )
        assert calls == ["3"], "↑ 回绕末项后 Enter 派发末项"

    def test_pure_nav_no_dispatch(self):
        calls: list[str] = []
        panel_loop(
            _simple_items(calls),
            render=_render_blank,
            prompt="> ",
            read=_reader([KEY_DOWN, KEY_UP, "0"]),
        )
        assert calls == [], "纯方向键移动不派发任何动作"

    def test_feedback_repaint_emits_position_and_calls_hook(self, capsys):
        moved: list[bool] = []
        panel_loop(
            _simple_items([]),
            render=_render_blank,
            prompt="> ",
            read=_reader([KEY_DOWN, "0"]),
            repaint="feedback",
            on_nav_moved=lambda: moved.append(True),
        )
        out = capsys.readouterr().out
        assert "▸" in out, "feedback 模式方向键给单行位置反馈"
        assert moved == [True], "on_nav_moved 回调触发（供置重绘）"

    def test_on_nav_moved_called_in_loop_mode_too(self):
        """loop 模式也回调 on_nav_moved（S 面板窄档导航后据以强制重绘）。"""
        moved: list[bool] = []
        panel_loop(
            _simple_items([]),
            render=_render_blank,
            prompt="> ",
            read=_reader([KEY_DOWN, "0"]),
            repaint="loop",
            on_nav_moved=lambda: moved.append(True),
        )
        assert moved == [True], "loop 模式方向键同样回调 on_nav_moved"

    def test_direct_sync_does_not_engage_enter_stays_default(self):
        """键入直达后裸回车仍走 default（不误触二次切换）——保各面板原语义。"""
        calls: list[str] = []
        panel_loop(
            _simple_items(calls),
            render=_render_blank,
            prompt="> ",
            read=_reader(["2", "", "0"]),  # 键入 2 派发，裸回车走 default=1
            default_key="1",
        )
        assert calls == ["2", "1"], "直达不置 engaged，裸回车派发 default 而非重派发 2"


class TestPanelLoopTextAndPick:
    """on_text 词法、direct=False、pick 收集、on_picked 回调。"""

    def test_unmatched_goes_on_text(self):
        seen: list[str] = []
        panel_loop(
            _simple_items([]),
            render=_render_blank,
            prompt="> ",
            read=_reader(["k9", "0"]),
            on_text=seen.append,
        )
        assert seen == ["k9"], "未命中项键的多字符交 on_text 词法"

    def test_help_swallowed_by_runtime(self, capsys):
        """``?`` 与 ``?键`` 由运行时承接，不进面板词法（帮助入口全面板可用）。"""
        seen: list[str] = []
        panel_loop(
            _simple_items([]),
            render=_render_blank,
            prompt="> ",
            read=_reader(["?", "?2", "0"]),
            on_text=seen.append,
        )
        out = capsys.readouterr().out
        assert seen == [], "帮助输入不得落进面板词法"
        assert "可用键：" in out, "? 无参须印本面板可用键一览"

    def test_panel_help_hook_takes_precedence(self, capsys):
        """面板提供 on_help 时优先自处理；返回 False 表示交回运行时通用一览。"""
        handled: list[str] = []

        def _on_help(target: str) -> bool:
            handled.append(target)
            return False

        panel_loop(
            _simple_items([]),
            render=_render_blank,
            prompt="> ",
            read=_reader(["?", "?1", "0"]),
            on_help=_on_help,
        )
        out = capsys.readouterr().out
        assert handled == ["", "1"], f"on_help 应收到去问号目标: {handled}"
        assert "可用键：" in out, "on_help 返回 False 时回落通用一览"

    def test_direct_false_routes_char_to_on_text(self):
        seen: list[str] = []
        items = [PanelItem("1", "甲"), PanelItem("0", "返回", kind="return")]
        panel_loop(
            items,
            render=_render_blank,
            prompt="> ",
            read=_reader(["1 2", "0"]),  # direct=False 时「1」不直达，整串交 on_text
            direct=False,
            on_text=seen.append,
        )
        assert seen == ["1 2"], "direct=False 时数字进 on_text 组双编号词法"

    def test_pick_collects_two_then_on_picked(self):
        picked: list[tuple[str, ...]] = []
        items = [
            PanelItem("1", "甲"),
            PanelItem("2", "乙"),
            PanelItem("3", "丙"),
            PanelItem("0", "返回", kind="return"),
        ]
        panel_loop(
            items,
            render=_render_blank,
            prompt="> ",
            # ↓ 到「乙」Enter 收集 → ↓ 到「丙」Enter 收满 → on_picked → 「0」退出
            read=_reader([KEY_DOWN, "", KEY_DOWN, "", "0"]),
            direct=False,
            pick=2,
            on_picked=picked.append,
        )
        assert picked == [("2", "3")], "导航两次 Enter 收满 2 项触发 on_picked"

    def test_pick_return_item_exits_without_collect(self):
        picked: list[tuple[str, ...]] = []
        items = [
            PanelItem("1", "甲"),
            PanelItem("0", "返回", kind="return"),
        ]
        panel_loop(
            items,
            render=_render_blank,
            prompt="> ",
            read=_reader(["0"]),
            direct=False,
            pick=2,
            on_picked=picked.append,
        )
        assert picked == [], "pick 模式下 return 项直接退出不收集"

    def test_pick_progress_feedback(self, capsys):
        items = [PanelItem("1", "甲"), PanelItem("2", "乙"), PanelItem("0", "返回", kind="return")]
        panel_loop(
            items,
            render=_render_blank,
            prompt="> ",
            read=_reader([KEY_DOWN, "", "0"]),  # ↓ 到「乙」Enter 收集一项（未满）→「0」退出
            direct=False,
            pick=2,
            on_picked=lambda _t: None,
        )
        assert "已选" in capsys.readouterr().out, "pick 未满时给进度反馈"


class TestPanelLoopExceptions:
    """退出/异常语义矩阵：Ctrl+C/EOF/render 异常原样上抛，运行时不吞。"""

    def test_read_eof_propagates(self):
        def _boom(prompt: str, arrows: bool = False) -> str | None:  # noqa: ARG001
            raise EOFError

        with pytest.raises(EOFError):
            panel_loop(_simple_items([]), render=_render_blank, prompt="> ", read=_boom)

    def test_read_keyboard_interrupt_propagates(self):
        def _boom(prompt: str, arrows: bool = False) -> str | None:  # noqa: ARG001
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            panel_loop(_simple_items([]), render=_render_blank, prompt="> ", read=_boom)

    def test_render_exception_propagates(self):
        def _bad_render(nav: NavState) -> list[str]:
            raise RuntimeError("render 失败")

        with pytest.raises(RuntimeError):
            panel_loop(_simple_items([]), render=_bad_render, prompt="> ", read=_reader(["0"]))

    def test_action_exception_propagates(self):
        def _boom() -> None:
            raise ValueError("动作失败")

        items = [PanelItem("1", "甲", action=_boom)]
        with pytest.raises(ValueError):
            panel_loop(items, render=_render_blank, prompt="> ", read=_reader(["1"]))


class TestPanelLoopRender:
    """渲染回调：每轮重建、None 行按空行打印。"""

    def test_render_receives_nav_and_prints_rows(self, capsys):
        seen: list[int] = []

        def _render(nav: NavState) -> list[str | None]:
            seen.append(nav.cursor)
            return ["行A", None, "行B"]

        panel_loop(_simple_items([]), render=_render, prompt="> ", read=_reader([KEY_DOWN, "0"]))
        out = capsys.readouterr().out
        assert "行A" in out and "行B" in out
        assert "" in out.splitlines(), "None 行按空行打印"
        assert len(seen) == 2, "方向键移动后回到循环顶重建渲染"
