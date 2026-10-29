"""窄屏渲染底线全景机检：40 列下每个面板的每一行都不得超出终端宽度。

为什么需要（对应契约「窄屏基准 40 列」与 `switch_panel` 的「窄档不画盒线」约定）：
`text_layout.render_panel` 的宽度是**内容驱动**的（内容下限 41 列 + 边框），它不看终端
宽度；只要某个面板无条件调用它，40~55 列的手机终端上就会撑出 49~57 列并被终端硬折成
锯齿。历史缺陷（`[C]/[A]/[I]` 固定盒线、`[V]/[H]/[D]/[3]` 长表格/长路径）都属这一类，
且只有真终端才能看出来——所以这里用 `COLUMNS=40` 驱动全部面板渲染路径逐行量宽。

断言口径：每行 `display_width(line) <= terminal_columns()`（= 40）。不写死行数/盘符，
新增面板只要被本表登记即自动纳入底线；新增面板忘了降级会在这里立刻变红。
"""

from __future__ import annotations

import contextlib
import io
from unittest.mock import patch

import pytest

from src.python.tui.text_layout import display_width, terminal_columns

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]

NARROW_FLOOR = 40


@pytest.fixture(autouse=True)
def _force_narrow(monkeypatch):
    """固定 40 列（`terminal_columns` 的下限），并清空状态行记忆避免跨例缓存。"""
    monkeypatch.setenv("COLUMNS", str(NARROW_FLOOR))
    from src.python.tui.status_line import reset_status_memo

    reset_status_memo()
    yield
    reset_status_memo()


def _render(fn, module: str) -> str:
    """驱动面板到「命令循环立即 0 返回」，返回其全部上屏文本。"""
    buf = io.StringIO()
    with patch(f"{module}.input_choice", return_value="0"):
        with contextlib.redirect_stdout(buf):
            fn()
    return buf.getvalue()


def _overflow(text: str, width: int) -> list[tuple[int, str]]:
    return [(display_width(line), line) for line in text.splitlines() if line.strip() and display_width(line) > width]


def _assert_fits(label: str, text: str) -> None:
    over = _overflow(text, terminal_columns())
    detail = "\n".join(f"  [{w} 列] {line[:70]}" for w, line in over[:5])
    assert not over, f"{label} 在 {NARROW_FLOOR} 列下超宽 {len(over)} 行（须按档位降级/折行）：\n{detail}"


def test_main_menu_fits_narrow_floor():
    from src.python.tui.tui_menu import render_menu

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        render_menu(0)
    _assert_fits("主菜单", buf.getvalue())


def test_report_boards_panel_fits_narrow_floor():
    from src.python.tui.handlers_config import _cmd_config_report_boards

    _assert_fits("[C] 报告章节", _render(_cmd_config_report_boards, "src.python.tui.handlers_config"))


def test_content_options_panel_fits_narrow_floor():
    from src.python.tui.handlers_config import _cmd_config_content_options

    _assert_fits("[S] 章节内容", _render(_cmd_config_content_options, "src.python.tui.handlers_config"))


def test_llm_providers_panel_fits_narrow_floor():
    from src.python.tui.handlers_config import _cmd_config_llm_providers

    _assert_fits("[M] 多链", _render(_cmd_config_llm_providers, "src.python.tui.handlers_llm_providers"))


def test_anonymization_panel_fits_narrow_floor():
    from src.python.tui.handlers_config import _cmd_config_anonymization_mode

    _assert_fits("[A] 匿名化", _render(_cmd_config_anonymization_mode, "src.python.tui.handlers_config"))


def test_comparison_indices_panel_fits_narrow_floor():
    from src.python.tui.handlers_config import _cmd_config_comparison_indices

    _assert_fits("[I] 指数池", _render(_cmd_config_comparison_indices, "src.python.tui.handlers_config"))


def test_global_settings_panel_fits_narrow_floor():
    """`[G]` 七项四组在 40 列下不越界（分组标题同样按内宽折行）。"""
    from src.python.tui.handlers_config import _cmd_global_settings

    buf = io.StringIO()
    with patch("builtins.input", side_effect=["0"]):
        with contextlib.redirect_stdout(buf):
            _cmd_global_settings()
    _assert_fits("[G] 全局设置", buf.getvalue())


def test_config_entry_map_fits_narrow_floor():
    from src.python.tui.handlers_config import _render_config_entry_map

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _render_config_entry_map()
    _assert_fits("[D] 配置入口地图", buf.getvalue())


def test_cache_panel_fits_narrow_floor():
    from src.python.tui.handlers_cache import _cmd_cache_management

    _assert_fits("[3] 缓存管理", _render(_cmd_cache_management, "src.python.tui.handlers_cache"))


def test_health_history_fits_narrow_floor():
    from src.python.tui.handlers_log import _cmd_view_health_history

    text = _render(_cmd_view_health_history, "src.python.tui.handlers_log")
    _assert_fits("[H] 数据源健康历史", text)


def test_run_logs_fit_narrow_floor():
    from src.python.tui.handlers_log import _cmd_view_logs

    text = _render(_cmd_view_logs, "src.python.tui.handlers_log")
    _assert_fits("[V] 运行日志", text)
