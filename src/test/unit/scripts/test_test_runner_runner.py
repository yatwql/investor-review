"""测试：test-runner 运行编排（`_test_runner/runner.py`）——目录准备 / 单档执行 / 分阶段执行。

覆盖：
  - 目录准备：`latest/` 各模式子目录与 `coverage/` 建齐
  - 历史归档：无 `latest/`、`latest/` 内无报告文件均不归档（返回 None）；有报告时整体移入
    `archives/<YYYYMMDD>/<HHMMSS>/` 并返回新路径
  - 单档执行：探针模式委派 portability、分阶段模式委派 `_run_phased`、子进程 argv/cwd/env 口径、
    超时结果映射（`timed_out`/`exit_code=-1`/duration=超时值）、`--no-timeout` 与覆盖超时、
    pytest 非测试失败退出码的可执行原因提示、pytest-html 缺失提示
  - 分阶段执行：预检失败/预检超时中止且不跑测试、单阶段无 Phase 标签、多阶段首阶段失败即跳过后续、
    阶段超时汇总、失败阶段落调试日志、日志写盘失败只提示不遮住失败本体

测试全部打桩 `subprocess.run`（不启动真实 pytest）、并把报告目录常量重定向到 `tmp_path`，
不触碰真实 `test-reports/`。
"""

from __future__ import annotations

import subprocess
import types
from pathlib import Path

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def runner_mod():
    """运行编排实现（入口脚本已把 scripts/ 载入，子包可直接导入）。"""
    load_script("test-runner.py")
    from _test_runner import runner  # pyright: ignore[reportMissingImports]  # scripts/ 由 load_script 注入 sys.path

    return runner


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    """构造一个假的子进程结果（不真实启动 pytest）。"""
    return subprocess.CompletedProcess(args=["pytest"], returncode=returncode, stdout=stdout, stderr=stderr)


class _FakeRun:
    """记录 `subprocess.run` 调用的桩：按计划返回结果或抛异常。"""

    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self.calls: list[dict] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": cmd, **kwargs})
        result = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        if isinstance(result, BaseException):
            raise result
        return result

    @property
    def argvs(self) -> list[list[str]]:
        return [call["cmd"] for call in self.calls]


def _install_fake_subprocess(monkeypatch, runner_mod, fake: _FakeRun) -> None:
    """用桩替换 runner 模块视角的 `subprocess`（保留 TimeoutExpired 供 except 分支识别）。"""
    stub = types.SimpleNamespace(run=fake, TimeoutExpired=subprocess.TimeoutExpired)
    monkeypatch.setattr(runner_mod, "subprocess", stub)


def _fake_mode(runner_mod, monkeypatch, cfg: dict) -> None:
    """把 MODES 换成只含一个伪模式的表（不执行真实 marker 表达式）。"""
    monkeypatch.setattr(runner_mod, "MODES", {"fake": cfg})


class TestDirectoryPreparation:
    """`latest/` 目录结构准备。"""

    def test_ensure_dirs_creates_nested_path(self, runner_mod, tmp_path):
        """`_ensure_dirs` 递归创建目录。"""
        target = tmp_path / "a" / "b" / "c"
        runner_mod._ensure_dirs(str(target))
        assert target.is_dir()

    def test_create_latest_structure_lays_out_modes_and_coverage(self, runner_mod, monkeypatch, tmp_path):
        """每个待跑模式各建一个子目录，另有 `coverage/`。"""
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        runner_mod._create_latest_structure(["unit", "scenario"])
        created = sorted(p.name for p in (tmp_path / "latest").iterdir())
        assert created == ["coverage", "scenario", "unit"]


class TestArchiveExisting:
    """历史报告归档：仅在 `latest/` 有报告文件时才移入 archives。"""

    def _redirect(self, runner_mod, monkeypatch, tmp_path):
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        monkeypatch.setattr(runner_mod, "_ARCHIVES_DIR", str(tmp_path / "archives"))
        monkeypatch.setattr(runner_mod, "_REPORTS_DIR", str(tmp_path))

    def test_no_latest_dir_returns_none(self, runner_mod, monkeypatch, tmp_path):
        """`latest/` 不存在 → 无可归档，返回 None（首次运行路径）。"""
        self._redirect(runner_mod, monkeypatch, tmp_path)
        assert runner_mod.archive_existing() is None

    def test_latest_without_reports_returns_none(self, runner_mod, monkeypatch, tmp_path):
        """`latest/` 存在但没有任何报告文件 → 不产生空归档目录。"""
        self._redirect(runner_mod, monkeypatch, tmp_path)
        cache = tmp_path / "latest" / "unit"
        cache.mkdir(parents=True)
        (cache / "notes.txt").write_text("非报告文件", encoding="utf-8")

        assert runner_mod.archive_existing() is None
        assert not (tmp_path / "archives").exists()

    def test_reports_are_moved_into_dated_archive(self, runner_mod, monkeypatch, tmp_path, capsys):
        """有报告文件 → 整个 `latest/` 移入 `archives/<date>/<time>/` 并返回该路径。"""
        self._redirect(runner_mod, monkeypatch, tmp_path)
        unit_dir = tmp_path / "latest" / "unit"
        unit_dir.mkdir(parents=True)
        (unit_dir / "report.html").write_text("<html></html>", encoding="utf-8")

        archived = runner_mod.archive_existing()

        assert archived is not None
        assert Path(archived, "unit", "report.html").is_file()
        assert not (tmp_path / "latest").exists()
        assert "历史报告已归档" in capsys.readouterr().out


class TestRunMode:
    """单档执行：委派分支、子进程口径、结果映射与提示。"""

    def test_probe_mode_delegates_to_portability(self, runner_mod, monkeypatch):
        """探针模式（非 pytest）委派 `run_portability`，透传超时与描述。"""
        from _test_runner import portability  # pyright: ignore[reportMissingImports]

        seen: dict = {}

        def _stub(mode_key, **kwargs):
            seen["mode_key"] = mode_key
            seen.update(kwargs)
            return {"mode": mode_key, "probes": True, "exit_code": 0}

        monkeypatch.setattr(portability, "run_portability", _stub)

        stats = runner_mod.run_mode("portability", timeout_override=11, no_timeout=True)

        assert stats["probes"] is True
        assert seen["mode_key"] == "portability"
        assert seen["timeout_override"] == 11
        assert seen["no_timeout"] is True
        assert seen["desc"]  # 模式描述随委派透传

    def test_phased_mode_delegates_to_run_phased(self, runner_mod, monkeypatch):
        """定义了 `phases` 的模式委派 `_run_phased`，参数顺序与 CLI 口径一致。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "phases": [{"marker": "unit"}]})
        seen: dict = {}

        def _stub(phases, mode_key, coverage, parallel_level, timeout_override, no_timeout):
            seen.update(
                phases=phases,
                mode_key=mode_key,
                coverage=coverage,
                parallel_level=parallel_level,
                timeout_override=timeout_override,
                no_timeout=no_timeout,
            )
            return {"mode": mode_key, "phased": True}

        monkeypatch.setattr(runner_mod, "_run_phased", _stub)

        stats = runner_mod.run_mode("fake", coverage=True, parallel_level="low", timeout_override=9, no_timeout=False)

        assert stats["phased"] is True
        assert seen == {
            "phases": [{"marker": "unit"}],
            "mode_key": "fake",
            "coverage": True,
            "parallel_level": "low",
            "timeout_override": 9,
            "no_timeout": False,
        }

    def test_success_maps_counts_and_env(self, runner_mod, monkeypatch, tmp_path):
        """成功一轮：计数/耗时/退出码落进结果表，且子进程带测试环境标识与仓库根 cwd。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 42})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        fake = _FakeRun([_completed(0, "12 passed, 1 skipped in 3.2s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        stats = runner_mod.run_mode("fake", parallel_level="low")

        assert (stats["passed"], stats["skipped"], stats["failed"]) == (12, 1, 0)
        assert stats["duration"] == pytest.approx(3.2)
        assert (stats["mode"], stats["desc"], stats["exit_code"]) == ("fake", "伪模式", 0)
        assert stats["timed_out"] is False

        call = fake.calls[0]
        assert call["cmd"][1:3] == ["-m", "pytest"]
        assert "-m" in call["cmd"] and "unit" in call["cmd"]
        assert call["env"]["INVEST_RUNNING_TESTS"] == "1"
        assert call["cwd"] == runner_mod._PROJECT_ROOT
        assert call["timeout"] == 42

    def test_timeout_yields_timed_out_stats(self, runner_mod, monkeypatch, tmp_path):
        """子进程超时 → 结果标 `timed_out`、退出码 -1、耗时记超时值（不抛给上层）。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 7})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        fake = _FakeRun([subprocess.TimeoutExpired(cmd="pytest", timeout=7)])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        stats = runner_mod.run_mode("fake")

        assert stats["timed_out"] is True
        assert stats["exit_code"] == -1
        assert stats["duration"] == pytest.approx(7.0)
        assert stats["passed"] == 0

    def test_no_timeout_disables_watchdog(self, runner_mod, monkeypatch, tmp_path):
        """`no_timeout=True` 时不给子进程超时（长跑模式手工观察用）。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 300})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        fake = _FakeRun([_completed(0, "1 passed in 0.1s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        runner_mod.run_mode("fake", no_timeout=True)

        assert fake.calls[0]["timeout"] is None

    def test_timeout_override_wins_over_mode_default(self, runner_mod, monkeypatch, tmp_path):
        """显式超时覆盖模式默认值（CI 上临时放宽/收紧）。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 300})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        fake = _FakeRun([_completed(0, "1 passed in 0.1s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        runner_mod.run_mode("fake", timeout_override=13)

        assert fake.calls[0]["timeout"] == 13

    def test_missing_html_plugin_degrades_to_text_output(self, runner_mod, monkeypatch, tmp_path, capsys):
        """缺 pytest-html 时提示降级，且 argv 不带 `--html`（不让 pytest 用法错误退出）。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 30})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        monkeypatch.setattr(runner_mod, "_check_pytest_html", lambda: False)
        fake = _FakeRun([_completed(0, "1 passed in 0.1s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        runner_mod.run_mode("fake")

        assert "--html" not in fake.calls[0]["cmd"]
        assert "pytest-html 未安装" in capsys.readouterr().out

    def test_coverage_flag_adds_cov_args(self, runner_mod, monkeypatch, tmp_path):
        """`coverage=True` 时 argv 带覆盖率开关（报告目录取 latest/coverage）。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 30})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        monkeypatch.setattr(runner_mod, "_check_pytest_html", lambda: True)
        fake = _FakeRun([_completed(0, "1 passed in 0.1s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        runner_mod.run_mode("fake", coverage=True)

        argv = fake.calls[0]["cmd"]
        assert "--cov-report=term-missing:skip-covered" in argv
        assert any(a.startswith("--cov-report=html:") and a.endswith("coverage") for a in argv)

    def test_non_test_exit_code_prints_actionable_hint(self, runner_mod, monkeypatch, tmp_path, capsys):
        """pytest 退出码 5（未收集到用例）给出可执行原因与输出尾部，而非只报 0 passed。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "nope", "timeout_sec": 30})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        fake = _FakeRun([_completed(5, "no tests ran in 0.01s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        stats = runner_mod.run_mode("fake")

        out = capsys.readouterr().out
        assert stats["exit_code"] == 5
        assert "未收集到用例" in out
        assert "no tests ran" in out

    def test_errors_and_subtests_are_summarized(self, runner_mod, monkeypatch, tmp_path, capsys):
        """errors / subtests 非零时进入概览行（否则这类失败在摘要里看不出来）。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 30})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        fake = _FakeRun([_completed(1, "2 passed, 1 error, 3 subtests passed in 2.0s\n\n=====\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        stats = runner_mod.run_mode("fake")

        out = capsys.readouterr().out
        assert (stats["errors"], stats["subtests"]) == (1, 3)
        assert "1 errors" in out
        assert "3 subtests" in out

    def test_test_failure_reports_err_overview(self, runner_mod, monkeypatch, tmp_path, capsys):
        """普通失败（退出码 1）在概览行标 ERR，并汇总 failed 计数。"""
        _fake_mode(runner_mod, monkeypatch, {"desc": "伪模式", "marker": "unit", "timeout_sec": 30})
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        fake = _FakeRun([_completed(1, "3 passed, 2 failed in 1.5s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        stats = runner_mod.run_mode("fake")

        out = capsys.readouterr().out
        assert (stats["passed"], stats["failed"], stats["exit_code"]) == (3, 2, 1)
        assert "[ERR] fake: 3 passed, 2 failed" in out


class TestRunModesConcurrently:
    """多档并发调度：计划序返回、失败即停只取消未启动档、并行度收敛。"""

    def test_serial_run_returns_plan_order(self, runner_mod):
        """`jobs=1` 即串行；结果按计划序而非完成序排列，且无档被跳过。"""
        seen: list[str] = []

        def _run_one(mode: str) -> dict:
            seen.append(mode)
            return {"mode": mode, "exit_code": 0, "duration": 1.0}

        results, aborted = runner_mod.run_modes_concurrently(["unit", "scenario", "regression"], 1, _run_one)

        assert seen == ["unit", "scenario", "regression"]
        assert [r["mode"] for r in results] == ["unit", "scenario", "regression"]
        assert aborted == []

    def test_fail_fast_cancels_queued_modes_only(self, runner_mod):
        """首个非零结果中止：未启动的档进 aborted，已跑的档结果仍在（不强杀半途）。"""

        def _run_one(mode: str) -> dict:
            return {"mode": mode, "exit_code": 1 if mode == "unit" else 0}

        results, aborted = runner_mod.run_modes_concurrently(["unit", "scenario", "edge"], 1, _run_one, fail_fast=True)

        assert [r["mode"] for r in results] == ["unit"]
        assert aborted == ["scenario", "edge"]

    def test_jobs_clamped_to_mode_count(self, runner_mod):
        """并行度超过档数时按档数收敛（不多起线程），结果仍齐全。"""

        def _run_one(mode: str) -> dict:
            return {"mode": mode, "exit_code": 0}

        results, aborted = runner_mod.run_modes_concurrently(["unit", "edge"], 8, _run_one)

        assert [r["mode"] for r in results] == ["unit", "edge"]
        assert aborted == []

    def test_all_failing_without_fail_fast_runs_every_mode(self, runner_mod):
        """未开 fail_fast 时失败不中止：全档都跑，aborted 为空（bench 统计需要全部耗时）。"""

        def _run_one(mode: str) -> dict:
            return {"mode": mode, "exit_code": 2}

        results, aborted = runner_mod.run_modes_concurrently(["unit", "edge"], 2, _run_one)

        assert [r["exit_code"] for r in results] == [2, 2]
        assert aborted == []


class TestRunPhased:
    """分阶段执行：预检门禁、阶段标签、失败即跳过后续、超时与调试日志。"""

    def _setup(self, runner_mod, monkeypatch, tmp_path, cfg: dict) -> None:
        _fake_mode(runner_mod, monkeypatch, cfg)
        monkeypatch.setattr(runner_mod, "_LATEST_DIR", str(tmp_path / "latest"))
        monkeypatch.setattr(runner_mod, "_check_pytest_html", lambda: False)

    def test_preflight_failure_aborts_without_running_pytest(self, runner_mod, monkeypatch, tmp_path, capsys):
        """预检脚本失败 → 退出码取预检退出码，且不启动任何 pytest 进程。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式", "preflight": [["guard", "--ci"]]})
        fake = _FakeRun([_completed(2, "编号冲突\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        combined = runner_mod._run_phased([{"marker": "unit", "desc": "阶段"}], "fake", False)

        assert combined["exit_code"] == 2
        assert combined["passed"] == 0
        assert fake.argvs == [["guard", "--ci"]]
        out = capsys.readouterr().out
        assert "预检失败" in out
        assert "跳过测试阶段" in out

    def test_preflight_timeout_aborts_with_exit_code_two(self, runner_mod, monkeypatch, tmp_path, capsys):
        """预检卡死（超时）视为失败：退出码 2 并跳过测试阶段。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式", "preflight": [["guard"]]})
        fake = _FakeRun([subprocess.TimeoutExpired(cmd="guard", timeout=600)])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        combined = runner_mod._run_phased([{"marker": "unit"}], "fake", False)

        assert combined["exit_code"] == 2
        assert len(fake.calls) == 1
        assert "预检超时" in capsys.readouterr().out

    def test_single_phase_has_no_phase_tag_and_writes_plain_report(self, runner_mod, monkeypatch, tmp_path, capsys):
        """单阶段（dev-verify 合并态）不带 Phase 标签、报告写 report.html。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式"})
        monkeypatch.setattr(runner_mod, "_check_pytest_html", lambda: True)
        fake = _FakeRun([_completed(0, "24 passed in 5.0s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        combined = runner_mod._run_phased([{"marker": "unit", "desc": "唯一阶段"}], "fake", False)

        assert combined["passed"] == 24
        assert combined["exit_code"] == 0
        assert combined["timed_out"] is False
        out = capsys.readouterr().out
        assert "Phase" not in out
        argv = fake.argvs[0]
        assert Path(argv[argv.index("--html") + 1]).name == "report.html"

    def test_multi_phase_labels_reports_and_stops_on_first_failure(self, runner_mod, monkeypatch, tmp_path, capsys):
        """多阶段：每阶段独立报告文件；首阶段失败即停，后续阶段不执行。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式"})
        monkeypatch.setattr(runner_mod, "_check_pytest_html", lambda: True)
        fake = _FakeRun([_completed(1, "2 passed, 1 failed in 1.0s\n"), _completed(0, "9 passed in 2.0s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        runner_mod._create_latest_structure(["fake"])  # 失败阶段要能落调试日志
        phases = [{"marker": "unit", "desc": "首阶段"}, {"marker": "scenario", "desc": "次阶段"}]
        combined = runner_mod._run_phased(phases, "fake", False)

        assert combined["exit_code"] == 1
        assert (combined["passed"], combined["failed"]) == (2, 1)
        assert len(fake.calls) == 1  # 次阶段未启动

        argv = fake.argvs[0]
        assert Path(argv[argv.index("--html") + 1]).name == "report_phase_A.html"
        assert "-m" in argv and "unit" in argv

        out = capsys.readouterr().out
        assert "[Phase A]" in out
        assert "跳过后续阶段" in out
        assert (tmp_path / "latest" / "fake" / "phase_A_debug.log").is_file()

    def test_multi_phase_success_aggregates_counts_and_duration(self, runner_mod, monkeypatch, tmp_path):
        """两阶段全绿：计数累加、耗时按阶段墙钟求和，报告按 A/B 分开。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式"})
        fake = _FakeRun([_completed(0, "5 passed, 1 skipped in 1.0s\n"), _completed(0, "7 passed in 2.0s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)
        # 阶段墙钟取两次 time() 差值：第一阶段 1.5s、第二阶段 2.5s
        ticks = iter([100.0, 101.5, 200.0, 202.5])
        monkeypatch.setattr(runner_mod, "_time", types.SimpleNamespace(time=lambda: next(ticks)))

        phases = [{"marker": "unit"}, {"marker": "scenario"}]
        combined = runner_mod._run_phased(phases, "fake", False)

        assert combined["exit_code"] == 0
        assert (combined["passed"], combined["skipped"]) == (12, 1)
        assert combined["duration"] == pytest.approx(4.0)
        assert len(fake.calls) == 2

    def test_phase_timeout_marks_timed_out_and_breaks(self, runner_mod, monkeypatch, tmp_path):
        """阶段超时 → 汇总标 `timed_out`、退出码 -1，后续阶段不再执行。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式"})
        fake = _FakeRun([subprocess.TimeoutExpired(cmd="pytest", timeout=60), _completed(0, "1 passed in 0.1s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        phases = [{"marker": "unit", "timeout_sec": 60}, {"marker": "scenario", "timeout_sec": 60}]
        combined = runner_mod._run_phased(phases, "fake", False)

        assert combined["timed_out"] is True
        assert combined["exit_code"] == -1
        assert combined["duration"] == pytest.approx(60.0)
        assert len(fake.calls) == 1

    def test_failure_detail_block_is_printed_in_full(self, runner_mod, monkeypatch, tmp_path, capsys):
        """阶段失败的 FAILURES 段整段打印（含空行），便于直接定位失败用例。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式"})
        output = (
            "===== FAILURES =====\n"
            "___ test_foo ___\n"
            "\n"
            "assert 1 == 2\n"
            "===== short test summary info =====\n"
            "\n"
            "1 failed in 0.5s\n"
        )
        fake = _FakeRun([_completed(1, output)])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        combined = runner_mod._run_phased([{"marker": "unit"}], "fake", False)

        out = capsys.readouterr().out
        assert combined["failed"] == 1
        assert "___ test_foo ___" in out  # FAILURES 段内的详情行
        assert "assert 1 == 2" in out
        assert "1 failed in 0.5s" in out  # 段外摘要仍按关键词打印

    def test_phase_timeout_override_and_no_timeout_propagate(self, runner_mod, monkeypatch, tmp_path):
        """阶段超时同样受 `--timeout` 覆盖与 `--no-timeout` 控制。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式"})
        fake = _FakeRun([_completed(0, "1 passed in 0.1s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        runner_mod._run_phased([{"marker": "unit", "timeout_sec": 600}], "fake", False, timeout_override=17)
        runner_mod._run_phased([{"marker": "unit", "timeout_sec": 600}], "fake", False, no_timeout=True)

        assert [call["timeout"] for call in fake.calls] == [17, None]

    def test_debug_log_write_failure_is_reported_not_swallowed(self, runner_mod, monkeypatch, tmp_path, capsys):
        """调试日志写盘失败（OSError）只提示，不改变本轮失败结论。"""
        self._setup(runner_mod, monkeypatch, tmp_path, {"desc": "伪模式"})
        # 让 `latest/` 指向一个**文件**：拼接出的日志路径必然不是可写目录
        blocker = tmp_path / "latest"
        blocker.write_text("占位", encoding="utf-8")
        fake = _FakeRun([_completed(1, "1 failed in 0.5s\n")])
        _install_fake_subprocess(monkeypatch, runner_mod, fake)

        combined = runner_mod._run_phased([{"marker": "unit", "desc": "阶段"}], "fake", False)

        assert combined["exit_code"] == 1
        assert combined["failed"] == 1
        assert "详细日志写入失败" in capsys.readouterr().out
