# -*- coding: utf-8 -*-
"""主菜单版式与管道输出基线（TUI 交互改进批次的「布局不动」护栏）。

为什么需要：主菜单版式（分组、键位、行型、宽窄两档折行、页脚）是用户肌肉记忆
的载体，任何交互改进都不得顺手改动它。本文件把**当前版式逐字节钉住**，并钉住
「管道 / 非 TTY 下不出现 ANSI 控制字符与原地重绘」这一等价性前提——状态条、
分页器一类新控件若在非 TTY 分支漏判，会在这里先红。

两层断言：
  - ``TestMenuLayoutGolden``：``render_menu`` 在宽（90 列）/ 窄（56 列）两档下的
    逐行输出与夹具一致；
  - ``TestPipeOutputClean``：走一条主菜单动线（Esc 两次确认退出），管道输出里
    不得出现 ``\\r`` 与 ESC 序列。

更新方式：确认版式改动是有意为之（并已同步契约与手册）后，运行
``TUI_LAYOUT_UPDATE=1 .venv/bin/python -m pytest src/test/unit/ui/test_tui_layout_baseline.py -q``。
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.test._tui_flow import common_patches, run_flow

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

REPO_ROOT = Path(__file__).resolve().parents[4]
BASELINE_FILE = REPO_ROOT / "src" / "test" / "data" / "fixtures" / "tui_menu_layout_baseline.json"

#: 两档列宽（wide = 宽/中档版式，narrow = 手机竖屏档）；基线按档存档
TIERS: dict[str, int] = {"wide_90": 90, "narrow_56": 56}


def _render_menu_lines(columns: int) -> list[str]:
    """按指定列宽渲染主菜单（首页第一项选中），返回逐行文本。"""
    from src.python.tui import tui_menu
    from src.python.tui import text_layout

    snapshot = list(tui_menu.MENU_ITEMS)
    try:
        tui_menu._apply_feature_gates()  # 与主循环同源裁剪（功能开关默认态）
        out = io.StringIO()
        with patch.object(text_layout, "terminal_columns", return_value=columns):
            with contextlib.redirect_stdout(out):
                tui_menu.render_menu(0)
        return out.getvalue().splitlines()
    finally:
        tui_menu.MENU_ITEMS[:] = snapshot


def _load_baseline() -> dict[str, list[str]]:
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))


@pytest.mark.usefixtures("offline_external_sources")
class TestMenuLayoutGolden:
    """主菜单版式逐行基线（宽 / 窄两档）。"""

    def test_wide_layout_matches_baseline(self):
        """宽档 90 列版式逐行一致（分组顺序、键位、选中标记、页脚）。"""
        expected = _load_baseline()["wide_90"]
        assert _render_menu_lines(TIERS["wide_90"]) == expected

    def test_narrow_layout_matches_baseline(self):
        """窄档 56 列版式逐行一致（折行与缩进随档位变化）。"""
        expected = _load_baseline()["narrow_56"]
        assert _render_menu_lines(TIERS["narrow_56"]) == expected

    def test_baseline_covers_every_menu_group(self):
        """基线必须覆盖全部分组标题：新增分组时夹具同步义务被显式化。"""
        from src.python.tui import tui_menu

        body = "\n".join(_load_baseline()["wide_90"])
        missing = [title for title, _keys in tui_menu.MENU_GROUPS if title not in body]
        assert missing == [], f"版式基线缺少分组标题：{missing}"


@pytest.mark.usefixtures("offline_external_sources")
class TestPipeOutputClean:
    """管道 / 非 TTY 输出不得含原地重绘控制字符。"""

    def _run_exit_flow(self) -> str:
        from src.python.tui import text_layout

        with patch.object(text_layout, "terminal_columns", return_value=TIERS["wide_90"]):
            feeder = run_flow(["KEY_ESC", "KEY_ESC"], pre_patches=common_patches())
        assert feeder.consumed == 2, "退出动线未按预期消费两次 Esc"
        return feeder.output

    def test_pipe_output_has_no_carriage_return(self):
        """``\\r`` 只属于 TTY 原地刷新路径；管道输出出现即说明档位判据漏判。"""
        assert "\r" not in self._run_exit_flow()

    def test_pipe_output_has_no_ansi_escape(self):
        """非 TTY 下颜色与控制序列必须全部关闭（ESC = 0x1b）。"""
        assert "\x1b" not in self._run_exit_flow()

    def test_exit_hint_is_on_screen(self):
        """退出确认提示确实上屏（防「输出为空也算干净」的空转断言）。"""
        assert "再按一次 Esc 退出" in self._run_exit_flow()


def _write_baseline() -> None:
    """按当前实现重写夹具（仅 ``TUI_LAYOUT_UPDATE=1`` 时由用例触发）。"""
    data = {name: _render_menu_lines(columns) for name, columns in TIERS.items()}
    BASELINE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_regenerate_baseline_when_requested():
    """夹具再生入口（常态跳过）：版式改动有意为之且已复核时使用。"""
    if os.environ.get("TUI_LAYOUT_UPDATE") != "1":
        pytest.skip("仅在 TUI_LAYOUT_UPDATE=1 时重写版式基线夹具")
    _write_baseline()
    assert set(_load_baseline()) == set(TIERS)
