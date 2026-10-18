"""测试 handlers_config 的 LLM 设置读写辅助函数与配置面板渲染。

面板渲染部分锁定「盒线边框四边对齐」这条不变式——补白按显示宽度而非码点数。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.python.tui.text_layout import display_width

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestReadLlmSettings:
    """_read_llm_settings: JSON 注释支持 + 文件不存在处理。"""

    @patch("src.python.config._strip_json_comments")
    @patch("src.python.tui.handlers_config.open")
    @patch("src.python.tui.handlers_config.json.loads")
    def test_normal_read(self, mock_json_loads, mock_open, mock_strip):
        """正常读取带注释的 JSON。"""
        mock_strip.return_value = '{"enabled_llm": {"news_correlation": true}}'
        mock_json_loads.return_value = {"enabled_llm": {"news_correlation": True}}
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "raw content"
        mock_open.return_value = mock_file

        from src.python.tui.handlers_config import _read_llm_settings

        result = _read_llm_settings()
        assert result is not None
        settings, path = result
        assert settings["enabled_llm"]["news_correlation"] is True
        assert "llm_settings.json" in path

    @patch("src.python.tui.handlers_config.open", side_effect=FileNotFoundError)
    @patch("src.python.tui.handlers_config.press_any_key")
    def test_file_not_found(self, mock_press, mock_open):
        """文件不存在时返回 None。"""
        from src.python.tui.handlers_config import _read_llm_settings

        result = _read_llm_settings()
        assert result is None

    @patch("src.python.config._strip_json_comments")
    @patch("src.python.tui.handlers_config.open")
    @patch("src.python.tui.handlers_config.json.loads", side_effect=json.JSONDecodeError("x", "", 1))
    @patch("src.python.tui.handlers_config.press_any_key")
    def test_json_decode_error(self, mock_press, mock_json_loads, mock_open, mock_strip):
        """JSON 解析错误时返回 None。"""
        mock_strip.return_value = "bad json"
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "bad json"
        mock_open.return_value = mock_file

        from src.python.tui.handlers_config import _read_llm_settings

        result = _read_llm_settings()
        assert result is None


class TestApplyEdit:
    """_apply_edit: 写入委托共享 config.edit_ops.apply_config_edit（与 Web 同一编辑函数）。"""

    @patch("src.python.config.edit_ops.apply_config_edit")
    def test_delegates_to_shared_edit(self, mock_apply):
        """TUI 写入经共享编辑层，payload 原样透传，成功返回 True。"""
        from src.python.tui.handlers_config import _apply_edit

        payload = {"key": "enabled_llm.news_correlation", "value": True}
        assert _apply_edit(payload) is True
        mock_apply.assert_called_once_with(payload)

    @patch("src.python.config.edit_ops.apply_config_edit", side_effect=ValueError("非法值"))
    def test_shared_edit_failure_returns_false(self, mock_apply):
        """共享层拒绝（校验/写入失败）→ 返回 False 不抛出，交由错误行呈现。"""
        from src.python.tui.handlers_config import _apply_edit

        assert _apply_edit({"key": "k", "value": "v"}) is False


# 标准 LLM 模块（菜单 S 1~5），其余编号由分组与块内顺序派生（见 _switch_menu_number）
_STANDARD_LLM_MODULES = {
    "global_macro": "全球政经局势",
    "expert_review": "智囊团深度复盘",
    "health_check": "持仓体检报告",
    "penetration_deep": "穿透深度分析",
    "news_correlation": "财经新闻热点与持仓关联分析",
}


def _switch_menu_number(flag: str) -> int:
    """按面板同一派生规则计算某功能开关的菜单编号（测试输入用）。

    编号 = 标准模块数 + 各分组长度 + 块内序，与
    ``handlers_config._cmd_config_llm_modules`` 实时派发同源：注册表新增/挪动
    开关时自动跟随——硬编码编号会静默错位成「切换了别的开关」（新增
    持仓变动复盘时实测）。
    """
    from src.python.config.features import GROUP_ORDER, switches_in_group

    serial = len(_STANDARD_LLM_MODULES)  # 面板补丁下的标准模块数（1..5）
    for group in GROUP_ORDER:
        block = switches_in_group(group)
        for offset, (f, _d) in enumerate(block, 1):
            if f == flag:
                return serial + offset
        serial += len(block)
    raise AssertionError(f"开关未上屏：{flag}")


class TestConfigLlmModulesExperimentalFlags:
    """_cmd_config_llm_modules: 四组开关面板（清单与分块取自 features 注册表 GROUP_ORDER）。"""

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=[str(_switch_menu_number("decision_reflection")), "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_menu_number_toggles_decision_reflection(
        self,
        mock_read,
        mock_names,
        mock_filter,
        mock_save_overrides,
        mock_input,
        mock_refresh,
        mock_press,
    ):
        """输入决策跨期反思闭环的派生编号 → 切换机制与诊断块内该项，持久化到 features.json。

        各块各项编号（呈现与体验 / 分析增强 / 独立章节与回放 / 机制与诊断）
        随注册表即时重排——本用例按面板同源规则取号，不写死。
        """
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        mock_save_overrides.assert_called_once_with({"decision_reflection": True})
        mock_press.assert_called_once()

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=[str(_switch_menu_number("prosperity_framework")), "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_menu_number_toggles_prosperity_framework(
        self,
        mock_read,
        mock_names,
        mock_filter,
        mock_save_overrides,
        mock_input,
        mock_refresh,
        mock_press,
    ):
        """输入景气度框架诊断的派生编号 → 切换该开关（默认开 → 关），持久化到 features.json。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        mock_save_overrides.assert_called_once_with({"prosperity_framework": False})
        mock_press.assert_called_once()

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=[str(_switch_menu_number("deterministic_signal")), "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_menu_number_toggles_promoted_standard_switch(
        self,
        mock_read,
        mock_names,
        mock_filter,
        mock_save_overrides,
        mock_input,
        mock_refresh,
        mock_press,
    ):
        """输入机制与诊断块首项（确定性信号模块，非实验项、默认开）→ 切换即关闭。

        转正不丢入口、也不等于不可关：机制与诊断块编号紧随前三个块（编号由分组与块内
        顺序派生，本用例按面板同源规则取号），默认开故点一次写入 false。
        """
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        mock_save_overrides.assert_called_once_with({"deterministic_signal": False})
        mock_press.assert_called_once()

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=[str(_switch_menu_number("llm_debate_procon")), "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.config.features.set_feature_enabled")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_menu_number_toggles_first_debate_flag(
        self,
        mock_read,
        mock_names,
        mock_filter,
        mock_set_feature,
        mock_save_overrides,
        mock_input,
        mock_refresh,
        mock_press,
    ):
        """输入第一个辩论开关的派生编号 → 仍切正反辩论（块内序首项连续性）。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        mock_save_overrides.assert_called_once_with({"llm_debate_procon": True})

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=[str(_switch_menu_number("metrics_enabled")), "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_menu_number_toggles_metrics_switch(
        self,
        mock_read,
        mock_names,
        mock_filter,
        mock_save_overrides,
        mock_input,
        mock_refresh,
        mock_press,
    ):
        """输入量化指标单开关的派生编号 → 持久化到 features.json。

        面板块序（呈现与体验 → 分析增强 → 独立章节与回放 → 机制与诊断）与块内
        顺序均按注册表声明序派生，任一组增项/挪项时编号自动跟随。
        """
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        mock_save_overrides.assert_called_once_with({"metrics_enabled": False})

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=[str(_switch_menu_number("doctor_check")), "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_standard_block_includes_promoted_switches(
        self,
        mock_read,
        mock_names,
        mock_filter,
        mock_save_overrides,
        mock_input,
        mock_refresh,
        mock_press,
    ):
        """系统自检（转正项）在机制与诊断块内可切换——转正不丢入口（回归）。

        编号 = 标准模块数 + 四组块累计 + doctor_check 块内序位（派生，非写死）。
        它此前只能靠手改 features.json 关闭；本用例锁定它在面板内仍可关。
        """
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        mock_save_overrides.assert_called_once_with({"doctor_check": False})


# 报告增强子模块基准配置（与 config.json 默认一致：数据质量仪表盘默认开，其余默认关）
#: 面板渲染测试用的最小配置（报告增强子模块已并入功能开关注册表，不再出现在 config）
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

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config._read_llm_settings")
    def test_llm_modules_panel_rectangular(self, mock_read, mock_input, mock_press, capsys):
        """LLM 分析章节面板：标准模块行与实验开关行在同一右边框内。"""
        mock_read.return_value = ({"enabled_llm": {}}, "/tmp/llm_settings.json")
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        self._assert_rectangular(capsys, _cmd_config_llm_modules)

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config.get_config_cache")
    def test_comparison_indices_panel_rectangular(self, mock_cache, mock_input, mock_refresh, mock_press, capsys):
        """对比指数池面板：指数名含中文时右边框仍对齐。"""
        mock_cache.return_value = {"comparison_indices": {"sh000905": "中证500", "sh000300": "沪深300"}}
        from src.python.tui.handlers_config import _cmd_config_comparison_indices

        self._assert_rectangular(capsys, _cmd_config_comparison_indices)

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["0"])
    @patch("src.python.config.get_config", return_value={})
    def test_report_boards_panel_rectangular(self, mock_get, mock_input, mock_refresh, mock_press, capsys):
        """报告可选章节面板：最长行（增强子模块说明）决定宽度且不撑破边框。"""
        from src.python.tui.handlers_config import _cmd_config_report_boards

        self._assert_rectangular(capsys, _cmd_config_report_boards)

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["0"])
    @patch("src.python.config.get_config", return_value=_SUB_BASE_CONFIG)
    def test_anonymization_panel_rectangular(self, mock_get, mock_input, mock_refresh, mock_press, capsys):
        """匿名化面板：带选中标记的行与普通行同宽（自成一档内区宽度）。"""
        from src.python.tui.handlers_config import _cmd_config_anonymization_mode

        self._assert_rectangular(capsys, _cmd_config_anonymization_mode)


class TestReportGroupMovedToSwitchPanel:
    """报告章节与增强子模块已并入功能开关注册表：P 面板不再另设入口，S 面板新增一块。"""

    def _source(self) -> str:
        from pathlib import Path

        return (Path(__file__).resolve().parents[4] / "src" / "python" / "tui" / "handlers_config.py").read_text(
            encoding="utf-8"
        )

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
        """面板分组由注册表 GROUP_ORDER 派生（渠道层不得另写清单）。"""
        src = self._source()
        assert "GROUP_ORDER" in src
        assert "for group in GROUP_ORDER" in src
        assert "GROUP_EXPERIMENTAL" not in src and "GROUP_REPORT" not in src


class TestConfigDirInfoSubmenu:
    """[D] 查看配置与目录信息子菜单：二级选项分发、返回与无效输入。"""

    @patch("builtins.input")
    @patch("src.python.tui.handlers_config._cmd_config_output_dir")
    @patch("src.python.tui.handlers_config._cmd_config_filename")
    @patch("src.python.tui.handlers_config._cmd_config_dir")
    def test_dispatches_three_sub_options_then_returns(self, mock_dir, mock_filename, mock_out, mock_input):
        """依次选 C/F/O 分别路由到三个处理器，B 返回。"""
        mock_input.side_effect = ["C", "F", "O", "B"]

        from src.python.tui.handlers_config import _cmd_config_dir_info

        _cmd_config_dir_info()

        mock_dir.assert_called_once_with()
        mock_filename.assert_called_once_with()
        mock_out.assert_called_once_with()

    @patch("builtins.input")
    @patch("src.python.tui.handlers_config._cmd_config_dir")
    def test_lowercase_choice_accepted(self, mock_dir, mock_input):
        """小写子键归一化为大写后分发。"""
        mock_input.side_effect = ["c", "B"]

        from src.python.tui.handlers_config import _cmd_config_dir_info

        _cmd_config_dir_info()

        mock_dir.assert_called_once_with()

    @patch("builtins.input")
    @patch("src.python.tui.handlers_config._cmd_config_dir")
    def test_back_returns_without_dispatch(self, mock_dir, mock_input):
        """选 B 直接返回，不触发任何处理器。"""
        mock_input.side_effect = ["B"]

        from src.python.tui.handlers_config import _cmd_config_dir_info

        _cmd_config_dir_info()

        mock_dir.assert_not_called()

    @patch("builtins.input")
    @patch("src.python.tui.handlers_config._cmd_config_dir")
    def test_unknown_choice_reprompts(self, mock_dir, mock_input, capsys):
        """无效子键提示后重新等待输入，不误触发处理器。"""
        mock_input.side_effect = ["Z", "B"]

        from src.python.tui.handlers_config import _cmd_config_dir_info

        _cmd_config_dir_info()

        mock_dir.assert_not_called()
        assert "无效选择" in capsys.readouterr().out

    @patch("src.python.tui.handlers_config._cmd_config_dir")
    @patch("builtins.input", side_effect=EOFError)
    def test_eof_returns_safely(self, mock_input, mock_dir):
        """EOF（非交互输入）不抛异常：读取一次即返回，不触发任何处理器。"""
        from src.python.tui.handlers_config import _cmd_config_dir_info

        _cmd_config_dir_info()

        mock_input.assert_called_once()
        mock_dir.assert_not_called()


class TestSwitchPanelReadonlyInfo:
    """_cmd_config_llm_modules 只读信息面：? 编号详情 / * 漂移标记 / ⚗ 启用统计上屏。"""

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=[f"? {_switch_menu_number('decision_reflection')}", "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_question_mark_shows_feature_detail_readonly(
        self, mock_read, mock_names, mock_filter, mock_save, mock_input, mock_refresh, mock_press, capsys
    ):
        """`? 编号` 上屏说明/当前/默认/存储键，纯只读（不触发任何配置写入）。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "登记决策 → 真实行情结算命中率 → 教训回灌专家复盘提示词" in out, "注册表 desc 应上屏"
        assert "features.json → decision_reflection" in out
        assert "出厂默认" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["? abc", f"? {9999}", "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_question_mark_invalid_input_reprompts(
        self, mock_read, mock_names, mock_filter, mock_save, mock_input, mock_refresh, mock_press, capsys
    ):
        """非数字编号与越界编号均给出行内提示并回到面板，不抛出、不写配置。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "请输入 ? 加编号" in out
        assert "无效编号" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["? 1", "0"])
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_question_mark_shows_llm_module_detail(
        self, mock_read, mock_names, mock_filter, mock_save, mock_input, mock_refresh, mock_press, capsys
    ):
        """LLM 模块详情：enabled_llm 存储键 + 当前/出厂默认（默认开）+ 只读。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "llm_settings.json → enabled_llm.global_macro" in out
        assert "当前  : 开启" in out and "出厂默认: 开启" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch(
        "src.python.tui.handlers_config._read_llm_settings",
        return_value=({"enabled_llm": {"global_macro": False}}, "/fake/llm_settings.json"),
    )
    def test_non_default_llm_module_star_marked(
        self, mock_read, mock_names, mock_filter, mock_input, mock_refresh, mock_press, capsys
    ):
        """LLM 模块显示值 ≠ 出厂默认时行尾标 *（关闭的默认开模块）。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "全球政经局势" in out and "[关闭]*" in out
        assert "与出厂默认值不一致" in out, "页脚应有 * 释义"

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_non_default_feature_star_marked(
        self, mock_read, mock_names, mock_filter, mock_input, mock_refresh, mock_press, capsys
    ):
        """功能开关与出厂默认不一致时行尾标 *（默认关的开关被置开）。"""
        import re

        from src.python.config.features import set_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        set_feature_enabled("decision_reflection", True)
        try:
            _cmd_config_llm_modules()
            out = capsys.readouterr().out
            assert re.search(r"决策跨期反思闭环\s+\[开启\]\*", out), f"应有 [开启]* 漂移标记:\n{out}"
        finally:
            set_feature_enabled("decision_reflection", False)

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_experiment_stats_suffix_on_experimental_row(
        self, mock_read, mock_names, mock_filter, mock_input, mock_refresh, mock_press, capsys
    ):
        """⚗ 实验项行尾附启用统计（次数 + 最近日期 MM-DD），数据来自 experiment_stats。"""
        import json
        import os

        from src.python.core import experiment_stats
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        os.makedirs(os.path.dirname(experiment_stats.EXPERIMENT_STATS_FILE), exist_ok=True)
        with open(experiment_stats.EXPERIMENT_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"decision_reflection": {"enabled_count": 5, "last_enabled_date": "2026-10-13"}},
                f,
                ensure_ascii=False,
            )

        _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "启用 5 次" in out
        assert "最近 10-13" in out


class TestSwitchPanelOperations:
    """[S] 面板写路径三通道：批量恢复默认（r/ra）、实验项全关（x）、键名/赋值直取。

    全部用例把 ``features.FEATURES_FILE`` 指向临时文件（持久化隔离），运行时
    FEATURE_FLAGS 由 conftest 自动重置兜底。
    """

    @staticmethod
    def _seed(tmp_path, monkeypatch, initial: dict):
        import src.python.config.features as features_mod

        path = tmp_path / "features.json"
        path.write_text(json.dumps(initial, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(features_mod, "FEATURES_FILE", str(path))
        # 载入种子覆写，使运行时与文件同源（与真实会话「导入即加载」一致）
        features_mod.load_feature_overrides()
        return path

    @staticmethod
    def _read(path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.config.features.filter_menu_llm_modules", return_value=None, create=True)
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_restore_group_clears_overrides_in_group(
        self, mock_read, mock_names, mock_filter, _mock_ff, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """`r 编号` 只恢复该项所在分组的覆写（跨组键保留），运行时回出厂默认。"""
        from src.python.config.features import is_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(tmp_path, monkeypatch, {"doctor_check": False, "market_temperature": False})
        with patch(
            "builtins.input",
            side_effect=[f"r {_switch_menu_number('doctor_check')}", "0"],
        ):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "已恢复「⚙ 机制与诊断" in out and "移除 1 项覆写" in out
        assert self._read(path) == {"market_temperature": False}, "同组 doctor_check 覆写应删、跨组键保留"
        assert is_feature_enabled("doctor_check") is True, "运行时应回出厂默认"
        assert is_feature_enabled("market_temperature") is False

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_restore_all_clears_file(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """`ra` 清空全部覆写（恢复全部默认），文件保留为空对象。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(
            tmp_path, monkeypatch, {"doctor_check": False, "market_temperature": False, "cost_lots": True}
        )
        with patch("builtins.input", side_effect=["ra", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "已恢复功能开关全部默认（移除 3 项覆写）" in out
        assert self._read(path) == {}

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_experimental_all_switched_off(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """`x` 实验项一键全关：experimental 集合回默认（删覆写），文件内实验键清掉。"""
        from src.python.config.features import experimental_flags, is_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(tmp_path, monkeypatch, {"decision_reflection": True, "report_qa": True, "cost_lots": True})
        with patch("builtins.input", side_effect=["x", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "实验项已全部关闭（回到无实验态）" in out
        for flag, _d in experimental_flags():
            assert flag in out, "被关闭的实验项应列出"
            assert is_feature_enabled(flag) is False
        assert self._read(path) == {"cost_lots": True}, "非实验键不受影响"

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_feature_slug_toggles_without_number(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """裸 slug 直接切换（编号/slug 双通道，编号漂移免疫）。"""
        from src.python.config.features import is_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["doctor_check", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "系统自检" in out and "已关闭" in out
        assert is_feature_enabled("doctor_check") is False
        assert self._read(path) == {"doctor_check": False}

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_assignment_uses_cli_vocabulary(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """`slug=on|off` 与 CLI --feature 同词表同解析（两次赋值均落盘）。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["doctor_check=off", "doctor_check=on", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert out.count("已关闭") >= 1 and out.count("已开启") >= 1
        assert self._read(path) == {"doctor_check": True}

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_assignment_invalid_value_reports_cli_error(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """非法取值走 CLI 解析器词表报错，不写盘、状态不变。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["doctor_check=maybe", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "取值 'maybe' 不可识别" in out
        assert self._read(path) == {}

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_restore_rejects_llm_item(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """`r 1`（LLM 模块条目）被拒——恢复默认仅支持功能开关分组，且不写任何配置。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(tmp_path, monkeypatch, {"doctor_check": False})
        with patch("builtins.input", side_effect=["r 1", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "恢复默认仅支持功能开关分组" in out
        assert self._read(path) == {"doctor_check": False}

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_restore_unknown_target_reports(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, tmp_path, monkeypatch, capsys
    ):
        """`r 不存在的目标` 给出行内提示，不抛出、不写盘。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["r nope", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "未识别目标" in out and "输入编号或键名" in out
        assert self._read(path) == {}

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.config.features.save_feature_overrides")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_question_mark_slug_detail_readonly(
        self, mock_read, mock_names, mock_filter, mock_save, mock_refresh, mock_press, capsys
    ):
        """`? slug` 与编号通道同源上屏详情，纯只读。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["? doctor_check", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "features.json → doctor_check" in out
        assert "出厂默认" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_unknown_input_reports_three_channel_hint(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, capsys
    ):
        """未知输入给出三通道提示（编号 / 键名 / 键名=on|off），不抛出。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["definitely_nope", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        assert "未知编号或键名" in out and "键名=on|off" in out


class TestDualEntryCrossHints:
    """持仓变动复盘双入口互指标注：LLM 行指章本体、独立组行指归因（只读，零行为变化）。"""

    @patch("src.python.tui.handlers_config.press_any_key")
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
    def test_both_rows_carry_cross_hint(self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, capsys):
        """两行各自携带对方入口提示，且仅这两行携带。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["0"]):
            _cmd_config_llm_modules()

        lines = capsys.readouterr().out.splitlines()
        llm_lines = [ln for ln in lines if " [" in ln and ln.split(" [")[0].rstrip().endswith(". 持仓变动复盘归因")]
        feature_lines = [ln for ln in lines if " [" in ln and ln.split(" [")[0].rstrip().endswith(". 持仓变动复盘")]
        assert len(llm_lines) == 1, "LLM 模块行应唯一出现"
        assert len(feature_lines) == 1, "独立组开关行应唯一出现"
        assert "章本体在「独立组」" in llm_lines[0]
        assert "归因在「LLM 区」" in feature_lines[0]
        # 其余行不携带互指提示（标注不扩散）
        other = [ln for ln in lines if "章本体在「独立组」" in ln or "归因在「LLM 区」" in ln]
        assert len(other) == 2

    @patch("src.python.tui.handlers_config.press_any_key")
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
    def test_hints_are_readonly_annotations(
        self, mock_read, mock_names, mock_filter, mock_save, mock_refresh, mock_press, capsys
    ):
        """互指标注纯只读：渲染不触发任何配置写入。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["0"]):
            _cmd_config_llm_modules()

        assert "章本体在「独立组」" in capsys.readouterr().out
        mock_save.assert_not_called()


class TestPanelPlainLanguageCopy:
    """[S] 面板用户文案白话化：不出现开发者术语 slug（页脚/帮助/报错全量断言）。"""

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_render_and_help_have_no_dev_jargon(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, capsys
    ):
        """面板渲染 + `?` 未识别帮助 + r 未识别提示：全部用「键名」，无 'slug'。"""
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["? nope", "r nope", "0"]):
            _cmd_config_llm_modules()

        out = capsys.readouterr().out
        # input() 的提示串在 input 被 mock 后不会上屏，页脚文案按源码断言（同
        # test_boards_panel_points_to_switch_menu 的取法）
        from pathlib import Path

        src = (Path(__file__).resolve().parents[4] / "src" / "python" / "tui" / "handlers_config.py").read_text(
            encoding="utf-8"
        )
        assert "输入编号或键名切换 (0-" in src
        assert "请输入 ? 加编号或键名" in out
        assert "输入编号或键名" in out
        assert "slug" not in out and "slug" not in src


class TestLlmRowCostSuffix:
    """[S] LLM 模块行尾历史费用摘要：近 N 日累计/次数/均值，读取失败静默省略。"""

    def _render(self, capsys):
        from src.python.tui.handlers_config import _cmd_config_llm_modules

        with patch("builtins.input", side_effect=["0"]):
            _cmd_config_llm_modules()
        return capsys.readouterr().out

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.core.perf.module_cost_summary")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_row_carries_window_cost(
        self, mock_read, mock_names, mock_filter, mock_cost, mock_refresh, mock_press, capsys
    ):
        """有费用样本的模块行附近 7 日累计/次数/均值，无样本模块行不带摘要。"""
        mock_cost.return_value = {"global_macro": {"total": 1.234567, "runs": 3, "avg": 0.411522}}
        out = self._render(capsys)
        gm_lines = [
            ln for ln in out.splitlines() if " [" in ln and ln.split(" [")[0].rstrip().endswith(". 全球政经局势")
        ]
        assert len(gm_lines) == 1
        assert "近7日 ¥1.2346（3 次 · 均 ¥0.4115）" in gm_lines[0]
        er_lines = [
            ln for ln in out.splitlines() if " [" in ln and ln.split(" [")[0].rstrip().endswith(". 智囊团深度复盘")
        ]
        assert len(er_lines) == 1
        assert "近7日" not in er_lines[0]

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.core.perf.module_cost_summary", side_effect=RuntimeError("boom"))
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_read_failure_is_silent(
        self, mock_read, mock_names, mock_filter, mock_cost, mock_refresh, mock_press, capsys
    ):
        """费用摘要读取异常：面板照常渲染、无摘要文本、不抛错。"""
        out = self._render(capsys)
        assert "配置 LLM 报告章节与功能开关" in out
        assert "近7日" not in out

    @patch("src.python.tui.handlers_config.press_any_key")
    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value=_STANDARD_LLM_MODULES)
    @patch("src.python.core.registry.get_llm_module_names")
    @patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json"))
    def test_default_render_uses_real_summary(
        self, mock_read, mock_names, mock_filter, mock_refresh, mock_press, capsys
    ):
        """未打桩时走真实 module_cost_summary（真实 perf 历史），面板不抛错。"""
        out = self._render(capsys)
        assert "配置 LLM 报告章节与功能开关" in out
