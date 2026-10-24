"""CLI ``config`` 子命令与一次性覆写（``--chapter`` / ``--anonymize``）测试。

覆盖：参数解析（章节键校验、匿名化枚举）、运行时覆写的三类来源分派
（config / enabled_llm / features）、``config list/get/set`` 的读写与
``--dry-run`` 不落盘、动作型键与非法取值的拒绝口径。
"""

from __future__ import annotations

import json

import pytest

from src.python.cli.cli import _build_parser, _handle_config
from src.python.cli.cli import _apply_cli_anonymize, _apply_cli_chapters
from src.python.config import _core, get_config

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


def _run_config(argv: list[str], capsys):
    """解析并执行 config 子命令，返回 (退出码, stdout)。"""
    args = _build_parser().parse_args(argv)
    rc = _handle_config(args, get_config())
    return rc, capsys.readouterr().out


class TestConfigParser:
    """config 子命令参数解析。"""

    def test_list_default_is_not_json(self):
        args = _build_parser().parse_args(["config", "list"])
        assert args.config_action == "list"
        assert args.json is False

    def test_set_carries_key_value_and_dry_run(self):
        args = _build_parser().parse_args(["config", "set", "enable_news", "off", "--dry-run"])
        assert (args.config_action, args.key, args.value, args.dry_run) == ("set", "enable_news", "off", True)

    def test_get_requires_key(self):
        with pytest.raises(SystemExit) as caught:
            _build_parser().parse_args(["config", "get"])
        assert caught.value.code == 2


class TestChapterAndAnonymizeParser:
    """全局一次性开关的参数解析与取值校验。"""

    def test_chapter_accepts_registry_key(self):
        args = _build_parser().parse_args(["--chapter", "enable_news=off", "report"])
        assert args.chapter == [("enable_news", False)]

    def test_chapter_accepts_sub_item_key(self):
        args = _build_parser().parse_args(["--chapter", "llm_debate_procon=on", "report"])
        assert args.chapter == [("llm_debate_procon", True)]

    def test_chapter_rejects_unknown_key(self):
        with pytest.raises(SystemExit) as caught:
            _build_parser().parse_args(["--chapter", "no_such_chapter=off", "report"])
        assert caught.value.code == 2

    def test_chapter_rejects_bad_bool(self):
        with pytest.raises(SystemExit) as caught:
            _build_parser().parse_args(["--chapter", "enable_news=maybe", "report"])
        assert caught.value.code == 2

    def test_anonymize_choices(self):
        args = _build_parser().parse_args(["--anonymize", "full_anonymous", "report"])
        assert args.anonymize == "full_anonymous"
        with pytest.raises(SystemExit) as caught:
            _build_parser().parse_args(["--anonymize", "hidden", "report"])
        assert caught.value.code == 2


class TestRuntimeOverrides:
    """``--chapter`` / ``--anonymize`` 只在本进程生效，且按来源正确分派。"""

    def test_config_chapter_overrides_get_config(self):
        _core._clear_config_cache()
        assert get_config()["enable_news"] is True
        _apply_cli_chapters([("enable_news", False)])
        assert get_config()["enable_news"] is False

    def test_llm_chapter_overrides_enabled_llm(self, monkeypatch):
        import src.python.config._llm_settings as llm_settings

        monkeypatch.setattr(
            llm_settings,
            "_load_llm_config",
            lambda: {"enabled_llm": {"expert_review": True, "health_check": True}},
        )
        _apply_cli_chapters([("expert_review", False)])
        assert llm_settings.get_llm_config()["enabled_llm"]["expert_review"] is False
        assert llm_settings.get_llm_config()["enabled_llm"]["health_check"] is True

    def test_feature_chapter_uses_feature_switch(self):
        from src.python.config.features import is_feature_enabled

        _apply_cli_chapters([("stock_fundamentals", True)])
        assert is_feature_enabled("stock_fundamentals") is True

    def test_sub_item_uses_feature_switch(self):
        from src.python.config.features import is_feature_enabled

        _apply_cli_chapters([("llm_debate_procon", True)])
        assert is_feature_enabled("llm_debate_procon") is True

    def test_anonymize_override_affects_getter(self):
        from src.python.config.anonymizer import get_anonymization_mode

        assert get_anonymization_mode() == "off"
        _apply_cli_anonymize("full_anonymous")
        assert get_anonymization_mode() == "full_anonymous"

    def test_unknown_chapter_raises(self):
        from src.python.config.chapter_registry import set_chapter_runtime_override

        with pytest.raises(ValueError, match="未知章节键"):
            set_chapter_runtime_override("no_such_chapter", True)


class TestConfigReadWrite:
    """config list / get / set 的读写与拒绝口径。"""

    def test_set_then_get_round_trip(self, capsys, tmp_path):
        holdings = str(tmp_path / "holdings")
        rc, _ = _run_config(["config", "set", "holdings_dir", holdings], capsys)
        assert rc == 0
        rc, out = _run_config(["config", "get", "holdings_dir"], capsys)
        assert rc == 0
        assert json.loads(out) == holdings

    def test_dry_run_does_not_write(self, capsys):
        _run_config(["config", "set", "holdings_filename", "before.xlsx"], capsys)
        from src.python.config._config_defaults import get_config_path

        before = get_config_path()
        snapshot = open(before, encoding="utf-8").read()
        rc, out = _run_config(["config", "set", "holdings_filename", "after.xlsx", "--dry-run"], capsys)
        assert rc == 0 and "校验通过" in out
        assert open(before, encoding="utf-8").read() == snapshot
        assert get_config()["holdings_filename"] == "before.xlsx"

    def test_set_bool_rejects_invalid_token(self, capsys):
        rc, out = _run_config(["config", "set", "enable_news", "maybe"], capsys)
        assert rc == 2 and "布尔取值" in out

    def test_set_action_key_points_to_cli_alternative(self, capsys):
        rc, out = _run_config(["config", "set", "llm_providers.priority", "p2,p1"], capsys)
        assert rc == 2 and "--llm-provider-order" in out

    def test_set_unknown_key(self, capsys):
        rc, out = _run_config(["config", "set", "no_such_key", "x"], capsys)
        assert rc == 2 and "不在白名单" in out

    def test_get_action_key_rejected(self, capsys):
        rc, out = _run_config(["config", "get", "comparison_indices"], capsys)
        assert rc == 2 and "动作型" in out

    def test_list_json_contains_values_and_actions(self, capsys):
        rc, out = _run_config(["config", "list", "--json"], capsys)
        assert rc == 0
        payload = json.loads(out)
        assert "holdings_dir" in payload["values"]
        assert "scheduler.time" in payload["values"]
        assert "llm_providers.priority" in payload["actions"]


class TestSchedulerConfigSet:
    """``config set scheduler.*``：单字段落盘与严格校验。"""

    def test_set_time_normalizes_and_persists(self, capsys):
        rc, out = _run_config(["config", "set", "scheduler.time", "8:05"], capsys)
        assert rc == 0 and '"08:05"' in out
        rc, out = _run_config(["config", "get", "scheduler.time"], capsys)
        assert json.loads(out) == "08:05"

    def test_set_weekdays_parses_comma_list(self, capsys):
        rc, _ = _run_config(["config", "set", "scheduler.weekdays", "0,6"], capsys)
        assert rc == 0
        rc, out = _run_config(["config", "get", "scheduler.weekdays"], capsys)
        assert json.loads(out) == [0, 6]

    def test_invalid_time_rejected(self, capsys):
        rc, out = _run_config(["config", "set", "scheduler.time", "25:00"], capsys)
        assert rc == 2 and "HH:MM" in out

    def test_unknown_field_rejected(self, capsys):
        rc, out = _run_config(["config", "set", "scheduler.nope", "x"], capsys)
        assert rc == 2 and "未知调度字段" in out
