"""测试：test-runner 主流程 `main()` —— 参数 → 模式计划 → 编排 → 汇总 → 退出码。

覆盖：
  - `--help` 直接返回；无效模式拒绝并退出 1（提示有效模式集合）
  - 各开关的提示输出（覆盖/超时/分阶段/文档更新/失败即停/并行度）
  - 单档运行参数透传（coverage / parallel_level / timeout_override / no_timeout →
    `run_mode` 关键字参数）、计划序与 fail_fast 透传
  - 汇总退出码归一：全绿 0、任一失败取最大退出码、任一超时 124、手动中断 130
  - 汇总页写入失败只告警不改变结论；归档清理旁路异常与删除提示
  - `--machine-info` / `--update-docs` 的机器报告与耗时对照回写

全部协作件（归档/建目录/单档执行/调度器/汇总页/机器报告/文档回写/归档清理）打桩，
`_LATEST_DIR` 重定向到 `tmp_path`——不启动真实 pytest 子进程，不写真实 `test-reports/`。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SCRIPT = "test-runner.py"


@pytest.fixture(name="mod")
def fixture_mod():
    """加载 `scripts/test-runner.py` 为可测模块（每次重新执行，状态互不串扰）。"""
    return load_script(_SCRIPT, module_name="test_runner_main_probe")


class _Harness:
    """`main()` 协作件桩集合：记录调用参数，返回预设结果。"""

    def __init__(self, mod, monkeypatch, tmp_path) -> None:
        self.mod = mod
        self.tmp_path = tmp_path
        self.calls: dict[str, object] = {}
        self.run_mode_args: list[dict] = []
        self.scheduled: dict[str, object] = {}
        self.results: list[dict] = []
        self.aborted: list[str] = []
        self.archive_path: str | None = "/tmp/archive-1"
        self.prune_result = {"removed": 0, "freed_mb": 0.0, "kept": 0, "total_mb": 0.0}
        self.prune_error: Exception | None = None
        self.raise_keyboard_interrupt = False

        monkeypatch.setattr(mod, "_LATEST_DIR", str(tmp_path / "latest"))
        (tmp_path / "latest").mkdir(exist_ok=True)
        monkeypatch.setattr(mod, "archive_existing", self._archive_existing)
        monkeypatch.setattr(mod, "_create_latest_structure", self._create_structure)
        monkeypatch.setattr(mod, "run_mode", self._run_mode)
        monkeypatch.setattr(mod, "run_modes_concurrently", self._run_modes_concurrently)
        monkeypatch.setattr(mod, "_render_index_html", self._render_index_html)
        monkeypatch.setattr(mod, "_print_machine_report", self._print_machine_report)
        monkeypatch.setattr(mod, "_update_test_coverage_doc_file", self._update_doc_file)
        monkeypatch.setattr(mod, "_collect_machine_info", self._collect_machine_info)
        monkeypatch.setattr(mod, "_format_machine_info", lambda info: f"machine:{info}")
        monkeypatch.setattr(mod, "prune_archives", self._prune_archives)

    # ── 协作件 ──

    def _archive_existing(self) -> str | None:
        self.calls["archived"] = True
        return self.archive_path

    def _create_structure(self, modes_to_run: list[str]) -> None:
        self.calls["structure"] = list(modes_to_run)

    def _run_mode(self, mode_key: str, **kwargs: object) -> dict:
        self.run_mode_args.append({"mode": mode_key, **kwargs})
        return {"mode_key": mode_key, "exit_code": 0}

    def _run_modes_concurrently(self, modes, jobs, runner, fail_fast=False):
        self.scheduled = {"modes": list(modes), "jobs": jobs, "runner": runner, "fail_fast": fail_fast}
        if self.raise_keyboard_interrupt:
            raise KeyboardInterrupt
        return list(self.results), list(self.aborted)

    def _render_index_html(self, results: list[dict], coverage: bool, archive_path: str | None) -> str:
        self.calls["render"] = {
            "results": list(results),
            "coverage": coverage,
            "archive_path": archive_path,
        }
        return "<html>summary</html>"

    def _print_machine_report(self, machine_info: dict | None, results: list[dict]) -> None:
        self.calls["machine_report"] = {"info": machine_info, "results": list(results)}

    def _update_doc_file(self, machine_info: dict, results: list[dict]) -> None:
        self.calls["doc_update"] = {"info": machine_info, "results": list(results)}

    def _collect_machine_info(self, parallel_level: str = "medium", bench_jobs: int = 1) -> dict:
        return {"parallel": parallel_level, "bench_jobs": bench_jobs}

    def _prune_archives(self, archives_dir, keep=None, cap_mb=None):
        self.calls["prune"] = {"archives_dir": archives_dir, "keep": keep, "cap_mb": cap_mb}
        if self.prune_error is not None:
            raise self.prune_error
        return dict(self.prune_result)

    # ── 运行 ──

    def run(self, argv: list[str], monkeypatch) -> int | None:
        """按 argv 执行 `main()`，返回退出码（未退出返回 None）。"""
        monkeypatch.setattr(sys, "argv", [_SCRIPT, *argv])
        try:
            self.mod.main()
        except SystemExit as exc:
            return exc.code if exc.code is None else int(exc.code)
        return None


def _mode_result(exit_code: int = 0, passed: int = 3, failed: int = 0, timed_out: bool = False) -> dict:
    return {
        "mode_key": "unit",
        "exit_code": exit_code,
        "passed": passed,
        "failed": failed,
        "timed_out": timed_out,
        "duration": 1.5,
    }


@pytest.fixture(name="harness")
def fixture_harness(mod, monkeypatch, tmp_path):
    """把 `main()` 的协作件全部换成桩（含 `_LATEST_DIR` → tmp_path）。"""
    return _Harness(mod, monkeypatch, tmp_path)


class TestHelpAndModeValidation:
    def test_help_prints_contract_and_returns(self, harness, monkeypatch, capsys):
        code = harness.run(["--help"], monkeypatch)
        out = capsys.readouterr().out
        assert code is None
        assert "test-runner" in out
        assert "prune" not in harness.calls and "structure" not in harness.calls

    def test_invalid_mode_rejected_with_valid_set(self, harness, monkeypatch, capsys):
        code = harness.run(["--mode", "not-a-mode"], monkeypatch)
        out = capsys.readouterr().out
        assert code == 1
        assert "无效模式: not-a-mode" in out
        for valid in harness.mod.MODES:
            assert valid in out
        assert "structure" not in harness.calls


class TestScheduling:
    def test_mode_plan_and_run_options_passed_through(self, harness, monkeypatch):
        harness.run(
            ["--mode", "unit,integration", "--coverage", "--parallel", "low", "--timeout", "42"],
            monkeypatch,
        )
        assert harness.calls["structure"] == ["unit", "integration"]
        assert harness.scheduled["modes"] == ["unit", "integration"]
        # 调度器收到的可调用对象被调用时，按 run_one 透传全部执行选项
        harness.scheduled["runner"]("unit")
        assert harness.run_mode_args == [
            {
                "mode": "unit",
                "coverage": True,
                "parallel_level": "low",
                "timeout_override": 42,
                "no_timeout": False,
            }
        ]

    def test_no_timeout_flag_forwarded(self, harness, monkeypatch):
        harness.run(["--mode", "unit", "--no-timeout"], monkeypatch)
        harness.scheduled["runner"]("unit")
        assert harness.run_mode_args[0]["no_timeout"] is True
        assert harness.run_mode_args[0]["timeout_override"] is None

    def test_fail_fast_forwarded_to_scheduler(self, harness, monkeypatch):
        harness.run(["--mode", "unit,integration", "--fail-fast"], monkeypatch)
        assert harness.scheduled["fail_fast"] is True

    def test_jobs_cli_forwarded_and_announced_for_multi_mode(self, harness, monkeypatch, capsys):
        harness.run(["--mode", "unit,integration", "--jobs", "3"], monkeypatch)
        out = capsys.readouterr().out
        assert harness.scheduled["jobs"] == 3
        assert "并行度 jobs=3" in out

    def test_single_mode_does_not_announce_parallel(self, harness, monkeypatch, capsys):
        harness.run(["--mode", "unit", "--jobs", "3"], monkeypatch)
        assert "并行度 jobs=" not in capsys.readouterr().out


class TestSummaryAndExitCodes:
    def test_all_passed_writes_summary_and_exits_zero(self, harness, monkeypatch, capsys, tmp_path):
        harness.results = [_mode_result(passed=5), _mode_result(passed=7)]
        code = harness.run(["--mode", "unit,integration", "--coverage"], monkeypatch)
        out = capsys.readouterr().out
        assert code == 0
        assert (tmp_path / "latest" / "index.html").read_text(encoding="utf-8") == "<html>summary</html>"
        assert harness.calls["render"]["coverage"] is True
        assert harness.calls["render"]["archive_path"] == harness.archive_path
        assert "全部完成 — 12 通过, 0 失败" in out
        assert "归档清理" not in out  # removed=0 时不打印

    def test_failure_exit_code_is_max_of_modes(self, harness, monkeypatch, capsys):
        harness.results = [_mode_result(exit_code=1, failed=2), _mode_result(exit_code=3, failed=1)]
        code = harness.run(["--mode", "unit,integration"], monkeypatch)
        out = capsys.readouterr().out
        assert code == 3
        assert "存在失败的测试 — 6 通过, 3 失败" in out

    def test_any_timeout_maps_to_124(self, harness, monkeypatch, capsys):
        harness.results = [_mode_result(exit_code=0), _mode_result(exit_code=1, timed_out=True)]
        code = harness.run(["--mode", "unit,integration"], monkeypatch)
        assert code == 124
        assert "存在失败的测试" in capsys.readouterr().out

    def test_aborted_modes_listed_under_fail_fast(self, harness, monkeypatch, capsys):
        harness.results = [_mode_result(exit_code=1, failed=1)]
        harness.aborted = ["integration", "regression"]
        code = harness.run(["--mode", "unit,integration,regression", "--fail-fast"], monkeypatch)
        out = capsys.readouterr().out
        assert code == 1
        assert "已跳过 integration, regression" in out

    def test_keyboard_interrupt_exits_130_after_reporting(self, harness, monkeypatch, capsys, tmp_path):
        harness.raise_keyboard_interrupt = True
        code = harness.run(["--mode", "unit"], monkeypatch)
        out = capsys.readouterr().out
        assert code == 130
        assert "手动中断" in out
        assert harness.calls["machine_report"] == {"info": None, "results": []}
        assert "doc_update" not in harness.calls
        assert not (tmp_path / "latest" / "index.html").exists()


class TestSideEffectsAndWarnings:
    def test_summary_write_failure_warns_but_keeps_verdict(self, harness, monkeypatch, capsys, tmp_path):
        monkeypatch.setattr(harness.mod, "_LATEST_DIR", str(tmp_path / "missing-dir"))
        harness.results = [_mode_result()]
        code = harness.run(["--mode", "unit"], monkeypatch)
        out = capsys.readouterr().out
        assert code == 0
        assert "汇总页写入失败" in out

    def test_prune_removal_announced(self, harness, monkeypatch, capsys):
        harness.prune_result = {"removed": 2, "freed_mb": 1.5, "kept": 3, "total_mb": 9.0}
        harness.results = [_mode_result()]
        harness.run(["--mode", "unit", "--keep-runs", "3", "--archive-cap-mb", "7"], monkeypatch)
        out = capsys.readouterr().out
        assert "删除 2 次运行" in out
        assert harness.calls["prune"]["keep"] == 3
        assert harness.calls["prune"]["cap_mb"] == 7

    def test_prune_failure_is_non_blocking(self, harness, monkeypatch, capsys):
        harness.prune_error = OSError("archive dir unreadable")
        harness.results = [_mode_result()]
        code = harness.run(["--mode", "unit"], monkeypatch)
        out = capsys.readouterr().out
        assert code == 0
        assert "归档清理失败（非关键，继续执行）" in out

    def test_machine_info_reported_without_doc_update(self, harness, monkeypatch, capsys):
        harness.results = [_mode_result()]
        harness.run(["--mode", "unit", "--machine-info", "--parallel", "high"], monkeypatch)
        out = capsys.readouterr().out
        assert "machine:{" in out
        info = harness.calls["machine_report"]["info"]
        assert info["parallel"] == "high"
        assert isinstance(info["bench_jobs"], int) and info["bench_jobs"] >= 1
        assert "doc_update" not in harness.calls

    def test_update_docs_implies_machine_info_and_writes_doc(self, harness, monkeypatch, capsys):
        harness.results = [_mode_result()]
        harness.run(["--mode", "unit", "--update-docs"], monkeypatch)
        out = capsys.readouterr().out
        assert "文档更新: 开启" in out
        info = harness.calls["machine_report"]["info"]
        assert info["parallel"] == "medium"
        assert isinstance(info["bench_jobs"], int) and info["bench_jobs"] >= 1
        assert harness.calls["doc_update"]["results"] == harness.results

    def test_timeout_and_phased_flags_announced(self, harness, monkeypatch, capsys):
        harness.results = [_mode_result()]
        harness.run(["--mode", "unit", "--timeout", "90", "--phased"], monkeypatch)
        out = capsys.readouterr().out
        assert "超时: 统一设为 90s" in out
        assert "分阶段: 已开启" in out
