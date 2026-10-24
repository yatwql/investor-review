"""test_handlers_config 兄弟分片（switch）：[S] 章节内容面板的只读信息 / 切换 / 实验开关。

``[S]`` 只呈现 ``PANEL_GROUPS["[S]"]`` 的六组（20 项）内容开关；LLM 章节 / 独立
整章 / 关联产物在 ``[C]``，其面板用例见 ``test_handlers_report_chapters``。
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _switch_menu_number(flag: str) -> int:
    """按面板同一派生规则计算某功能开关的菜单编号（测试输入用）。

    编号 = ``panel_option_numbers("[S]")`` 的序号——注册表新增/挪动开关时自动
    跟随；硬编码编号会静默错位成「切换了别的开关」。
    """
    from src.python.config.features import panel_option_numbers

    for number, name, _definition in panel_option_numbers("[S]"):
        if name == flag:
            return number
    raise AssertionError(f"开关不在 [S] 面板上屏：{flag}")


class TestContentPanelToggles:
    """[S] 面板：编号由注册表派生，切换落到 features.json（六组顺序稳定）。"""

    def _toggle(self, flag: str, capsys) -> None:
        from src.python.tui.handlers_config import _cmd_config_content_options

        with (
            patch("builtins.input", side_effect=[str(_switch_menu_number(flag)), "0"]),
            patch("src.python.config.features.save_feature_overrides") as save,
            patch("src.python.tui.handlers_config.refresh_config"),
        ):
            _cmd_config_content_options()
        return save

    def test_menu_number_toggles_decision_reflection(self, capsys):
        """输入决策跨期反思闭环的派生编号 → 切换机制与质量块内该项。"""
        save = self._toggle("decision_reflection", capsys)
        save.assert_called_once_with({"decision_reflection": True})

    def test_menu_number_toggles_prosperity_framework(self, capsys):
        """输入景气度框架诊断的派生编号 → 切换该开关（默认开 → 关）。"""
        save = self._toggle("prosperity_framework", capsys)
        save.assert_called_once_with({"prosperity_framework": False})

    def test_menu_number_toggles_promoted_standard_switch(self, capsys):
        """非实验项同样可切（转正不等于不可关）：确定性信号模块默认开 → 关。"""
        save = self._toggle("deterministic_signal", capsys)
        save.assert_called_once_with({"deterministic_signal": False})

    def test_derived_number_toggles_switch(self, capsys):
        """编号全部由面板注册表派生：任意一项按其派生编号都能精确命中。"""
        flag = "metrics_enabled"
        save = self._toggle(flag, capsys)
        save.assert_called_once_with({flag: False})

    def test_numbering_is_contiguous_from_registry(self, capsys):
        """面板编号 1..N 连续，且与注册表组序一致（不写死条数）。"""
        from src.python.config.features import PANEL_GROUPS, panel_option_numbers, switches_in_group

        numbered = panel_option_numbers("[S]")
        assert [n for n, _f, _d in numbered] == list(range(1, len(numbered) + 1))
        expected = [flag for group in PANEL_GROUPS["[S]"] for flag, _d in switches_in_group(group)]
        assert [f for _n, f, _d in numbered] == expected


class TestGlobalSettingsMenu:
    """[G] 全局设置七项：数字/字母双通道、入口地图只读、无效输入与 EOF 兜底。

    目录项（持仓信息目录 / 文件名 / 输出目录）与配置入口地图直接挂在 `[G]` 二级，
    不再经中间子面板——同一配置只有一条入口路径。
    """

    @staticmethod
    def _patch_handlers(calls: list[str]):
        from unittest.mock import patch as _patch

        return _patch.dict(
            "src.python.tui.handlers_config.__dict__",
            {
                "_cmd_config_dir": lambda: calls.append("dir"),
                "_cmd_config_filename": lambda: calls.append("file"),
                "_cmd_config_output_dir": lambda: calls.append("out"),
                "_render_config_entry_map": lambda: calls.append("map"),
            },
        )

    def test_letters_dispatch_directly(self):
        """H/F/O/M 四个目录与索引项直接派发（无中间层）。"""
        from src.python.tui.handlers_config import _cmd_global_settings

        calls: list[str] = []
        with self._patch_handlers(calls), patch("builtins.input", side_effect=["H", "F", "O", "M", "0"]):
            _cmd_global_settings()
        assert calls == ["dir", "file", "out", "map"]

    def test_lowercase_letter_accepted(self):
        """小写字母归一化为大写后派发。"""
        from src.python.tui.handlers_config import _cmd_global_settings

        calls: list[str] = []
        with self._patch_handlers(calls), patch("builtins.input", side_effect=["h", "0"]):
            _cmd_global_settings()
        assert calls == ["dir"]

    def test_number_equivalent_to_letter(self):
        """编号与字母双通道等价（编号是第一入口）。"""
        from src.python.tui.handlers_config import GLOBAL_SETTINGS_ITEMS, _cmd_global_settings

        calls: list[str] = []
        index = next(i for i, item in enumerate(GLOBAL_SETTINGS_ITEMS, 1) if item[0] == "M")
        with self._patch_handlers(calls), patch("builtins.input", side_effect=[str(index), "0"]):
            _cmd_global_settings()
        assert calls == ["map"]

    def test_invalid_choice_reprompts(self):
        """无效键提示后重新等待输入，不误触发任何处理器。"""
        from src.python.tui.handlers_config import _cmd_global_settings

        calls: list[str] = []
        with self._patch_handlers(calls), patch("builtins.input", side_effect=["Z", "0"]):
            _cmd_global_settings()
        assert calls == []

    def test_zero_and_empty_return(self):
        """`0` 与空回车都返回主菜单，不派发任何项。"""
        from src.python.tui.handlers_config import _cmd_global_settings

        calls: list[str] = []
        with self._patch_handlers(calls), patch("builtins.input", side_effect=["0", ""]):
            _cmd_global_settings()
        assert calls == []

    def test_eof_returns_safely(self):
        """EOF（非交互输入）不抛异常：读取一次即返回。"""
        from src.python.tui.handlers_config import _cmd_global_settings

        calls: list[str] = []
        with self._patch_handlers(calls), patch("builtins.input", side_effect=EOFError):
            _cmd_global_settings()
        assert calls == []


class TestSwitchPanelReadonlyInfo:
    """[S] 面板只读信息面：? 编号详情 / * 漂移标记 / ⚗ 启用统计上屏。"""

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=[f"? {_switch_menu_number('decision_reflection')}", "0"])
    @patch("src.python.config.features.save_feature_overrides")
    def test_question_mark_shows_feature_detail_readonly(self, mock_save, mock_input, mock_refresh, capsys):
        """`? 编号` 上屏说明/当前/默认/存储键，纯只读（不触发任何配置写入）。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "登记决策 → 真实行情结算命中率 → 教训回灌专家复盘提示词" in out, "注册表 desc 应上屏"
        assert "features.json → decision_reflection" in out
        assert "出厂默认" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["? abc", "? 9999", "0"])
    @patch("src.python.config.features.save_feature_overrides")
    def test_question_mark_invalid_input_reprompts(self, mock_save, mock_input, mock_refresh, capsys):
        """非数字编号与越界编号均给出行内提示并回到面板，不抛出、不写配置。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "请输入 ? 加编号" in out
        assert "无效编号" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["？1", "0"])
    @patch("src.python.config.features.save_feature_overrides")
    def test_full_width_question_mark_shows_detail(self, mock_save, mock_input, mock_refresh, capsys):
        """全角 `？`（中文输入法默认输出）与半角 `?` 同效上屏说明，同样只读。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "features.json →" in out
        assert "出厂默认" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["0"])
    @patch("src.python.tui.handlers_config.filter_menu_llm_modules", return_value={})
    def test_non_default_feature_star_marked(self, mock_filter, mock_input, mock_refresh, capsys):
        """功能开关与出厂默认不一致时行尾标 *（默认关的开关被置开）。"""
        import re

        from src.python.config.features import set_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_content_options

        set_feature_enabled("decision_reflection", True)
        try:
            _cmd_config_content_options()
            out = capsys.readouterr().out
            assert re.search(r"决策跨期反思闭环\s+decision_reflection\s+\[开启\]\*", out), (
                f"应有 [开启]* 漂移标记:\n{out}"
            )
        finally:
            set_feature_enabled("decision_reflection", False)

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("builtins.input", side_effect=["0"])
    def test_experiment_stats_suffix_on_experimental_row(self, mock_input, mock_refresh, capsys, tmp_path, monkeypatch):
        """⚗ 实验项行尾附启用统计（次数 + 最近日期 MM-DD），数据来自 experiment_stats。"""
        from src.python.core import experiment_stats
        from src.python.tui.handlers_config import _cmd_config_content_options

        stats_file = tmp_path / "experiment_stats.json"
        stats_file.write_text(
            json.dumps({"decision_reflection": {"enabled_count": 5, "last_enabled_date": "2026-10-13"}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(experiment_stats, "EXPERIMENT_STATS_FILE", str(stats_file))

        _cmd_config_content_options()

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
        from src.python.core.json_comments import strip_json_comments

        return json.loads(strip_json_comments(path.read_text(encoding="utf-8")))

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_restore_group_clears_overrides_in_group(self, mock_refresh, tmp_path, monkeypatch, capsys):
        """`r 编号` 只恢复该项所在分组的覆写（跨组键保留），运行时回出厂默认。"""
        from src.python.config.features import is_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_content_options

        path = self._seed(tmp_path, monkeypatch, {"deterministic_signal": False, "market_temperature": False})
        with patch("builtins.input", side_effect=[f"r {_switch_menu_number('deterministic_signal')}", "0"]):
            _cmd_config_content_options()

        assert self._read(path) == {"market_temperature": False}, "同组 deterministic_signal 覆写应删、跨组键保留"
        assert is_feature_enabled("deterministic_signal") is True, "运行时应回出厂默认"
        assert is_feature_enabled("market_temperature") is False

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_restore_all_clears_file(self, mock_refresh, tmp_path, monkeypatch, capsys):
        """`ra` 清空全部覆写（恢复全部默认），文件保留为空对象。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        path = self._seed(
            tmp_path, monkeypatch, {"deterministic_signal": False, "market_temperature": False, "cost_lots": True}
        )
        with patch("builtins.input", side_effect=["ra", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "已恢复功能开关全部默认（移除 3 项覆写）" in out
        assert self._read(path) == {}

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_experimental_all_switched_off(self, mock_refresh, tmp_path, monkeypatch, capsys):
        """`x` 实验项一键全关：experimental 集合回默认（删覆写），文件内实验键清掉。"""
        from src.python.config.features import experimental_flags, is_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_content_options

        path = self._seed(tmp_path, monkeypatch, {"decision_reflection": True, "report_qa": True, "cost_lots": True})
        with patch("builtins.input", side_effect=["x", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "实验项已全部关闭（回到无实验态）" in out
        for flag, _d in experimental_flags():
            assert flag in out, "被关闭的实验项应列出"
            assert is_feature_enabled(flag) is False
        assert self._read(path) == {"cost_lots": True}, "非实验键不受影响"

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_feature_slug_toggles_without_number(self, mock_refresh, tmp_path, monkeypatch, capsys):
        """裸键名直接切换（编号/键名双通道，编号漂移免疫）。"""
        from src.python.config.features import is_feature_enabled
        from src.python.tui.handlers_config import _cmd_config_content_options

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["deterministic_signal", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "确定性信号模块" in out and "已关闭" in out
        assert is_feature_enabled("deterministic_signal") is False
        assert self._read(path) == {"deterministic_signal": False}

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_assignment_uses_cli_vocabulary(self, mock_refresh, tmp_path, monkeypatch, capsys):
        """`键名=on|off` 与 CLI --feature 同词表同解析（两次赋值均落盘）。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["deterministic_signal=off", "deterministic_signal=on", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert out.count("已关闭") >= 1 and out.count("已开启") >= 1
        assert self._read(path) == {"deterministic_signal": True}

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_assignment_invalid_value_reports_cli_error(self, mock_refresh, tmp_path, monkeypatch, capsys):
        """非法取值走 CLI 解析器词表报错，不写盘、状态不变。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["deterministic_signal=maybe", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "取值 'maybe' 不可识别" in out
        assert self._read(path) == {}

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_restore_unknown_target_reports(self, mock_refresh, tmp_path, monkeypatch, capsys):
        """`r 不存在的目标` 给出行内提示，不抛出、不写盘。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        path = self._seed(tmp_path, monkeypatch, {})
        with patch("builtins.input", side_effect=["r nope", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "未识别目标" in out and "输入编号或键名" in out
        assert self._read(path) == {}

    @patch("src.python.tui.handlers_config.refresh_config")
    @patch("src.python.config.features.save_feature_overrides")
    def test_question_mark_slug_detail_readonly(self, mock_save, mock_refresh, capsys):
        """`? 键名` 与编号通道同源上屏详情，纯只读。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        with patch("builtins.input", side_effect=["? deterministic_signal", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "features.json → deterministic_signal" in out
        assert "出厂默认" in out
        mock_save.assert_not_called()

    @patch("src.python.tui.handlers_config.refresh_config")
    def test_unknown_input_reports_three_channel_hint(self, mock_refresh, capsys):
        """未知输入给出三通道提示（编号 / 键名 / 键名=on|off），不抛出。"""
        from src.python.tui.handlers_config import _cmd_config_content_options

        with patch("builtins.input", side_effect=["definitely_nope", "0"]):
            _cmd_config_content_options()

        out = capsys.readouterr().out
        assert "未知编号或键名" in out and "键名=on|off" in out
