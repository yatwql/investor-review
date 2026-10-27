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
    def test_content_options_panel_rectangular(self, mock_input, capsys):
        """[S] 章节内容面板：五组开关行与组标题行在同一右边框内。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        self._assert_rectangular(capsys, _cmd_config_content_options)

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
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/tmp/llm_settings.json"))
    @patch("src.python.config.get_config", return_value={})
    def test_report_boards_panel_rectangular(self, mock_get, mock_read, mock_input, mock_refresh, capsys):
        """[C] 章节显隐面板：四块章节、智囊团子项与块标题在同一右边框内。"""
        from src.python.tui.handlers_config import _cmd_config_report_boards

        self._assert_rectangular(capsys, _cmd_config_report_boards)

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["0"])
    @patch("src.python.config.get_config", return_value=_SUB_BASE_CONFIG)
    def test_anonymization_panel_rectangular(self, mock_get, mock_input, mock_refresh, capsys):
        """匿名化面板：带选中标记的行与普通行同宽（自成一档内区宽度）。"""
        from src.python.tui.handlers_config import _cmd_config_anonymization_mode

        self._assert_rectangular(capsys, _cmd_config_anonymization_mode)


class TestChapterPanelsOwnTheirBlocks:
    """两面板职责切分：``[C]`` 只放章节（含 LLM / 整章 / 关联产物），``[S]`` 只放章内内容。"""

    def _source(self, module: str) -> str:
        from pathlib import Path

        return (Path(__file__).resolve().parents[4] / "src" / "python" / "tui" / module).read_text(encoding="utf-8")

    def test_p_panel_is_chapter_registry_driven(self):
        """[C] 的清单、编号、分块与子项全部来自章节注册表（渠道层不另写清单）。"""
        src = self._source("handlers_report_chapters.py")
        assert "chapter_numbers" in src and "chapters_in_block" in src
        assert "BLOCK_ORDER" in src
        assert "enable_fund_deep_analysis" not in src, "章节键名不得写死在渠道层"

    def test_s_panel_renders_only_panel_groups(self):
        """[S] 由 PANEL_GROUPS + panel_option_numbers 派生，不再混排 LLM 模块。"""
        src = self._source("handlers_switch.py")
        assert "PANEL_GROUPS" in src
        assert "panel_option_numbers" in src
        assert "get_llm_module_names" not in src, "LLM 章节已归 [C]"
        assert "enabled_llm" not in src, "[S] 不再读写 llm_settings"

    def test_panels_partition_feature_registry(self):
        """两面板对功能开关的呈现是**划分**：并集=全注册表、交集为空。"""
        from src.python.config.chapter_registry import chapter_registry
        from src.python.config.features import PANEL_GROUPS, feature_switch_registry, panel_option_numbers

        content = {flag for _n, flag, _d in panel_option_numbers("[S]")}
        chapter_backed = {e.key for e in chapter_registry if e.source == "features"}
        sub_items = {flag for e in chapter_registry for flag in e.sub_items}
        assert content & chapter_backed == set()
        assert content & sub_items == set()
        assert content | chapter_backed | sub_items == set(feature_switch_registry)
        assert set(PANEL_GROUPS) == {"[C]", "[S]"}


class TestPanelPlainLanguageCopy:
    """[S] 面板用户文案白话化：不出现开发者术语 slug（页脚/帮助/报错全量断言）。"""

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_render_and_help_have_no_dev_jargon(self, mock_refresh, capsys):
        """面板渲染 + `?` 未识别帮助 + r 未识别提示：全部用「键名」，无 'slug'。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        with patch("builtins.input", side_effect=["? nope", "r nope", "0"]):
            _cmd_config_content_options()

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
    def test_global_settings_renders_map_then_returns(self, mock_input, capsys):
        """[G] → M 打印入口地图后回到全局设置，0 返回；全程不调用任何写入处理器。"""
        from src.python.tui.handlers_config import _cmd_global_settings

        with (
            patch("src.python.tui.handlers_config._cmd_config_dir") as m_dir,
            patch("src.python.tui.handlers_config._cmd_config_filename") as m_fn,
            patch("src.python.tui.handlers_config._cmd_config_output_dir") as m_out,
        ):
            _cmd_global_settings()
        out = capsys.readouterr().out
        assert "配置入口地图" in out
        assert "功能开关 / LLM 模块启停 / 实验项" in out
        for handler in (m_dir, m_fn, m_out):
            handler.assert_not_called()

    @patch("builtins.input", side_effect=["Z", "0"])
    def test_global_settings_invalid_choice_lists_keys(self, mock_input, capsys):
        """无效选择提示「请输入编号或字母」，且面板列出全部七个字母。"""
        from src.python.tui.handlers_config import GLOBAL_SETTINGS_ITEMS, _cmd_global_settings

        _cmd_global_settings()
        out = capsys.readouterr().out
        assert "请输入编号或字母" in out
        for letter, _label, _handler, _group in GLOBAL_SETTINGS_ITEMS:
            assert f"[{letter}]" in out

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
        from src.python.tui.handlers_config import _cmd_config_content_options

        with (
            patch("builtins.input", side_effect=["0"]),
            patch("src.python.tui.handlers_config.refresh_config"),
        ):
            _cmd_config_content_options()
        out = capsys.readouterr().out
        return [ln for ln in out.splitlines() if "[开启]" in ln or "[关闭]" in ln]

    def test_every_row_shows_its_key(self, capsys):
        """每一行都同时出现「编号 + 名称 + 键名」——键名与注册表真值逐一对应。"""
        from src.python.config.features import feature_switch_registry

        rows = self._rows(capsys)
        assert rows
        flat = "\n".join(rows)
        # 本章节内容面板的每个开关键名（长键名同样完整展示，不截断）
        missing = [
            key
            for key in feature_switch_registry
            if key not in flat
            and key not in {"llm_debate_procon", "llm_debate_conditional"}
            and feature_switch_registry[key].group not in {"standalone", "chapter_options"}
        ]
        assert missing == []

    def test_key_column_is_aligned_within_each_block(self, capsys):
        """同一块内各行状态列一致（块内按最长名称/键名对齐；块间以分隔线断开）。"""
        import re

        from src.python.tui.text_layout import display_width

        from src.python.tui.handlers_config import _cmd_config_content_options

        with (
            patch("builtins.input", side_effect=["0"]),
            patch("src.python.tui.handlers_config.refresh_config"),
        ):
            _cmd_config_content_options()
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

    def test_footer_explains_key_column_without_cost_row(self, capsys):
        """页脚解释键名列；本章节内容面板无 LLM 章节行，故不再有费用摘要口径。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        with (
            patch("builtins.input", side_effect=["0"]),
            patch("src.python.tui.handlers_config.refresh_config"),
        ):
            _cmd_config_content_options()
        out = capsys.readouterr().out
        assert "键名即行内淡色列" in out
        assert "近 7 日该模块调用次数" not in out
