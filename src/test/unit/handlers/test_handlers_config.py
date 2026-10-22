"""测试 handlers_config 的 LLM 设置读写辅助函数与配置面板渲染。

面板渲染部分锁定「盒线边框四边对齐」这条不变式——补白按显示宽度而非码点数。"""

from __future__ import annotations
from unittest.mock import patch
import pytest
from src.python.tui.text_layout import display_width

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture(autouse=True)
def _deterministic_panel_width(monkeypatch):
    """固定终端宽度：`[S]` 面板版面按终端列数分三档，断言文案需绑定确定档位。

    dev-verify 在非 TTY 子进程里跑（拿不到真实终端宽度），不锁定会让同一断言随
    执行环境在「宽/中/窄」三档间漂移 —— 属测试环境不确定性，不是产品行为差异。
    """
    monkeypatch.setenv("COLUMNS", "120")


class TestReadLlmSettings:
    """`_read_llm_settings`：读取委派给 config 层唯一入口（JSONC 容错由该层负责）。"""

    def test_delegates_to_config_layer(self):
        from src.python.tui.handlers_config import _read_llm_settings

        snapshot = ({"enabled_llm": {"news_correlation": True}}, "/tmp/llm_settings.json")
        with patch("src.python.config.read_llm_settings_file", return_value=snapshot):
            assert _read_llm_settings() == snapshot

    def test_none_prints_error_and_returns_none(self, capsys):
        from src.python.tui.handlers_config import _read_llm_settings

        with patch("src.python.config.read_llm_settings_file", return_value=None):
            assert _read_llm_settings() is None
        assert "无法读取 llm_settings.json" in capsys.readouterr().out


class TestApplyEdit:
    """_apply_edit: 写入委托共享 config.edit_ops.apply_config_edit（与 Web 同一编辑函数）。"""

    @patch("src.python.config.edit_ops.apply_config_edit")
    def test_delegates_to_shared_edit(self, mock_apply):
        """TUI 写入经共享编辑层，payload 原样透传，成功返回 True。"""
        from src.python.tui.handlers_config import _apply_edit

        payload = {"key": "enabled_llm.news_correlation", "value": True}
        assert _apply_edit(payload) is True
        mock_apply.assert_called_once_with(payload)

    @patch("src.python.config.edit_ops.apply_config_edit")
    def test_success_clears_status_memo(self, mock_apply):
        """写入成功即清页头状态行记忆（回首页立即重绘新值，不等 TTL）。"""
        from src.python.tui import status_line
        from src.python.tui.handlers_config import _apply_edit

        status_line._memo["line"] = "旧状态"
        status_line._memo["ts"] = 0.0
        try:
            assert _apply_edit({"key": "k", "value": "v"}) is True
            assert status_line._memo.get("line") is None
        finally:
            status_line.reset_status_memo()

    @patch("src.python.config.edit_ops.apply_config_edit", side_effect=ValueError("非法值"))
    def test_shared_edit_failure_returns_false(self, mock_apply):
        """共享层拒绝（校验/写入失败）→ 返回 False 不抛出，交由错误行呈现。"""
        from src.python.tui.handlers_config import _apply_edit

        assert _apply_edit({"key": "k", "value": "v"}) is False


_STANDARD_LLM_MODULES = {
    "global_macro": "全球政经局势",
    "expert_review": "智囊团深度复盘",
    "health_check": "持仓体检报告",
    "penetration_deep": "穿透深度分析",
    "news_correlation": "财经新闻热点与持仓关联分析",
}

_SUB_BASE_CONFIG: dict = {}


class TestConfigPanelsAreRectangular:
    """配置面板的盒线边框必须四边对齐。

    缺陷场景：面板行以 `len()`（码点数）手写空格补白，中文/全角字符占 2 列却
    只算 1；上下边框、分隔线、内容行又各写各的补白数，同一面板的右边框对不到
    同一列。本类逐个面板驱动一次渲染，断言打印出的盒线行显示宽度全等。
    """

    @staticmethod
    def _box_widths(captured: str) -> set[int]:
        """收集捕获输出中盒线行的显示宽度（非盒线行——如面板下方的图例——不计）。"""
        widths = set()
        for line in captured.splitlines():
            stripped = line.strip()
            if stripped.startswith(("┌", "│", "└")) and stripped.endswith(("┐", "│", "┘")):
                widths.add(display_width(line))
        return widths

    def _assert_rectangular(self, capsys, panel):
        """驱动面板函数一次（输入 0 直接返回），断言其盒线行等宽。"""
        panel()
        widths = self._box_widths(capsys.readouterr().out)
        assert widths, "未捕获到任何盒线行——面板渲染路径可能已变"
        assert len(widths) == 1, f"面板右边框未对齐，出现 {len(widths)} 种行宽：{sorted(widths)}"

    @patch("builtins.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config._read_llm_settings")
    def test_llm_modules_panel_rectangular(self, mock_read, mock_input, capsys):
        """LLM 分析章节面板：标准模块行与实验开关行在同一右边框内。"""
        mock_read.return_value = ({"enabled_llm": {}}, "/tmp/llm_settings.json")
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        self._assert_rectangular(capsys, _cmd_config_llm_modules)

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config.get_config_cache")
    def test_comparison_indices_panel_rectangular(self, mock_cache, mock_input, mock_refresh, capsys):
        """对比指数池面板：指数名含中文时右边框仍对齐。"""
        mock_cache.return_value = {"comparison_indices": {"sh000905": "中证500", "sh000300": "沪深300"}}
        from src.python.tui.handlers_config import _cmd_config_comparison_indices

        self._assert_rectangular(capsys, _cmd_config_comparison_indices)

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["0"])
    @patch("src.python.config.get_config", return_value={})
    def test_report_boards_panel_rectangular(self, mock_get, mock_input, mock_refresh, capsys):
        """报告可选章节面板：最长行（增强子模块说明）决定宽度且不撑破边框。"""
        from src.python.tui.handlers_config import _cmd_config_report_boards

        self._assert_rectangular(capsys, _cmd_config_report_boards)

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["0"])
    @patch("src.python.config.get_config", return_value=_SUB_BASE_CONFIG)
    def test_anonymization_panel_rectangular(self, mock_get, mock_input, mock_refresh, capsys):
        """匿名化面板：带选中标记的行与普通行同宽（自成一档内区宽度）。"""
        from src.python.tui.handlers_config import _cmd_config_anonymization_mode

        self._assert_rectangular(capsys, _cmd_config_anonymization_mode)


class TestReportGroupMovedToSwitchPanel:
    """报告章节与增强子模块已并入功能开关注册表：P 面板不再另设入口，S 面板新增一块。"""

    def _source(self, module: str = "handlers_config.py") -> str:
        from pathlib import Path

        return (Path(__file__).resolve().parents[4] / "src" / "python" / "tui" / module).read_text(encoding="utf-8")

    def test_p_subpanel_removed(self):
        src = self._source()
        assert "_cmd_config_report_submodules" not in src, "P 子面板应已删除"
        assert "REPORT_SUBMODULE_ITEMS" not in src, "面板清单常量应随子面板删除"

    def test_boards_panel_points_to_switch_menu(self):
        """基础章节面板第 6 项提示改到菜单 [S]，输入范围收为 (0-6)。"""
        src = self._source()
        assert "输入编号切换 (0-6)" in src
        assert "报告增强子模块 / LLM 分析章节 — 请在菜单 S 配置" in src

    def test_switch_panel_renders_report_group(self):
        """面板分组由注册表 GROUP_ORDER 派生（渠道层不得另写清单）。

        面板本体已迁至 `handlers_switch`（域拆分），断言随实现位置同步。
        """
        src = self._source("handlers_switch.py")
        assert "GROUP_ORDER" in src
        assert "for group in GROUP_ORDER" in src
        assert "GROUP_EXPERIMENTAL" not in src and "GROUP_REPORT" not in src


class TestDualEntryCrossHints:
    """持仓变动复盘双入口互指标注：LLM 行指章本体、独立组行指归因（只读，零行为变化）。"""

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch(
        "src.python.tui.handlers_config.filter_menu_llm_modules",
        return_value={
            **_STANDARD_LLM_MODULES,
            "holding_change": "持仓变动复盘归因",
        },
    )
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_both_rows_carry_cross_hint(self, mock_read, mock_names, mock_filter, mock_refresh, capsys):
        """两行各自携带对方入口提示，且仅这两行携带。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["0"]):
            _cmd_config_llm_modules()

        lines = capsys.readouterr().out.splitlines()
        llm_lines = [ln for ln in lines if "持仓变动复盘归因" in ln and "holding_change " in ln]
        feature_lines = [ln for ln in lines if "持仓变动复盘" in ln and "holding_change_review " in ln]
        assert len(llm_lines) == 1, "LLM 模块行应唯一出现"
        assert len(feature_lines) == 1, "独立组开关行应唯一出现"
        assert "见独立组" in llm_lines[0]
        assert "见 LLM 区" in feature_lines[0]
        # 其余行不携带互指提示（标注不扩散）
        other = [ln for ln in lines if "见独立组" in ln or "见 LLM 区" in ln]
        assert len(other) == 2

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.config.features.save_feature_overrides")
    @patch(
        "src.python.tui.handlers_config.filter_menu_llm_modules",
        return_value={
            **_STANDARD_LLM_MODULES,
            "holding_change": "持仓变动复盘归因",
        },
    )
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_hints_are_readonly_annotations(self, mock_read, mock_names, mock_filter, mock_save, mock_refresh, capsys):
        """互指标注纯只读：渲染不触发任何配置写入。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["0"]):
            _cmd_config_llm_modules()

        assert "见独立组" in capsys.readouterr().out
        mock_save.assert_not_called()


class TestPanelPlainLanguageCopy:
    """[S] 面板用户文案白话化：不出现开发者术语 slug（页脚/帮助/报错全量断言）。"""

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_render_and_help_have_no_dev_jargon(self, mock_read, mock_names, mock_filter, mock_refresh, capsys):
        """面板渲染 + `?` 未识别帮助 + r 未识别提示：全部用「键名」，无 'slug'。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["? nope", "r nope", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        # 提示串由模板产出（input 被 mock 后不上屏），故断言「模板渲染结果」——不再
        # 按源码 grep，改提示措辞时用例仍表达真实意图
        from src.python.tui.prompt_text import panel_prompt

        prompt = panel_prompt("输入编号切换开关", example="3", help_hint="?3 查看说明")
        assert "输入编号切换开关（如 3）" in prompt
        assert "?3 查看说明" in prompt and "0 返回" in prompt
        assert "请输入 ? 加编号或键名" in out
        assert "输入编号或键名" in out
        assert "slug" not in out, "面板输出不得出现内部术语 slug"

    def test_prompt_teaches_main_path_with_example(self):
        """提示语自带具体例子（如 3 / ?3 / 0 返回）——不看文档也知道怎么按。"""
        from src.python.tui.prompt_text import panel_prompt

        prompt = panel_prompt("输入编号切换开关", example="3", help_hint="?3 查看说明")
        assert "输入编号切换开关（如 3）" in prompt, "主路径要有具体编号示例，不能只写占位符"
        assert "?3 查看说明" in prompt, "说明查询要有无空格写法示例"
        assert "0 返回" in prompt, "返回通道要在提示语里可见"


class TestConfigEntryMap:
    """配置入口地图（[D] 子菜单 [M]）：只读索引，键位真实性由主菜单兜底。"""

    @staticmethod
    def _map() -> tuple[tuple[str, str, str], ...]:
        from src.python.tui.handlers_config import _CONFIG_ENTRY_MAP

        return _CONFIG_ENTRY_MAP

    def test_every_mapped_key_exists_in_main_menu(self):
        """地图中每个菜单键都真实存在于主菜单（键位调整时本用例兜底）。"""
        from src.python.tui.tui_menu import MENU_ITEMS

        menu_keys = {key for key, _label, _cb, _ex in MENU_ITEMS}
        for label, keys, _hint in self._map():
            for key in keys.replace("/", " ").split():
                token = key.strip("[]")
                assert token in menu_keys, f"{label} 映射到不存在的菜单键 {key}"

    def test_map_entries_are_unique_and_described(self):
        """条目唯一且每行三列齐备（配置项 / 菜单键 / 说明），键统一加方括号。"""
        entries = self._map()
        labels = [label for label, _k, _h in entries]
        assert len(labels) == len(set(labels))
        for label, keys, hint in entries:
            assert label.strip() and hint.strip()
            assert keys.startswith("[") and keys.endswith("]")

    @patch("builtins.input", side_effect=["M", "0"])
    def test_d_submenu_renders_map_then_returns(self, mock_input, capsys):
        """[D] → M 打印入口地图后回到子菜单，0 返回；全程不调用任何写入处理器。"""
        from src.python.tui.handlers_config import _cmd_config_dir_info

        with (
            patch("src.python.tui.handlers_config._cmd_config_dir") as m_dir,
            patch("src.python.tui.handlers_config._cmd_config_filename") as m_fn,
            patch("src.python.tui.handlers_config._cmd_config_output_dir") as m_out,
        ):
            _cmd_config_dir_info()
        out = capsys.readouterr().out
        assert "配置入口地图" in out
        assert "功能开关 / LLM 模块启停 / 实验项" in out
        for handler in (m_dir, m_fn, m_out):
            handler.assert_not_called()

    @patch("builtins.input", side_effect=["Z", "0"])
    def test_invalid_choice_lists_map_option(self, mock_input, capsys):
        """无效选择提示含新增的 M 选项（C/F/O/M/0）。"""
        from src.python.tui.handlers_config import _cmd_config_dir_info

        _cmd_config_dir_info()
        assert "请输入 C/F/O/M/0" in capsys.readouterr().out

    def test_map_rendering_is_readonly(self):
        """纯渲染无副作用：不调用配置写入/刷新入口。"""
        from src.python.tui.handlers_config import _render_config_entry_map

        with (
            patch("src.python.tui.handlers_config.refresh_config") as m_refresh,
            patch("src.python.config.features.save_feature_overrides") as m_save,
        ):
            _render_config_entry_map()
        m_refresh.assert_not_called()
        m_save.assert_not_called()


class TestKeyColumnVisible:
    """面板显式展示键名：无需猜测即可直接输入（`? 键名` / `键名=on|off`）。"""

    @staticmethod
    def _rows(capsys) -> list[str]:
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with (
            patch("builtins.input", side_effect=["0"]),
            patch("src.python.tui.handlers_config.refresh_config"),
            patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json")),
            patch("src.python.core.registry.get_llm_module_names", return_value={"global_macro": "全球政经局势"}),
        ):
            _cmd_config_llm_modules()
        out = capsys.readouterr().out
        return [ln for ln in out.splitlines() if "[开启]" in ln or "[关闭]" in ln]

    def test_every_row_shows_its_key(self, capsys):
        """每一行都同时出现「编号 + 名称 + 键名」——键名与注册表真值逐一对应。"""
        from src.python.config.features import feature_switch_registry

        rows = self._rows(capsys)
        assert rows
        flat = "\n".join(rows)
        assert "global_macro" in flat
        # 注册表全集里每个开关键名（长键名同样完整展示，不截断）
        missing = [key for key in feature_switch_registry if key not in flat]
        assert missing == []

    def test_key_column_is_aligned_within_each_block(self, capsys):
        """同一块内各行状态列一致（块内按最长名称/键名对齐；块间以分隔线断开）。"""
        import re

        from src.python.tui.text_layout import display_width

        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with (
            patch("builtins.input", side_effect=["0"]),
            patch("src.python.tui.handlers_config.refresh_config"),
            patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json")),
        ):
            _cmd_config_llm_modules()
        out = capsys.readouterr().out

        block_columns: list[set[int]] = [set()]
        for ln in out.splitlines():
            if "│───" in ln:  # 组分隔线 → 新块
                block_columns.append(set())
                continue
            m = re.search(r"\[(开启|关闭)\]", ln)
            if m:
                block_columns[-1].add(display_width(ln[: m.start()]))
        non_empty = [cols for cols in block_columns if cols]
        assert non_empty
        for cols in non_empty:
            assert len(cols) == 1, f"块内状态列未对齐: {sorted(cols)}"

    def test_footer_explains_key_column_and_cost(self, capsys):
        """页脚图例解释键名列与费用摘要口径（不靠用户推断）。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with (
            patch("builtins.input", side_effect=["0"]),
            patch("src.python.tui.handlers_config.refresh_config"),
            patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json")),
        ):
            _cmd_config_llm_modules()
        out = capsys.readouterr().out
        assert "键名即行内淡色列" in out
        assert "近 7 日该模块调用次数 / 累计费用 / 单次均值" in out
