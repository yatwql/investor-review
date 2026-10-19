"""[S] 配置面板方向键导航测试（面板主体测试见同目录相邻文件）。

覆盖：
  - 面板行输入 `arrows=True` 契约（↑/↓ 返回方向键键名）
  - 游标移动的可观察位置反馈（▸ 行）与 Enter 按选中项既有派发
  - 未导航裸回车保持原语义（不误触切换）

运行：
  pytest src/test/unit/handlers/test_handlers_config_nav.py -v
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


_STANDARD_LLM_MODULES = {
    "global_macro": "全球政经局势",
    "expert_review": "智囊团深度复盘",
    "health_check": "持仓体检报告",
    "penetration_deep": "穿透深度分析",
    "news_correlation": "财经新闻热点与持仓关联分析",
}


def _panel_last_switch_flag() -> str:
    """面板末项（末分组末块的末开关）：从注册表动态派生，不写死清单。"""
    from src.python.config.features import GROUP_ORDER, switches_in_group

    blocks = list(switches_in_group(list(GROUP_ORDER)[-1]))
    assert blocks, "末分组必须有开关（结构断言）"
    return blocks[-1][0]


@patch("src.python.tui.handlers_config.press_any_key")
@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.config.features.save_feature_overrides")
@patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
@patch("src.python.core.registry.get_llm_module_names")
@patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
def test_panel_arrow_up_wraps_to_last_switch_and_enter_toggles(
    mock_read, mock_names, mock_filter, mock_save, mock_refresh, mock_press
):
    """面板以 arrows=True 调行输入：↑ 游标回绕到末项，Enter 按其编号走既有派发。"""
    from src.python.tui.handlers_config import _cmd_config_llm_modules

    last_flag = _panel_last_switch_flag()
    with patch("src.python.tui.handlers_config.input_choice", side_effect=["KEY_UP", "", "0"]) as mock_choice:
        _cmd_config_llm_modules()

    assert mock_choice.call_args.kwargs.get("arrows") is True, "面板行输入须启用方向键"
    assert mock_save.called, "Enter 应按选中项（末开关）触发既有切换派发"
    saved_keys = set(next(iter(mock_save.call_args.args)))
    assert saved_keys == {last_flag}
    mock_press.assert_called_once()


@patch("src.python.tui.handlers_config.press_any_key")
@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.config.features.save_feature_overrides")
@patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
@patch("src.python.core.registry.get_llm_module_names")
@patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
def test_panel_enter_without_navigation_keeps_original_semantics(
    mock_read, mock_names, mock_filter, mock_save, mock_refresh, mock_press
):
    """未用方向键时裸回车保持原语义（不误触任何切换）。"""
    from src.python.tui.handlers_config import _cmd_config_llm_modules

    with patch("src.python.tui.handlers_config.input_choice", side_effect=["", "0"]):
        _cmd_config_llm_modules()

    assert not mock_save.called, "无导航姿态的回车不得触发切换"
    mock_press.assert_called_once()


@patch("src.python.tui.handlers_config.press_any_key")
@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.config.features.save_feature_overrides")
@patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
@patch("src.python.core.registry.get_llm_module_names")
@patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
def test_panel_arrow_down_shows_position_feedback(
    mock_read, mock_names, mock_filter, mock_save, mock_refresh, mock_press, capsys
):
    """↓ 移动游标给可观察位置反馈（▸ 行），不改任何开关状态。"""
    from src.python.tui.handlers_config import _cmd_config_llm_modules

    with patch("src.python.tui.handlers_config.input_choice", side_effect=["KEY_DOWN", "0"]):
        _cmd_config_llm_modules()

    out = capsys.readouterr().out
    assert "▸" in out, "方向键移动须给位置反馈"
    assert not mock_save.called, "纯导航不改状态"
