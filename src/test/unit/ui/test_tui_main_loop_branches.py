"""TUI 主入口（`tui/tui`）主循环的非交互分支：启动降级、游标夹紧、筛选态导航、`__main__` 收尾。

锁住的契约：
  - 启动期的缓存清理 / 隐私提示 / 首次引导都是「非关键」步骤——失败只记日志，绝不阻断进菜单；
  - 首页筛选态下直达键按不到被隐藏项时给一行可观察反馈（不静默吞键），方向键与回车只在
    命中项之间移动（游标不落到隐藏项上）；
  - 门控裁剪后游标越界要被夹回首项（否则下一帧取不到项）；
  - `python -m src.python.tui.tui` 直接运行时 Ctrl+C 打印告别语并以 0 退出。
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

from src.python.tui import tui as tui_mod
from src.python.tui.panel_runtime import NavState
from src.python.tui.tui_keys import KEY_CTRL_C, KEY_DOWN, KEY_ENTER
from src.python.tui.tui_menu import MENU_ITEMS, _apply_feature_gates, index_by_key, match_menu_items

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _noop(*_args, **_kwargs) -> None:
    return None


class _Harness:
    """一次 main() 驱动的观测面：退出、执行项、逐帧游标、标准输出。"""

    def __init__(self) -> None:
        self.fired: list[str] = []
        self.executed: list[int] = []
        self.cursors: list[int] = []

    @property
    def renders(self) -> int:
        return len(self.cursors)


def _run_main(
    monkeypatch,
    keys: list[str],
    *,
    filter_keyword: str | None = None,
    privacy=None,
    wizard=None,
    cleanup=None,
    nav_cursor: int | None = None,
    default_key: str | None = None,
) -> _Harness:
    """驱动真实 `main()`：只替换输入、退出、菜单项执行与渲染观测点。"""
    _apply_feature_gates()  # 先把 MENU_ITEMS 复位成当前开关下的母本，避免跨用例残留
    harness = _Harness()
    seq = iter(keys)

    def _fake_key() -> str:
        try:
            return next(seq)
        except StopIteration:
            raise SystemExit from None

    def _fake_exit() -> None:
        harness.fired.append("exit")
        raise SystemExit

    def _fake_render(cursor: int, _menu_filter: str) -> list[str]:
        harness.cursors.append(cursor)
        return [f"帧 {cursor}"]

    monkeypatch.setattr(tui_mod, "get_key", _fake_key)
    monkeypatch.setattr(tui_mod, "exit_app", _fake_exit)
    monkeypatch.setattr(tui_mod, "init_config", _noop)
    monkeypatch.setattr(tui_mod, "_apply_feature_gates", _noop)
    monkeypatch.setattr(tui_mod, "_bind_callbacks", _noop)
    monkeypatch.setattr(tui_mod, "execute_item", harness.executed.append)
    monkeypatch.setattr(tui_mod, "_render_menu_frame", _fake_render)
    monkeypatch.setattr(tui_mod, "_clear_last_frame", _noop)
    monkeypatch.setattr("src.python.cache.cleanup_expired", cleanup or (lambda **_kw: 0))
    monkeypatch.setattr("src.python.report.privacy_notice.show_privacy_notice_if_needed", privacy or _noop)
    monkeypatch.setattr("src.python.startup_wizard.show_startup_wizard_if_needed", wizard or _noop)
    if filter_keyword is not None:
        monkeypatch.setattr(tui_mod, "_ask_menu_filter", lambda _current: filter_keyword)
    if default_key is not None:
        config = {"default_menu_key": default_key}
        monkeypatch.setattr("src.python.config.get_config", lambda: config)
    if nav_cursor is not None:
        monkeypatch.setattr(tui_mod, "NavState", lambda count, cursor: NavState(count=count, cursor=nav_cursor))

    with pytest.raises(SystemExit):
        tui_mod.main()
    return harness


class TestStartupDegrades:
    def test_cache_cleanup_logs_removed_count(self, monkeypatch, caplog):
        """启动清理有产出时记 INFO（用户可从日志确认清理生效），并照常进菜单。"""
        with caplog.at_level("INFO"):
            harness = _run_main(monkeypatch, ["0"], cleanup=lambda **_kw: 4)

        assert harness.fired == ["exit"]
        assert harness.renders >= 1
        assert "过期缓存文件" in caplog.text

    def test_cache_cleanup_failure_only_warns(self, monkeypatch, caplog):
        """清理抛 OSError（缓存目录不可写）→ 只 WARNING，不阻断启动。"""

        def _broken(**_kw) -> int:
            raise OSError("cache dir readonly")

        with caplog.at_level("WARNING"):
            harness = _run_main(monkeypatch, ["0"], cleanup=_broken)

        assert harness.fired == ["exit"]
        assert "启动时缓存清理失败" in caplog.text

    def test_privacy_notice_failure_does_not_block(self, monkeypatch):
        """隐私提示抛错 → 吞掉继续（首次提示是辅助步骤，不能让程序起不来）。"""

        def _broken() -> None:
            raise RuntimeError("privacy notice crashed")

        harness = _run_main(monkeypatch, ["0"], privacy=_broken)

        assert harness.fired == ["exit"]
        assert harness.renders >= 1

    def test_startup_wizard_failure_does_not_block(self, monkeypatch):
        def _broken() -> None:
            raise RuntimeError("wizard crashed")

        harness = _run_main(monkeypatch, ["0"], wizard=_broken)

        assert harness.fired == ["exit"]
        assert harness.renders >= 1


class TestCursorClamp:
    def test_cursor_beyond_count_is_clamped_to_first(self, monkeypatch):
        """门控裁剪后原游标越界 → 夹回首项再渲染（否则取不到项直接 IndexError）。"""
        harness = _run_main(monkeypatch, ["0"], nav_cursor=len(MENU_ITEMS) + 5)

        assert harness.cursors[0] == 0
        assert harness.fired == ["exit"]


class TestCtrlCExit:
    def test_ctrl_c_exits_from_menu(self, monkeypatch):
        """首页 Ctrl+C = 退出（与 Esc×2 / 0 / X 同一收束点）。"""
        harness = _run_main(monkeypatch, [KEY_CTRL_C])

        assert harness.fired == ["exit"]


class TestFilteredDirectKey:
    def test_hidden_item_key_gives_feedback_and_keeps_frame(self, monkeypatch, capsys):
        """筛选态下按到被隐藏项的键 → 一行提示（含改关键词与清筛选两条出路），不执行该项。"""
        _apply_feature_gates()
        keyword = "报告"
        visible = match_menu_items(keyword)
        hidden = [item[0] for index, item in enumerate(MENU_ITEMS) if index not in visible]
        assert visible and hidden, "前置：该关键词下必须同时存在可见项与隐藏项"

        harness = _run_main(monkeypatch, ["/", hidden[0], "0", "0"], filter_keyword=keyword)

        out = capsys.readouterr().out
        assert harness.executed == [], "被隐藏项不得被执行"
        assert f"「{hidden[0]}」不在当前筛选结果中" in out
        assert "0 清除筛选" in out, "提示须给出清除筛选的键位"

    def test_zero_clears_filter_before_exit(self, monkeypatch, capsys):
        """筛选态下按 0 先清筛选（不直接退出），再按 0 才退出。"""
        _apply_feature_gates()
        harness = _run_main(monkeypatch, ["/", "0", "0"], filter_keyword="报告")

        assert harness.fired == ["exit"]
        assert harness.renders >= 3, "清筛选后须重绘一帧"
        assert "已清除筛选" in capsys.readouterr().out


class TestFilteredNavigation:
    @staticmethod
    def _hidden_default_key(keyword: str) -> tuple[str, list[int]]:
        _apply_feature_gates()
        visible = match_menu_items(keyword)
        hidden = [item[0] for index, item in enumerate(MENU_ITEMS) if index not in visible]
        assert visible and hidden, "前置：该关键词下必须同时存在可见项与隐藏项"
        return hidden[0], visible

    def test_enter_moves_cursor_to_first_match(self, monkeypatch):
        """筛选态下回车先把游标移到最近命中项再执行（不执行隐藏项）。"""
        keyword = "报告"
        hidden_key, visible = self._hidden_default_key(keyword)

        harness = _run_main(monkeypatch, ["/", KEY_ENTER, "0", "0"], filter_keyword=keyword, default_key=hidden_key)

        assert harness.executed, "回车须执行（移到命中项后）"
        assert harness.executed[0] in visible

    def test_down_arrow_moves_between_matches(self, monkeypatch):
        """筛选态方向键只在命中项之间移动：下一帧游标必为另一个命中项。"""
        keyword = "报告"
        hidden_key, visible = self._hidden_default_key(keyword)
        assert len(visible) >= 2, "前置：该关键词至少命中两项才能验证「在命中项间移动」"

        harness = _run_main(monkeypatch, ["/", KEY_DOWN, "0", "0"], filter_keyword=keyword, default_key=hidden_key)

        final_cursor = harness.cursors[-1]
        assert final_cursor in visible
        assert final_cursor != harness.cursors[0], "方向键须真正移动游标（不留在隐藏项上）"


class TestMainGuard:
    def test_keyboard_interrupt_prints_farewell_and_exits_zero(self, monkeypatch, capsys):
        """直接运行入口（`__main__`）时 Ctrl+C → 打印告别语并以退出码 0 结束。

        顺带覆盖「项目根不在 sys.path」时的自动补路径（直接执行脚本的现场）。
        """
        root = Path(tui_mod.__file__).resolve().parents[3]
        saved = list(sys.path)

        def _interrupt() -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr("src.python.core.doctor.interpreter_preflight_error", _interrupt)
        sys.path[:] = [entry for entry in sys.path if Path(entry).resolve() != root]
        try:
            with pytest.raises(SystemExit) as exc:
                runpy.run_path(tui_mod.__file__, run_name="__main__")
        finally:
            sys.path[:] = saved

        assert exc.value.code == 0
        assert "感谢使用，再见！" in capsys.readouterr().out


def test_default_menu_key_lands_on_matching_item(monkeypatch):
    """配置里的 default_menu_key 决定首帧游标（E/B/L/… 首屏选中项即上次常用项）。"""
    _apply_feature_gates()
    key = MENU_ITEMS[-2][0]
    expected = index_by_key(key)
    assert expected is not None

    harness = _run_main(monkeypatch, ["0"], default_key=key)

    assert harness.cursors[0] == expected
