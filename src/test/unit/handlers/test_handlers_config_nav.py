"""[S] 配置面板 + [C]/[A]/[D] 子菜单方向键导航测试（面板主体测试见同目录相邻文件）。

覆盖：
  - 面板行输入 `arrows=True` 契约（↑/↓ 返回方向键键名）
  - 游标移动的可观察位置反馈（▸ 行）与 Enter 按选中项既有派发
  - 未导航裸回车保持原语义（不误触切换）
  - 子菜单（P/A/D）经 panel_loop 单源化后的导航
  - 面板渲染编号 1..N 连续（编号是面板第一入口，跳号即按到空号）

运行：
  pytest src/test/unit/handlers/test_handlers_config_nav.py -v
"""

from __future__ import annotations

import contextlib
import io
import re
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _panel_last_switch_flag() -> str:
    """``[S]`` 面板末项（六组末组末开关）：从注册表动态派生，不写死清单。"""
    from src.python.config.features import panel_option_numbers

    numbered = panel_option_numbers("[S]")
    assert numbered, "面板必须有开关（结构断言）"
    return numbered[-1][1]


@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.config.features.save_feature_overrides")
def test_panel_arrow_up_wraps_to_last_switch_and_enter_toggles(mock_save, mock_refresh):
    """面板以 arrows=True 调行输入：↑ 游标回绕到末项，Enter 按其编号走既有派发。"""
    from src.python.tui.handlers_config import _cmd_config_content_options

    last_flag = _panel_last_switch_flag()
    with patch("src.python.tui.handlers_config.input_choice", side_effect=["KEY_UP", "", "0"]) as mock_choice:
        _cmd_config_content_options()

    assert mock_choice.call_args.kwargs.get("arrows") is True, "面板行输入须启用方向键"
    assert mock_save.called, "Enter 应按选中项（末开关）触发既有切换派发"
    saved_keys = set(next(iter(mock_save.call_args.args)))
    assert saved_keys == {last_flag}


@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.config.features.save_feature_overrides")
def test_panel_enter_without_navigation_keeps_original_semantics(mock_save, mock_refresh):
    """未用方向键时裸回车保持原语义（不误触任何切换）。"""
    from src.python.tui.handlers_config import _cmd_config_content_options

    with patch("src.python.tui.handlers_config.input_choice", side_effect=["", "0"]):
        _cmd_config_content_options()

    assert not mock_save.called, "无导航姿态的回车不得触发切换"


@patch("src.python.tui.handlers_config.refresh_config")
@patch("src.python.config.features.save_feature_overrides")
def test_panel_arrow_down_shows_position_feedback(mock_save, mock_refresh, capsys):
    """↓ 移动游标给可观察位置反馈（▸ 行），不改任何开关状态。"""
    from src.python.tui.handlers_config import _cmd_config_content_options

    with patch("src.python.tui.handlers_config.input_choice", side_effect=["KEY_DOWN", "0"]):
        _cmd_config_content_options()

    out = capsys.readouterr().out
    assert "▸" in out, "方向键移动须给位置反馈"
    assert not mock_save.called, "纯导航不改状态"


class TestSubmenuArrowNav:
    """[C]/[A]/[D] 子菜单方向键导航（导航控制流单源化后全列表面板可用）。

    锁定 panel_loop 迁移后子菜单的 ↑/↓ 导航 + Enter 按选中项派发，及空回车默认语义。
    """

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config._apply_edit", return_value=True)
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    @patch("src.python.config.get_config", return_value={})
    def test_report_boards_arrow_down_enter_toggles_selected(self, _mock_get, _mock_read, mock_apply, _mock_refresh):
        """[C] ↓ 移到第 2 项（市场新闻）后 Enter 按其编号派发切换。"""
        from src.python.tui.handlers_config import _cmd_config_report_boards
        from src.python.tui.tui_keys import KEY_DOWN

        with patch("src.python.tui.handlers_config.input_choice", side_effect=[KEY_DOWN, "", "0"]) as mock_input:
            _cmd_config_report_boards()

        assert mock_input.call_args_list[0].kwargs.get("arrows") is True, "面板行输入须启用方向键"
        assert mock_apply.called, "Enter 应按选中项触发既有切换派发"
        assert mock_apply.call_args.args[0]["key"] == "enable_news", "↓ 后 Enter 命中第 2 项（市场新闻）"

    @patch("src.python.tui.handlers_config._apply_edit", return_value=True)
    @patch("src.python.config.anonymizer.get_anonymization_mode", return_value="off")
    def test_anonymization_arrow_down_enter_selects_mode(self, _mock_cur, mock_apply):
        """[A] ↓ 移到第 2 项后 Enter 选中该匿名化模式。"""
        from src.python.tui.handlers_config import _cmd_config_anonymization_mode
        from src.python.tui.tui_keys import KEY_DOWN

        with patch("src.python.tui.handlers_config.input_choice", side_effect=[KEY_DOWN, "", "0"]):
            _cmd_config_anonymization_mode()

        assert mock_apply.called, "Enter 应按选中模式派发切换"
        applied = mock_apply.call_args.args[0]
        assert applied["key"] == "anonymization.mode" and applied["value"] == "code_display", (
            "↓ 后 Enter 命中第 2 项（代码显示）"
        )


class TestInlineCursorRendering:
    """渲染级回归：方向键移动后 ▸ 必须落在行内编号/键名前。

    锁住「测试绿 ≠ 屏幕可见」缺口：此前 8 面板迁移到 panel_loop 只断言了导航态
    （回绕/派发/防误触），未断言渲染输出含 ▸，导致 S/I/M/缓存漏画游标却全绿放行。
    本类直接断言渲染文本里的行内游标字符，漏画即红。
    """

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.config.features.save_feature_overrides")
    def test_s_panel_arrow_down_draws_inline_cursor(self, *_mocks):
        """[S] ↓后重绘：▸ 落在某行内编号前（非仅一闪而过的反馈行）。"""
        from src.python.tui.handlers_config import _cmd_config_content_options
        from src.python.tui.tui_keys import KEY_DOWN

        buf = io.StringIO()
        with patch("src.python.tui.handlers_config.input_choice", side_effect=[KEY_DOWN, "0"]):
            with contextlib.redirect_stdout(buf):
                _cmd_config_content_options()
        assert re.search(r"▸\s*\d+\.", buf.getvalue()), "[S] 方向键移动后渲染须在行内编号前画 ▸"

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.get_config_cache")
    def test_comparison_indices_arrow_shows_cursor(self, mock_cache, *_mocks):
        """[I] ↓ 移到第 2 项（D 删除指数）后 ▸ 落在该行键名前。"""
        from src.python.tui.handlers_config import _cmd_config_comparison_indices
        from src.python.tui.tui_keys import KEY_DOWN

        mock_cache.return_value = {"comparison_indices": {"sh000905": "中证500"}}
        buf = io.StringIO()
        with patch("src.python.tui.handlers_config.input_choice", side_effect=[KEY_DOWN, "0"]):
            with contextlib.redirect_stdout(buf):
                _cmd_config_comparison_indices()
        assert re.search(r"▸\s*D\.", buf.getvalue()), "[I] 方向键移动后 ▸ 须落在选中行（D 删除指数）"

    def test_providers_panel_arrow_shows_cursor(self):
        """[M] ↓ 移到第 2 条线路后 ▸ 落在该行编号前。"""
        from src.python.tui.handlers_config import _cmd_config_llm_providers
        from src.python.tui.tui_keys import KEY_DOWN

        providers = {
            "strategy": "priority",
            "providers": [
                {"name": "main", "provider": "claude", "priority": 10},
                {"name": "aux", "provider": "openai", "priority": 20},
            ],
        }
        buf = io.StringIO()
        with (
            patch("src.python.config.get_llm_providers", return_value=providers),
            patch("src.python.tui.handlers_llm_providers.input_choice", side_effect=[KEY_DOWN, "0"]),
            patch("src.python.tui.handlers_config._apply_edit", return_value=True),
        ):
            with contextlib.redirect_stdout(buf):
                _cmd_config_llm_providers()
        assert re.search(r"▸\s*\d+\.", buf.getvalue()), "[M] 方向键移动后 ▸ 须落在选中线路行"

    def test_cache_management_arrow_shows_cursor(self):
        """缓存管理 ↓ 后 ▸ 落在唯一可导航项「3 清理」（0 为 return 项不参与导航）。"""
        from types import SimpleNamespace

        from src.python.tui import handlers_cache
        from src.python.tui.tui_keys import KEY_DOWN

        stats = SimpleNamespace(
            total_files=1,
            total_size_bytes=10,
            hit_total=1,
            hit_rate=100.0,
            top_by_size=[],
            by_prefix={},
            expired=0,
            snapshot_files=0,
            snapshot_size_bytes=0,
            state_files=0,
            state_size_bytes=0,
        )
        buf = io.StringIO()
        with (
            patch("src.python.cache.operations.get_cache_stats", return_value=stats),
            patch("src.python.tui.handlers_cache.input_choice", side_effect=[KEY_DOWN, "0"]),
        ):
            with contextlib.redirect_stdout(buf):
                handlers_cache._cmd_cache_management()
        assert re.search(r"▸\s*3\s清理", buf.getvalue()), "缓存面板方向键移动后 ▸ 须落在可导航项（3 清理）"


class TestPanelNumberingRendered:
    """渲染级编号连续性：[C]/[S]/[M] 面板逐项编号必须 1..N 连续，末尾 0 为返回项。

    首页不走编号体系（字母为主入口、`1/2/3` 是数据类别名，连续性由
    `test_tui_menu.py::test_numeric_keys_are_contiguous` 单独守）；面板内编号才是
    第一入口，出现 1/2/4 这类跳号会让用户按到空号并把「无效编号」当成自己的操作错。
    断言按结构关系（前缀恰为 1..N、末项 0），不写死任何总数。
    """

    _NUMBERING = re.compile(r"(?:^|│)\s*(?:▸\s*)?(\d+)\.\s", re.M)

    def _rendered_numbers(self, fn, target: str = "src.python.tui.handlers_config") -> list[int]:
        buf = io.StringIO()
        with patch(f"{target}.input_choice", return_value="0"):
            with contextlib.redirect_stdout(buf):
                fn()
        return [int(n) for n in self._NUMBERING.findall(buf.getvalue())]

    @staticmethod
    def _assert_contiguous(numbers: list[int]) -> None:
        assert numbers, "面板未渲染任何编号条目"
        assert numbers[-1] == 0, f"末项应为 0（返回主菜单），实际 {numbers[-1]}"
        body = numbers[:-1]
        assert body == list(range(1, len(body) + 1)), f"面板编号跳号：{body}"

    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    @patch("src.python.config.get_config", return_value={})
    def test_report_boards_numbering(self, *_mocks):
        """[C] 章节编号自 1 连续（子项不占章节编号），末项 0。"""
        from src.python.tui.handlers_config import _cmd_config_report_boards

        numbers = self._rendered_numbers(_cmd_config_report_boards)
        self._assert_contiguous(numbers)
        assert numbers[:-1] == list(range(1, len(numbers)))

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.config.features.save_feature_overrides")
    def test_content_options_numbering(self, *_mocks):
        """[S] 六组开关编号 1..N 连续、末项 0（N 由注册表派生）。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        self._assert_contiguous(self._rendered_numbers(_cmd_config_content_options))

    def test_llm_providers_numbering(self):
        from src.python.tui.handlers_config import _cmd_config_llm_providers

        self._assert_contiguous(
            self._rendered_numbers(_cmd_config_llm_providers, target="src.python.tui.handlers_llm_providers")
        )

    def test_anonymization_detail_shows_switch_effect(self, capsys):
        """[A] 面板 `?3` 给出该项说明（不是只有键与名称）。"""
        from src.python.tui.handlers_config import _cmd_config_anonymization_mode

        with patch("src.python.tui.handlers_config.input_choice", side_effect=["?3", "0"]):
            _cmd_config_anonymization_mode()
        out = capsys.readouterr().out
        assert "切换到该匿名化模式" in out

    def test_providers_detail_shows_model_and_priority(self, capsys):
        """[M] 面板 `?1` 给出模型与优先级（面板自带业务含义，不靠通用回落）。"""
        from src.python.tui.handlers_config import _cmd_config_llm_providers

        providers = {
            "strategy": "priority",
            "providers": [
                {"name": "main", "provider": "claude", "priority": 10, "model": "m1", "endpoint": "https://api.x"},
                {"name": "aux", "provider": "openai", "priority": 20},
            ],
        }
        with (
            patch("src.python.config.get_llm_providers", return_value=providers),
            patch("src.python.tui.handlers_llm_providers.input_choice", side_effect=["?1", "0"]),
        ):
            _cmd_config_llm_providers()
        out = capsys.readouterr().out
        assert "模型 m1" in out
        assert "优先级 10" in out
