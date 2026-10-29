"""TUI 分层：主菜单项与分组、[G]/[D] 子菜单路由、数字/字母双通道、返回语义。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.tui import tui_menu
from src.python.tui.handlers_config import GLOBAL_SETTINGS_ITEMS, _cmd_global_settings
from src.python.tui.handlers_log import _cmd_diagnose_menu, _cmd_log_settings
from src.python.tui.text_layout import display_width

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


@pytest.fixture(autouse=True)
def _fixed_width(monkeypatch):
    """终端宽度固定为 120 列：标签宽度断言不随运行环境 $COLUMNS 漂移（autouse）。"""
    monkeypatch.setenv("COLUMNS", "120")


@pytest.mark.unit
class TestMainMenuStructure:
    def test_menu_items_are_unique_and_well_formed(self):
        """菜单项键唯一、标签非空（不写死条数：新增菜单项属良性变更）。"""
        keys = [key for key, _label, _cb, _exit in tui_menu.MENU_ITEMS]
        assert len(keys) == len(set(keys))
        assert all(label.strip() for _key, label, _cb, _exit in tui_menu.MENU_ITEMS)

    def test_group_keys_and_order(self):
        groups = dict(tui_menu.MENU_GROUPS)
        assert list(groups) == ["生成报告", "数据与查看", "持仓维护", "配置", "诊断与排查"]
        assert groups["生成报告"] == ("E", "B", "L", "W", "Q")
        assert groups["数据与查看"] == ("1", "2", "3")
        assert groups["持仓维护"] == ("U",)
        assert groups["配置"] == ("C", "S", "G", "R")
        assert groups["诊断与排查"] == ("D",)

    def test_every_item_grouped_once(self):
        grouped = [key for keys in dict(tui_menu.MENU_GROUPS).values() for key in keys]
        assert sorted(grouped) == sorted(key for key, _l, _c, _e in tui_menu.MENU_ITEMS if key != "X")

    def test_labels_within_display_width(self):
        for key, label, _cb, _exit in tui_menu.MENU_ITEMS:
            assert display_width(label) <= 48, (key, label)

    def test_removed_top_level_keys(self):
        keys = {item[0] for item in tui_menu.MENU_ITEMS}
        for retired in ("M", "I", "A", "V", "H", "T"):
            assert retired not in keys


@pytest.mark.unit
class TestGlobalSettingsMenu:
    def test_seven_items_grouped(self):
        """七项、四组：目录与文件（H/F/O）/ LLM（L）/ 基准与脱敏（I/A）/ 索引（M）。"""
        assert len(GLOBAL_SETTINGS_ITEMS) == 7
        assert {group for _l, _n, _h, group in GLOBAL_SETTINGS_ITEMS} == {
            "目录与文件",
            "LLM 调优",
            "基准与脱敏",
            "索引",
        }
        assert [letter for letter, _n, _h, _g in GLOBAL_SETTINGS_ITEMS] == ["H", "F", "O", "L", "I", "A", "M"]
        assert all(len(letter) == 1 and letter.isupper() for letter, *_ in GLOBAL_SETTINGS_ITEMS)

    def test_number_and_letter_dispatch_same_handler(self):
        calls: list[str] = []
        with patch.dict(
            "src.python.tui.handlers_config.__dict__",
            {
                "_cmd_config_dir": lambda: calls.append("dir"),
                "_cmd_config_filename": lambda: calls.append("file"),
                "_cmd_config_output_dir": lambda: calls.append("out"),
                "_cmd_config_llm_tuning": lambda: calls.append("llm"),
                "_cmd_config_comparison_indices": lambda: calls.append("idx"),
                "_cmd_config_anonymization_mode": lambda: calls.append("anon"),
                "_render_config_entry_map": lambda: calls.append("map"),
            },
        ):
            with patch("builtins.input", side_effect=["3", "O", "7", "M", "0"]):
                _cmd_global_settings()
        assert calls == ["out", "out", "map", "map"]

    def test_zero_returns(self):
        calls: list[str] = []
        with (
            patch.dict(
                "src.python.tui.handlers_config.__dict__",
                {
                    name: (lambda: calls.append(name))
                    for name in (
                        "_cmd_config_dir",
                        "_cmd_config_filename",
                        "_cmd_config_output_dir",
                        "_cmd_config_llm_tuning",
                        "_cmd_config_comparison_indices",
                        "_cmd_config_anonymization_mode",
                        "_render_config_entry_map",
                    )
                },
            ),
            patch("builtins.input", return_value="0"),
        ):
            _cmd_global_settings()
        assert calls == []


@pytest.mark.unit
class TestDiagnoseMenu:
    def test_enter_defaults_to_doctor(self):
        calls: list[str] = []
        with patch.dict(
            "src.python.tui.handlers_log.__dict__",
            {
                "_cmd_log_settings": lambda: calls.append("log"),
                "_cmd_view_logs": lambda: calls.append("view"),
                "_cmd_view_health_history": lambda: calls.append("health"),
                "_cmd_run_doctor": lambda: calls.append("doctor"),
            },
        ):
            with patch("builtins.input", side_effect=["", "0"]):
                _cmd_diagnose_menu()
        assert calls == ["doctor"]

    def test_letter_routes(self):
        calls: list[str] = []
        with patch.dict(
            "src.python.tui.handlers_log.__dict__",
            {
                "_cmd_log_settings": lambda: calls.append("log"),
                "_cmd_view_logs": lambda: calls.append("view"),
                "_cmd_view_health_history": lambda: calls.append("health"),
                "_cmd_run_doctor": lambda: calls.append("doctor"),
            },
        ):
            with patch("builtins.input", side_effect=["L", "V", "H", "T", "0"]):
                _cmd_diagnose_menu()
        assert calls == ["log", "view", "health", "doctor"]

    def test_zero_returns_without_side_effect(self):
        calls: list[str] = []
        with (
            patch.dict(
                "src.python.tui.handlers_log.__dict__",
                {
                    name: (lambda: calls.append(name))
                    for name in (
                        "_cmd_log_settings",
                        "_cmd_view_logs",
                        "_cmd_view_health_history",
                        "_cmd_run_doctor",
                    )
                },
            ),
            patch("builtins.input", return_value="0"),
        ):
            _cmd_diagnose_menu()
        assert calls == []


@pytest.mark.unit
class TestLogSettingsPanel:
    def _seed(self, tmp_path, monkeypatch):
        from src.python.config import _logging

        path = tmp_path / "logger.json"
        path.write_text(_logging.render_default_logger_config(), encoding="utf-8")
        monkeypatch.setattr(_logging, "LOGGER_CONFIG_PATH", str(path))
        monkeypatch.setattr(_logging, "get_logger_config_path", lambda: str(path))
        return path

    def test_edit_file_level(self, tmp_path, monkeypatch):
        from src.python.core.json_comments import loads

        path = self._seed(tmp_path, monkeypatch)
        with (
            patch("builtins.input", side_effect=["1", "DEBUG", "0"]),
            patch("src.python.core.logger.reload_logger_config"),
        ):
            _cmd_log_settings()

        doc = loads(path.read_text(encoding="utf-8"))
        assert doc["file"]["level"] == "DEBUG"
        assert "写盘" in path.read_text(encoding="utf-8")

    def test_invalid_value_rejected(self, tmp_path, monkeypatch, capsys):
        path = self._seed(tmp_path, monkeypatch)
        before = path.read_text(encoding="utf-8")
        with patch("builtins.input", side_effect=["4", "99", "0"]):
            _cmd_log_settings()

        assert path.read_text(encoding="utf-8") == before
        assert "[ERR]" in capsys.readouterr().out
