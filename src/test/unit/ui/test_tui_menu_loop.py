"""test_tui_menu 兄弟分片（loop）：主循环退出通道与窄屏直达导航。"""

from __future__ import annotations
import unittest
from unittest.mock import MagicMock, patch
from src.python.tui.tui_menu import (
    MENU_ITEMS,
)
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestMainLoopExitKeys(unittest.TestCase):
    """首页退出通道：`X`（显式退出项）与 `0`（退出别名）都退出、其它键不误退。"""

    """首页退出通道：`X`（显式退出项）与 `0`（退出别名）都退出；其它键不误退。"""

    @staticmethod
    def _drive(keys: list[str]) -> tuple[list[str], str]:
        """驱动真实 main() 循环：返回（退出回调触发记录, 打印内容）。"""
        import contextlib
        import io

        import src.python.tui.tui as tui_mod
        import src.python.tui.tui_menu as menu_mod

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

        out = io.StringIO()
        with (
            patch.object(tui_mod, "get_key", _fake_key),
            patch.object(tui_mod, "exit_app", _fake_exit),
            patch.object(menu_mod, "exit_app", _fake_exit),
            patch.object(tui_mod, "init_config"),
            patch.object(tui_mod, "_apply_feature_gates"),
            patch.object(tui_mod, "_bind_callbacks"),
            patch.object(tui_mod, "print_header"),
            patch.object(tui_mod, "show_config"),
            patch.object(tui_mod, "render_menu"),
        ):
            try:
                with contextlib.redirect_stdout(out):
                    tui_mod.main()
            except SystemExit:
                pass
        return fired, out.getvalue()

    def test_zero_key_exits(self):
        """按 0 → 退出（与子菜单「0 = 返回」的习惯一致，首页返回即退出程序）。"""
        fired, _ = self._drive(["0"])
        self.assertEqual(fired, ["exit"])

    def test_upper_x_exits_via_menu_item(self):
        """按 X → 命中 [X] 退出项。"""
        fired, _ = self._drive(["X"])
        self.assertEqual(fired, ["exit"])

    def test_non_exit_key_does_not_exit(self):
        """按未映射键（如 Z）不退出（按键无效但不误退）。"""
        fired, _ = self._drive(["Z"])
        self.assertEqual(fired, [])

    def test_footer_documents_both_exit_keys(self):
        """页脚同时写出 `Esc`、`0` 与 `X` 都能退出，否则用户无从发现退出别名。"""
        import contextlib
        import io

        from src.python.tui.tui_menu import render_menu

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            render_menu(0)
        footer = buf.getvalue()
        self.assertIn("Esc / 0 / X 退出", footer)
        self.assertIn("Ctrl+C 退出", footer)

    def test_exit_item_label_mentions_zero_alias(self):
        """退出项标签本身也点明 `0 亦可`——光标停在该项时就能看到，不必只看页脚。"""

        exit_items = [item for item in MENU_ITEMS if item[3]]
        self.assertEqual(len(exit_items), 1)
        self.assertIn("0 亦可", exit_items[0][1])

    def test_footer_wraps_within_terminal_width(self):
        """窄屏（手机）页脚按可用宽度折行：不硬折、不越界，续行缩进对齐。"""
        import contextlib
        import io

        from src.python.tui.text_layout import display_width
        from src.python.tui.tui_menu import render_menu

        for columns in (40, 46, 60):
            buf = io.StringIO()
            with (
                patch.dict("os.environ", {"COLUMNS": str(columns)}),
                patch("os.get_terminal_size", side_effect=OSError()),
                contextlib.redirect_stdout(buf),
            ):
                render_menu(0)
            for line in buf.getvalue().splitlines():
                self.assertLessEqual(display_width(line), columns, (columns, line))


class TestRenderMenuNarrowDirect(unittest.TestCase):
    """首页菜单两档渲染：narrow 直达+导航并存（选中态 + 双提示页脚）/ 宽中档导航。"""

    @staticmethod
    def _render(columns: int) -> str:
        import contextlib
        import io

        from src.python.tui.tui_menu import render_menu

        buf = io.StringIO()
        with (
            patch.dict("os.environ", {"COLUMNS": str(columns)}),
            patch("os.get_terminal_size", side_effect=OSError()),
            contextlib.redirect_stdout(buf),
        ):
            render_menu(1)
        return buf.getvalue()

    def test_narrow_renders_selection_indicator(self):
        """narrow（40 列）同样渲染 `>` 选中指示器——方向键导航在窄屏可用。"""
        out = self._render(40)
        self.assertIn(">", out)

    def test_narrow_footer_documents_direct_and_nav_keys(self):
        """narrow 页脚同时写明直达与导航路径及退出键（40 列折行，按逻辑内容断言）。"""
        out = self._render(40)
        footer = " ".join(out.split("窄屏直达", 1)[1].split())
        self.assertIn("窄屏直达", out)
        self.assertIn("↑↓/j k 选择", footer)
        self.assertIn("回车执行", footer)
        self.assertIn("Esc / 0 /", footer)
        self.assertIn("X 退出", footer)
        self.assertIn("Ctrl+C 退出", footer)
        self.assertNotIn("↑↓ 移动", out)

    def test_wide_keeps_selection_indicator_and_nav_footer(self):
        """宽屏（100 列）保留 `>` 选中态与方向键页脚（导航主路径不变）。"""
        out = self._render(100)
        self.assertIn(">", out)
        self.assertIn("↑↓/j k 移动", out)
        self.assertIn("Esc / 0 / X 退出", out)


class TestNarrowMainLoopDirectNav(unittest.TestCase):
    """narrow 档主循环：直达键零重绘主路径不变；方向键/Enter 导航可用
    （非 TTY 回退整屏追加，TTY 原地重绘不滚屏）。"""

    @staticmethod
    def _drive(keys: list[str], columns: int, *, tty: bool = False):
        """驱动真实 main()：返回（退出记录, render_menu 次数, execute_item 参数, stdout, 清帧 spy）。"""
        import contextlib
        import io

        import src.python.tui.tui as tui_mod
        import src.python.tui.tui_menu as menu_mod

        fired: list[str] = []
        executed: list[int] = []
        seq = iter(keys)

        def _fake_key() -> str:
            try:
                return next(seq)
            except StopIteration:
                raise SystemExit from None

        def _fake_exit() -> None:
            fired.append("exit")
            raise SystemExit

        def _fake_execute(idx: int) -> None:
            executed.append(idx)

        render_mock = MagicMock()
        clear_mock = MagicMock()
        buf = io.StringIO()
        if tty:
            buf.isatty = lambda: True  # 模拟交互终端以走窄屏原地重绘分支
        with (
            patch.object(tui_mod, "get_key", _fake_key),
            patch.object(tui_mod, "exit_app", _fake_exit),
            patch.object(menu_mod, "exit_app", _fake_exit),
            patch.object(tui_mod, "terminal_columns", return_value=columns),
            patch.object(tui_mod, "init_config"),
            patch.object(tui_mod, "_apply_feature_gates"),
            patch.object(tui_mod, "_bind_callbacks"),
            patch.object(tui_mod, "execute_item", _fake_execute),
            patch.object(tui_mod, "print_header"),
            patch.object(tui_mod, "show_config"),
            patch.object(tui_mod, "render_menu", render_mock),
            patch.object(tui_mod, "_clear_last_frame", clear_mock),
        ):
            try:
                with contextlib.redirect_stdout(buf):
                    tui_mod.main()
            except SystemExit:
                pass
        return fired, render_mock.call_count, executed, buf.getvalue(), clear_mock

    def test_narrow_nav_keys_move_selection_and_rerender(self):
        """窄屏（40 列）方向键移动选中态并重绘（非 TTY 回退整屏追加）；未登记字母零重绘。"""
        fired, renders, executed, _, _ = self._drive(["KEY_DOWN", "KEY_UP", "Z", "0"], columns=40)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(executed, [])
        self.assertEqual(renders, 3, "初帧 + 方向键两帧；未登记字母不重绘")

    def test_narrow_enter_executes_selected(self):
        """窄屏 Enter 执行当前选中项（与宽/中档一致的导航确认语义）。"""
        import src.python.tui.tui_menu as menu_mod

        fired, renders, executed, _, _ = self._drive(["KEY_ENTER", "0"], columns=40)
        sel_default = [i for i, (key, *_rest) in enumerate(menu_mod.MENU_ITEMS) if key == "L"][0]
        self.assertEqual(executed, [sel_default], "Enter 执行默认选中项（缺省键 L）")
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)

    def test_narrow_arrow_inplace_repaint_on_tty(self):
        """TTY 窄屏方向键走原地重绘分支：清帧助手被调用，仍在内层循环（不追加新屏）。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=40, tty=True)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2, "初帧 + 原地重绘一帧（不追加新屏）")
        cleared.assert_called_once()

    def test_narrow_arrow_fallback_without_ansi(self):
        """非 TTY（管道/测试）窄屏方向键回退整屏追加：清帧助手不被调用、重绘计数正确。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=40, tty=False)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)
        cleared.assert_not_called()

    def test_clear_last_frame_writes_ansi(self):
        """清帧助手：n>0 输出光标上移 n 行 + 清屏至末尾；n=0 不输出。"""
        import contextlib
        import io as _io

        import src.python.tui.tui as tui_mod

        buf = _io.StringIO()
        with contextlib.redirect_stdout(buf):
            tui_mod._clear_last_frame(5)
            tui_mod._clear_last_frame(0)
        self.assertEqual(buf.getvalue(), "\x1b[5A\x1b[0J")

    def test_wide_arrow_key_rerenders(self):
        """宽屏（100 列）方向键仍走导航主路径：每按一次重绘一屏（整屏追加，不走原地重绘）。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=100)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2, "宽屏方向键移动选中态后重绘")
        cleared.assert_not_called()

    def test_esc_double_press_exits(self):
        """Esc 连按两次（3 秒窗口内）→ 退出（首按给确认提示，不立即退出）。"""
        fired, _, _, _, _ = self._drive(["KEY_ESC", "KEY_ESC"], columns=100)
        self.assertEqual(fired, ["exit"])

    def test_esc_single_press_shows_confirm_hint(self):
        """单次 Esc 不退出：输出「再按一次」确认提示（方向键拆包误判不致退出）。"""
        fired, renders, _, out, _ = self._drive(["KEY_ESC", "0"], columns=100)
        self.assertEqual(fired, ["exit"])
        self.assertIn("再按一次 Esc 退出", out)
        self.assertEqual(renders, 1, "提示不触发整屏重绘")

    def test_esc_armed_cancelled_by_navigation_key(self):
        """任何非 Esc 按键解除退出确认态：孤 Esc 挂起的确认不被后续按键引爆。"""
        fired, _, _, out, _ = self._drive(["KEY_ESC", "KEY_DOWN", "KEY_ESC", "0"], columns=100)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(out.count("再按一次 Esc 退出"), 2, "两次独立 Esc 首按（确认态已被方向键解除）")

    def test_wide_arrow_inplace_repaint_on_tty(self):
        """宽屏 TTY 方向键同样原地重绘：宽/窄导航手感一致，不滚屏堆积。"""
        fired, renders, _, _, cleared = self._drive(["KEY_DOWN", "0"], columns=100, tty=True)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)
        cleared.assert_called_once()

    def test_hint_lines_included_in_inplace_clear(self):
        """反馈行并入原地重绘清除范围：清帧调用 = 帧行数 + 反馈行数（防清帧错位）。"""
        fired, renders, _, out, cleared = self._drive(["KEY_ESC", "KEY_DOWN", "0"], columns=40, tty=True)
        self.assertEqual(fired, ["exit"])
        self.assertEqual(renders, 2)
        cleared.assert_called_once_with(1)  # 渲染器 mock 帧行数 0 + Esc 提示 1 行


class TestTierSemanticParity(unittest.TestCase):
    """守护「分档只改版式不改语义」（架构设计约束·TUI 分档条目）：同一按键在窄/宽两档产生
    相同的语义动作与可观察反馈——分档至多改变呈现方式（原地重绘 vs 整屏追加、
    单行提示 vs 重绘一屏），不得删改按键语义或反馈本身。"""

    _drive = staticmethod(TestNarrowMainLoopDirectNav._drive)

    def test_registered_letter_parity(self):
        """登记字母键：两档执行同一菜单项（语义不随宽度漂移）。"""
        narrow = self._drive(["C", "0"], columns=40)
        wide = self._drive(["C", "0"], columns=100)
        self.assertEqual(narrow[2], wide[2], "执行同一选中项")
        self.assertTrue(narrow[2], "确实执行了 [C]")

    def test_enter_and_nav_parity(self):
        """方向键 + Enter：两档执行同一选中项。"""
        narrow = self._drive(["KEY_DOWN", "KEY_ENTER", "0"], columns=40)
        wide = self._drive(["KEY_DOWN", "KEY_ENTER", "0"], columns=100)
        self.assertEqual(narrow[2], wide[2], "↓ 后 Enter 执行同一项")
        self.assertTrue(narrow[2])

    def test_unregistered_letter_feedback_both_tiers(self):
        """未登记字母：两档都是一行反馈、帧保持不动（不靠重绘当反馈）。"""
        narrow = self._drive(["Z", "0"], columns=40)
        wide = self._drive(["Z", "0"], columns=100)
        self.assertIn("未登记", narrow[3], "窄屏未登记键须有单行反馈")
        self.assertIn("未登记", wide[3], "宽档未登记键须有单行反馈")
        self.assertEqual((narrow[1], wide[1]), (1, 1), "两档均只渲染初帧（按错键不重绘）")

    def test_unknown_key_feedback_both_tiers(self):
        """未知键（KEY_RIGHT）：两档都是一行提示、帧保持不动。"""
        narrow = self._drive(["KEY_RIGHT", "0"], columns=40)
        wide = self._drive(["KEY_RIGHT", "0"], columns=100)
        self.assertIn("未识别按键", narrow[3], "窄屏未知键须有单行反馈")
        self.assertIn("未识别按键", wide[3], "宽档未知键须有单行反馈")
        self.assertEqual((narrow[1], wide[1]), (1, 1), "两档均只渲染初帧（按错键不重绘）")

    def test_esc_exit_parity(self):
        """Esc 连按两次退出：两档一致。"""
        narrow = self._drive(["KEY_ESC", "KEY_ESC"], columns=40)
        wide = self._drive(["KEY_ESC", "KEY_ESC"], columns=100)
        self.assertEqual(narrow[0], ["exit"])
        self.assertEqual(wide[0], ["exit"])


class TestNavKeyAliases(unittest.TestCase):
    """`j`/`k` 与 ↓/↑ 等价（主菜单同一套别名，不改击键数）。"""

    _drive = staticmethod(TestNarrowMainLoopDirectNav._drive)

    def test_j_equals_down_arrow(self):
        """`j` + Enter 与 ↓ + Enter 派发同一项。"""
        via_j = self._drive(["j", "KEY_ENTER", "0"], columns=100)
        via_arrow = self._drive(["KEY_DOWN", "KEY_ENTER", "0"], columns=100)
        self.assertEqual(via_j[2], via_arrow[2], "j 未等价于 ↓")
        self.assertTrue(via_j[2], "确实派发了一项")

    def test_k_equals_up_arrow(self):
        """`k` + Enter 与 ↑ + Enter 派发同一项（含回绕到末项）。"""
        via_k = self._drive(["k", "KEY_ENTER", "0"], columns=100)
        via_arrow = self._drive(["KEY_UP", "KEY_ENTER", "0"], columns=100)
        self.assertEqual(via_k[2], via_arrow[2], "k 未等价于 ↑")
        self.assertTrue(via_k[2])


class TestPlainMode(unittest.TestCase):
    """`TUI_PLAIN=1`：关掉原地重绘，改走整屏追加（日志抓取/朗读场景）。"""

    _drive = staticmethod(TestNarrowMainLoopDirectNav._drive)

    def test_plain_mode_disables_inplace_repaint(self):
        """即使 TTY 可用，纯追加模式下方向键也不触发清帧（改走整屏追加）。"""
        import os
        from unittest.mock import patch as _patch

        with _patch.dict(os.environ, {"TUI_PLAIN": "1"}):
            fired, renders, _executed, _out, cleared = self._drive(["KEY_DOWN", "0"], columns=100, tty=True)
        self.assertEqual(fired, ["exit"])
        cleared.assert_not_called()
        self.assertEqual(renders, 2, "回退整屏追加：初帧 + 一次重绘")
