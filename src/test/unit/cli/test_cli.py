"""CLI 命令行模式单元测试。

覆盖参数解析、CliProgressReporter、报告/缓存路由、退出码。

兄弟分片：test_cli_subcommands.py（view-logs / doctor / cassettes 子命令）。"""

from __future__ import annotations
import pytest
from src.python.cli import (
    _apply_cli_experiments,
    _apply_cli_switches,
    _build_parser,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


@pytest.mark.unit
class TestArgparse:
    """CLI 参数解析测试。"""

    def test_whatif_effective_date_accepts_strict_format(self):
        """--effective-date 合法 YYYY-MM-DD → 解析保留归一化值（共享层规则）。"""
        args = _build_parser().parse_args(["whatif", "--candidate", "c.xlsx", "--effective-date", "2026-07-01"])
        assert args.effective_date == "2026-07-01"

    def test_whatif_effective_date_rejects_compact_format(self):
        """--effective-date 紧凑式（20260101）→ argparse 类型错误退出 2，不再进入业务链。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["whatif", "--candidate", "c.xlsx", "--effective-date", "20260101"])
        assert exc.value.code == 2

    def test_global_help(self):
        """--help 输出主帮助信息。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["--help"])
        assert exc.value.code == 0

    def test_global_version(self):
        """--version 输出版本号。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["--version"])
        assert exc.value.code == 0

    def test_report_subcommand(self):
        """report 子命令默认参数。"""
        args = _build_parser().parse_args(["report"])
        assert args.command == "report"
        assert args.type == "basic"
        assert args.history is None  # 未显式传 --history → 由配置层 history.fetch_mode 决定
        assert args.force_llm is False

    def test_report_type_both(self):
        """report --type both 解析。"""
        args = _build_parser().parse_args(["report", "--type", "both"])
        assert args.type == "both"

    def test_report_type_full(self):
        """report --type full 解析。"""
        args = _build_parser().parse_args(["report", "--type", "full"])
        assert args.type == "full"

    def test_report_history_auto(self):
        """report --history auto 解析。"""
        args = _build_parser().parse_args(["report", "--history", "auto"])
        assert args.history == "auto"

    def test_report_force_llm(self):
        """report --force-llm 标志解析。"""
        args = _build_parser().parse_args(["report", "--force-llm"])
        assert args.force_llm is True

    def test_cache_subcommands(self):
        """cache 子命令及其互斥操作。"""
        args = _build_parser().parse_args(["cache", "--clean"])
        assert args.command == "cache"
        assert args.clean is True

        args = _build_parser().parse_args(["cache", "--stats"])
        assert args.stats is True

        args = _build_parser().parse_args(["cache", "--update", "basic"])
        assert args.update == "basic"

    def test_global_config(self):
        """--config 全局参数解析。"""
        args = _build_parser().parse_args(["--config", "/tmp/test.json", "report"])
        assert args.config == "/tmp/test.json"

    def test_global_verbose(self):
        """--verbose 全局标志解析。"""
        args = _build_parser().parse_args(["--verbose", "report"])
        assert args.verbose is True

    def test_global_output(self):
        """--output 全局参数解析。"""
        args = _build_parser().parse_args(["--output", "/tmp/reports", "report"])
        assert args.output == "/tmp/reports"

    def test_experiment_absent_by_default(self):
        """未指定 --experiment 时为 None（不触碰运行时开关）。"""
        args = _build_parser().parse_args(["report"])
        assert args.experiment is None

    def test_experiment_by_flag_name(self):
        """--experiment 接受开关名。"""
        args = _build_parser().parse_args(["--experiment", "decision_reflection", "report"])
        assert args.experiment == [("decision_reflection",)]

    def test_experiment_by_display_name(self):
        """--experiment 接受中文显示名（与 TUI 菜单 S 同源）。"""
        from src.python.config.features import feature_switch_registry

        _label = feature_switch_registry["decision_reflection"].label
        args = _build_parser().parse_args(["--experiment", _label, "report"])
        assert args.experiment == [("decision_reflection",)]

    def test_experiment_repeatable(self):
        """--experiment 可重复指定，逐项独立解析（键名与显示名混用）。"""
        args = _build_parser().parse_args(
            ["--experiment", "decision_reflection", "--experiment", "决策跨期反思闭环", "report"]
        )
        assert args.experiment == [("decision_reflection",), ("decision_reflection",)]

    def test_experiment_all(self):
        """--experiment all 展开为全部实验功能。"""
        from src.python.config.features import experimental_flags

        expected = tuple(sorted(flag for flag, _d in experimental_flags()))
        args = _build_parser().parse_args(["--experiment", "all", "report"])
        assert args.experiment == [expected]

    def test_experiment_unknown_rejected(self):
        """未知名称 → argparse 报错 SystemExit(2)，不静默忽略。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["--experiment", "no_such_feature", "report"])
        assert exc.value.code == 2

    def test_invalid_command(self):
        """未知命令 → SystemExit(2)。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["unknown"])
        assert exc.value.code == 2

    def test_cache_missing_action(self):
        """cache 不带操作参数 → SystemExit(2)（互斥组 required=True）。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["cache"])
        assert exc.value.code == 2

    def test_whatif_subcommand(self):
        """whatif 子命令：--candidate 必填、--base 可选。"""
        args = _build_parser().parse_args(["whatif", "--candidate", "after.xlsx"])
        assert args.command == "whatif"
        assert args.candidate == "after.xlsx"
        assert args.base is None

        args = _build_parser().parse_args(["whatif", "--base", "before.xlsx", "--candidate", "after.xlsx"])
        assert args.base == "before.xlsx"
        assert args.candidate == "after.xlsx"

    def test_whatif_missing_candidate(self):
        """whatif 不带 --candidate → SystemExit(2)。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["whatif"])
        assert exc.value.code == 2

    def test_whatif_effective_date_parse(self):
        """whatif --effective-date 解析。"""
        args = _build_parser().parse_args(["whatif", "--candidate", "after.xlsx", "--effective-date", "2026-07-01"])
        assert args.effective_date == "2026-07-01"

        args = _build_parser().parse_args(["whatif", "--candidate", "after.xlsx"])
        assert args.effective_date is None


@pytest.mark.unit
class TestArgparseFeatureOverrides:
    """--feature NAME=VALUE 参数解析（全注册表、双向、即时校验）。"""

    def test_feature_absent_by_default(self):
        """未指定 --feature 时为 None（不触碰运行时开关）。"""
        args = _build_parser().parse_args(["report"])
        assert args.feature is None

    def test_feature_off_on_standard_switch(self):
        """常规开关也能经 --feature 关闭——本批次补上的正是这条通道。"""
        args = _build_parser().parse_args(["--feature", "report_qa=off", "report"])
        assert args.feature == [("report_qa", False)]

    def test_feature_on_experimental_switch(self):
        """实验开关同样可经 --feature 打开（与 --experiment 等价路径）。"""
        args = _build_parser().parse_args(["--feature", "deterministic_signal=on", "report"])
        assert args.feature == [("deterministic_signal", True)]

    def test_feature_repeatable(self):
        """可重复指定，逐项独立解析并保留顺序。"""
        args = _build_parser().parse_args(
            ["--feature", "metrics_enabled=off", "--feature", "data_quality=off", "report"]
        )
        assert args.feature == [("metrics_enabled", False), ("data_quality", False)]

    def test_feature_unknown_name_rejected(self):
        """未知开关名 → SystemExit(2)（解析期报错，不留到运行时静默失效）。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["--feature", "no_such_switch=on", "report"])
        assert exc.value.code == 2

    def test_feature_bad_value_rejected(self):
        """取值不在词表内 → SystemExit(2)。"""
        with pytest.raises(SystemExit) as exc:
            _build_parser().parse_args(["--feature", "report_qa=maybe", "report"])
        assert exc.value.code == 2


@pytest.mark.unit
class TestApplyCliExperiments:
    """_apply_cli_experiments 行为测试。"""

    def test_none_is_noop(self, monkeypatch):
        """未传 --experiment 时不改动任何开关。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "deterministic_signal", False)
        _apply_cli_experiments(None)
        assert feat.FEATURE_FLAGS["deterministic_signal"] is False

    def test_empty_groups_is_noop(self, monkeypatch):
        """空列表同样不改动开关。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "decision_reflection", False)
        _apply_cli_experiments([])
        assert feat.FEATURE_FLAGS["decision_reflection"] is False

    def test_enables_requested_flags(self, monkeypatch):
        """逐项启用命令行指定的实验功能。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "prosperity_framework", False)
        monkeypatch.setitem(feat.FEATURE_FLAGS, "decision_reflection", False)
        _apply_cli_experiments([("prosperity_framework",), ("decision_reflection",)])
        assert feat.FEATURE_FLAGS["prosperity_framework"] is True
        assert feat.FEATURE_FLAGS["decision_reflection"] is True

    def test_does_not_touch_other_flags(self, monkeypatch):
        """未指定的实验功能保持原值（不误开）。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "prosperity_framework", False)
        monkeypatch.setitem(feat.FEATURE_FLAGS, "llm_debate_conditional", False)
        _apply_cli_experiments([("prosperity_framework",)])
        assert feat.FEATURE_FLAGS["llm_debate_conditional"] is False
        assert feat.FEATURE_FLAGS["llm_debate_procon"] is False

    def test_not_persisted(self, monkeypatch):
        """命令行开关仅影响本次运行，不写 features.json。"""
        from src.python.config import features as feat

        called: list[dict] = []
        monkeypatch.setattr(feat, "save_feature_overrides", lambda *a, **k: called.append({"a": a}))
        _apply_cli_experiments([("decision_reflection",)])
        assert called == []


@pytest.mark.unit
class TestApplyCliSwitches:
    """_apply_cli_switches 行为测试（--feature 双向覆写）。"""

    def test_none_is_noop(self, monkeypatch):
        """未传 --feature 时不改动任何开关。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "report_qa", True)
        _apply_cli_switches(None)
        assert feat.FEATURE_FLAGS["report_qa"] is True

    def test_disables_standard_switch(self, monkeypatch):
        """关闭常规开关——本参数相对 --experiment 的核心能力。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "report_qa", True)
        _apply_cli_switches([("report_qa", False)])
        assert feat.FEATURE_FLAGS["report_qa"] is False

    def test_enables_and_disables_in_one_run(self, monkeypatch):
        """同一次运行内双向覆写互不干扰。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "metrics_enabled", True)
        monkeypatch.setitem(feat.FEATURE_FLAGS, "deterministic_signal", False)
        _apply_cli_switches([("metrics_enabled", False), ("deterministic_signal", True)])
        assert feat.FEATURE_FLAGS["metrics_enabled"] is False
        assert feat.FEATURE_FLAGS["deterministic_signal"] is True

    def test_duplicate_key_last_wins(self, monkeypatch):
        """同名重复以最后一次为准（命令行从左到右覆盖）。"""
        from src.python.config import features as feat

        monkeypatch.setitem(feat.FEATURE_FLAGS, "metrics_enabled", True)
        _apply_cli_switches([("metrics_enabled", False), ("metrics_enabled", True)])
        assert feat.FEATURE_FLAGS["metrics_enabled"] is True

    def test_not_persisted(self, monkeypatch):
        """仅本次运行生效，不写 features.json（实验开关的关闭路径仍走面板/文件）。"""
        from src.python.config import features as feat

        called: list[dict] = []
        monkeypatch.setattr(feat, "save_feature_overrides", lambda *a, **k: called.append({"a": a}))
        _apply_cli_switches([("report_qa", False)])
        assert called == []
