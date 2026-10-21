"""test_cli 兄弟分片（main）：入口 / 主流程 / 早退开关。"""

from __future__ import annotations
import subprocess
import sys
import pytest
from unittest.mock import patch
from src.python.cli import (
    _EXIT_SEVERE,
    _EXIT_SUCCESS,
    main,
    run_cli,
)
from src.python.core.constants import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


@pytest.mark.unit
class TestMain:
    """main() 入口参数透传测试。"""

    def test_report_param_passthrough(self):
        """report 子命令参数正确透传给 _handle_report。"""
        with (
            patch("src.python.cli.cli._handle_report", return_value=_EXIT_SUCCESS) as mock_report,
            patch("src.python.config.init_config"),
            patch("src.python.config.get_config", return_value={}),
            patch("src.python.core.logger.setup_logger"),
        ):
            with patch.object(
                __import__("sys"),
                "argv",
                ["cli.py", "report", "--type", "full", "--history", "auto", "--force-llm"],
            ):
                main()

        mock_report.assert_called_once()
        args = mock_report.call_args[0][0]
        assert args.type == "full"
        assert args.history == "auto"
        assert args.force_llm is True

    def test_cache_param_passthrough(self):
        """cache 子命令参数正确透传给 _handle_cache。"""
        with (
            patch("src.python.cli.cli._handle_cache", return_value=_EXIT_SUCCESS) as mock_cache,
            patch("src.python.config.init_config"),
            patch("src.python.config.get_config", return_value={}),
            patch("src.python.core.logger.setup_logger"),
        ):
            with patch.object(
                __import__("sys"),
                "argv",
                ["cli.py", "cache", "--update", "all"],
            ):
                main()

        mock_cache.assert_called_once()
        args = mock_cache.call_args[0][0]
        assert args.update == "all"

    def test_whatif_param_passthrough(self):
        """whatif 子命令参数正确透传给 _handle_whatif。"""
        with (
            patch("src.python.cli.cli._handle_whatif", return_value=_EXIT_SUCCESS) as mock_whatif,
            patch("src.python.config.init_config"),
            patch("src.python.config.get_config", return_value={}),
            patch("src.python.core.logger.setup_logger"),
        ):
            with patch.object(
                __import__("sys"),
                "argv",
                ["cli.py", "whatif", "--base", "before.xlsx", "--candidate", "after.xlsx"],
            ):
                main()

        mock_whatif.assert_called_once()
        args = mock_whatif.call_args[0][0]
        assert args.command == "whatif"
        assert args.base == "before.xlsx"
        assert args.candidate == "after.xlsx"

    def test_whatif_effective_date_param_passthrough(self):
        """whatif --effective-date → _handle_whatif 收到 args.effective_date。"""
        with (
            patch("src.python.cli.cli._handle_whatif", return_value=_EXIT_SUCCESS) as mock_whatif,
            patch("src.python.config.init_config"),
            patch("src.python.config.get_config", return_value={}),
            patch("src.python.core.logger.setup_logger"),
        ):
            with patch.object(
                __import__("sys"),
                "argv",
                [
                    "cli.py",
                    "whatif",
                    "--base",
                    "before.xlsx",
                    "--candidate",
                    "after.xlsx",
                    "--effective-date",
                    "2026-07-01",
                ],
            ):
                main()

        mock_whatif.assert_called_once()
        args = mock_whatif.call_args[0][0]
        assert args.effective_date == "2026-07-01"


@pytest.mark.unit
class TestMainEarlyExitExperiments:
    """早返回命令（doctor/check-sources）的命令行实验开关（早返回命令分派回归）。

    这些命令在 ``init_config()`` 之前分派，命令行 ``--experiment`` 若不随早返回
    路径一并应用，会被静默忽略——doctor 会报告「实验开关关闭」，而用户明明
    指定了该开关，据此判断实验功能状态即得到相反答案。
    """

    @staticmethod
    def _enabled_during_dispatch(argv: list[str], patch_target: str) -> dict[str, bool]:
        """跑一次 main()，返回被分派函数执行瞬间全注册表各开关的生效值。"""
        from src.python.config.features import feature_switch_registry, is_feature_enabled

        seen: dict[str, bool] = {}

        def _record(*_args, **_kwargs) -> int:
            seen.update({flag: is_feature_enabled(flag) for flag in feature_switch_registry})
            return _EXIT_SUCCESS

        with (
            patch(patch_target, side_effect=_record),
            patch("src.python.config.init_config"),
            patch("src.python.config.get_config"),
            patch("src.python.core.logger.setup_logger"),
        ):
            with patch.object(__import__("sys"), "argv", argv):
                main()
        return seen

    @pytest.mark.parametrize(
        ("command", "patch_target"),
        [
            ("doctor", "src.python.cli.cli._handle_doctor"),
            ("check-sources", "src.python.cli.cli._handle_check_sources"),
            ("cassettes", "src.python.cli.cli._handle_cassettes"),
        ],
    )
    def test_experiment_flag_effective_on_early_exit_command(self, command, patch_target):
        """--experiment 指定的开关在该命令分派前已生效。"""
        seen = self._enabled_during_dispatch(
            ["cli.py", "--experiment", "decision_reflection", command],
            patch_target,
        )
        assert seen["decision_reflection"] is True
        assert seen["factor_catalog"] is False  # 未指定的开关（已转正，非实验项）不受影响

    def test_without_experiment_flag_keeps_defaults(self):
        """不传开关参数 → 实验项保持默认关闭（对照组，防误判为恒真）。"""
        from src.python.config.features import experimental_flags

        seen = self._enabled_during_dispatch(["cli.py", "doctor"], "src.python.cli.cli._handle_doctor")
        experimental = [flag for flag, _d in experimental_flags()]
        assert not any(seen[flag] for flag in experimental)

    @pytest.mark.parametrize(
        ("command", "patch_target"),
        [
            ("doctor", "src.python.cli.cli._handle_doctor"),
            ("cassettes", "src.python.cli.cli._handle_cassettes"),
        ],
    )
    def test_feature_flag_effective_on_early_exit_command(self, command, patch_target):
        """--feature 在早返回命令分派前已生效（含关闭常规开关的反向取值）。"""
        seen = self._enabled_during_dispatch(
            ["cli.py", "--feature", "doctor_check=off", command],
            patch_target,
        )
        assert seen["doctor_check"] is False

    def test_feature_flag_overrides_experiment_flag(self):
        """同名时显式取值覆盖 --experiment 的隐式「只开」（后者先应用）。"""
        seen = self._enabled_during_dispatch(
            ["cli.py", "--experiment", "decision_reflection", "--feature", "decision_reflection=off", "doctor"],
            "src.python.cli.cli._handle_doctor",
        )
        assert seen["decision_reflection"] is False

    def test_features_json_overrides_loaded_before_cli_flags(self):
        """早返回路径同样先读 features.json 覆写，再叠加命令行增量。"""
        import json
        import os

        from src.python.config import features

        os.makedirs(os.path.dirname(features.FEATURES_FILE), exist_ok=True)
        with open(features.FEATURES_FILE, "w", encoding="utf-8") as f:
            json.dump({"decision_reflection": True}, f)

        seen = self._enabled_during_dispatch(["cli.py", "doctor"], "src.python.cli.cli._handle_doctor")
        assert seen["decision_reflection"] is True
        # 常规开关（默认开、非实验项）不受 --experiment 取值域影响，保持默认
        from src.python.config.features import is_feature_enabled

        assert is_feature_enabled("deterministic_signal") is True


@pytest.mark.unit
class TestRunCli:
    """run_cli() 把 main() 的返回值/异常翻译为进程退出码。"""

    def test_propagates_return_code(self):
        """main() 返回的非零码必须向上抛 SystemExit（否则失败被吞成 0）。"""
        with (
            patch("src.python.cli.cli.main", return_value=_EXIT_SEVERE),
            patch("src.python.core.logger.log_app_boundary"),
        ):
            with pytest.raises(SystemExit) as exc:
                run_cli()

        assert exc.value.code == _EXIT_SEVERE

    def test_keyboard_interrupt_maps_to_130(self, caplog):
        """Ctrl-C → 130（shell 约定），不当作崩溃。"""
        with (
            patch("src.python.cli.cli.main", side_effect=KeyboardInterrupt),
            patch("src.python.core.logger.log_app_boundary"),
        ):
            with pytest.raises(SystemExit) as exc:
                run_cli()

        assert exc.value.code == 130

    def test_unhandled_exception_maps_to_severe(self):
        """未处理异常 → 2，且不得把 traceback 直接抛给用户。"""
        with (
            patch("src.python.cli.cli.main", side_effect=RuntimeError("boom")),
            patch("src.python.core.logger.log_app_boundary"),
        ):
            with pytest.raises(SystemExit) as exc:
                run_cli()

        assert exc.value.code == _EXIT_SEVERE

    def test_boundary_log_written_on_exit(self):
        """退出时记录应用边界（日志可追溯本次运行）。"""
        with (
            patch("src.python.cli.cli.main", return_value=_EXIT_SUCCESS),
            patch("src.python.core.logger.log_app_boundary") as mock_boundary,
        ):
            with pytest.raises(SystemExit):
                run_cli()

        assert mock_boundary.call_args[0][0] == "关闭"


@pytest.mark.unit
class TestModuleEntryPoint:
    """``python -m src.python.cli`` 必须把退出码传给 shell。

    回归：``__main__.py`` 曾只调 ``main()`` 而丢弃返回值，导致 ``scripts/cli.sh``
    / ``scripts/cli.ps1`` / cron / CI 调用的退出码恒为 0——``doctor``（部分失败=1、
    严重=2）与 ``cassettes --verify``（解析失败=2）的结论对外部不可见。
    这里用 ``runpy`` 以 ``__main__`` 身份执行该入口，并预先把 ``main`` 打桩为固定
    返回码，断言进程退出码就是它（而非恒 0）。
    """

    _PROBE = (
        "import runpy, src.python.cli.cli as cli; "
        "cli.main = lambda: 7; "
        "runpy.run_module('src.python.cli', run_name='__main__')"
    )

    def test_module_entry_propagates_exit_code(self):
        proc = subprocess.run(
            [sys.executable, "-c", self._PROBE],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

        assert proc.returncode == 7, f"退出码未传递（stdout={proc.stdout!r} stderr={proc.stderr!r})"
