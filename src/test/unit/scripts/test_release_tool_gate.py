"""测试：发布流程的门禁编排与归档前置 — release.py 第三部分

覆盖（设备见同目录 `_release_fixtures.py`）：
  - 门禁：守护清单与 scripts/ 实体同源且互异、regression 先行、失败即停、
    最坏退出码传递、并行度随核数收敛、设计护栏、耗时埋点
  - gate 归档前置：未迁档 / 缺批次节 / 仍是开发版 三类拦截 + 无自审条目放行
  - 发布耗时台账：`_finish_timing` 写 `logs/release.jsonl`（观测面不阻断发布）

共享设备见同目录 `_release_fixtures.py`（子进程替身 / 临时仓库夹具 / 台账样例）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.test._script_loader import load_script
from src.test.unit.scripts._release_fixtures import (
    FakeRunner,
    _mode_arg,
    isolate_release_runtime_paths,
    ns,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def rel():
    return load_script("release.py", module_name="release_tool_gate")


@pytest.fixture(autouse=True)
def _isolate_release_runtime_paths(rel, monkeypatch, tmp_path):
    """发布运行态文件（通过戳/bench 戳/耗时台账）一律重定向到 tmp。

    回归背景：`TestGateArchivePrecondition` 曾未隔离 `GATE_STAMP_FILE`——gate 成功
    用例走完尾部写入，把仓库真实的 `logs/release-gate-stamp.json` 写成夹具版本号
    （发布时间戳也被改写），使「门禁通过戳」不可信；且每次跑单测都会再污染一次。
    """
    isolate_release_runtime_paths(rel, monkeypatch, tmp_path)


# ─────────────────────────── 门禁 ───────────────────────────


class TestGate:
    @pytest.fixture(autouse=True)
    def _fresh_evolution(self, rel, monkeypatch, tmp_path):
        """门禁编排用例不读真实 folders.md 新鲜度：新鲜度断言依赖「列头日期 =
        运行当日」（墙钟 + 仓库文件状态），用例在不同时区/日期的 CI 上会因
        本地未重跑 evolution 而随机红——编排用例将其视为通过，新鲜度拦截
        行为由 TestEvolutionFreshness（纯函数）与 test_gate_stops_on_stale_
        evolution（门禁中止）单独覆盖。"""
        monkeypatch.setattr(rel, "check_evolution_freshness", lambda *_a, **_k: [])
        rf = tmp_path / "review-findings.md"
        rf.write_text("", encoding="utf-8")
        archived = tmp_path / "archived_review-findings.x.md"
        archived.write_text("", encoding="utf-8")
        monkeypatch.setattr(rel, "RF_FILE", rf)
        monkeypatch.setattr(rel, "BENCH_STAMP_FILE", tmp_path / "release-bench-stamp.json")
        monkeypatch.setattr(rel, "read_app_version", lambda _t: "0.13.12")
        monkeypatch.setattr(rel, "ledger_archive_paths", lambda _v: (archived, tmp_path / "archived_plan.md"))
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("archived", 0))
        monkeypatch.setattr(rel, "has_archive_section", lambda *_a, **_k: True)

    def test_gate_workers_converge_with_cpu(self, rel, monkeypatch):
        """并行度随核数收敛：弱机器降路、4 核+ 封顶、缺核信息取封顶、单核不下 1 路。"""
        monkeypatch.setattr(rel.os, "cpu_count", lambda: 2)
        assert rel._gate_workers() == 2
        monkeypatch.setattr(rel.os, "cpu_count", lambda: 8)
        assert rel._gate_workers() == 4
        monkeypatch.setattr(rel.os, "cpu_count", lambda: None)
        assert rel._gate_workers() == 4
        monkeypatch.setattr(rel.os, "cpu_count", lambda: 1)
        assert rel._gate_workers() == 1

    def test_guard_scripts_exist_and_unique(self, rel):
        assert len(rel.GUARD_SCRIPTS) == len(set(rel.GUARD_SCRIPTS))
        for script in rel.GUARD_SCRIPTS:
            path = _REPO_ROOT / script
            assert path.is_file(), script
            assert script.startswith("scripts/check-"), script

    def test_gate_records_step_timings(self, rel, monkeypatch, tmp_path):
        """门禁三步（并行 verify+回归 / 守护清单 / 设计护栏）入计时器。"""
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "stamp.json")
        rel._reset_timer()
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        labels = [entry["step"] for entry in rel._timer().steps]
        assert labels == ["P2 verify+regression（并行）", "P2 守护清单", "P2 设计护栏"]
        assert all(entry["elapsed_s"] >= 0 for entry in rel._timer().steps)

    def test_gate_stops_on_stale_evolution(self, rel):
        """演进对照新鲜度过期 → gate 返回 2 且不触发任何子进程（前置拦截）。"""
        stale = ["当前开发版列头 2026-10-20 ≠ 今日，先执行 scripts/release.py evolution 刷新"]
        rel.check_evolution_freshness = lambda *_a, **_k: list(stale)
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 2
        assert runner.calls == []  # 新鲜度失败即中止，回归/守护一个不跑

    def test_gate_runs_verify_and_regression_before_guards(self, rel, monkeypatch, tmp_path):
        """gate 同时跑 P1 verify 与 P2 regression（并行），且都在守护清单之前。"""
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "stamp.json")
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        mode_calls = {_mode_arg(c) for c in runner.calls if any("test-runner.py" in p for p in c)}
        assert {"verify", "regression"} <= mode_calls
        last_pytest = max(i for i, c in enumerate(runner.calls) if any("test-runner.py" in p for p in c))
        first_guard = min(i for i, c in enumerate(runner.calls) if any("check-" in p for p in c))
        assert last_pytest < first_guard
        guard_calls = [
            c
            for c in runner.calls
            if any("check-" in part for part in c) and not any("style-guardrails" in part for part in c)
        ]
        assert len(guard_calls) == len(rel.GUARD_SCRIPTS)
        assert all("--ci" in c for c in guard_calls)

    def test_gate_runs_style_guardrail(self, rel):
        """发布门禁包含设计护栏（E 级拦 / W 级观察统计；不并入守护清单清单）。"""
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        guardrail_calls = [c for c in runner.calls if any("style-guardrails" in part for part in c)]
        assert len(guardrail_calls) == 1
        assert "--ci" in guardrail_calls[0]
        # 护栏在守护清单之后执行（守护清单语义独立）
        guard_idx = max(i for i, c in enumerate(runner.calls) if any("check-doc-links" in part for part in c))
        assert runner.calls.index(guardrail_calls[0]) > guard_idx

    def test_gate_stops_on_style_guardrail_failure(self, rel):
        """设计护栏 E 级 finding → gate 非零退出并中止。"""
        responses = [
            (["scripts/test-runner.py"], (0, "", "")),
            (["scripts/check-style-guardrails.py"], (2, "强调色越权", "")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 2

    def test_gate_stops_on_regression_failure(self, rel, monkeypatch, tmp_path):
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "stamp.json")
        runner = FakeRunner(responses=[(["scripts/test-runner.py"], (1, "", "boom"))])
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 1
        assert not any(any("check-" in p for p in c) for c in runner.calls)  # 回归/verify 失败 → 守护清单一个不跑

    def test_gate_stops_on_verify_failure(self, rel, monkeypatch, tmp_path):
        """P1 verify 失败同样在合并前中止（且不写通过戳）。"""
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "stamp.json")
        runner = FakeRunner(
            responses=[
                (["scripts/test-runner.py", "verify"], (1, "", "1 failed")),
                (["scripts/test-runner.py", "regression"], (0, "291 passed", "")),
            ]
        )
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 1
        assert not rel.GATE_STAMP_FILE.exists()

    def test_gate_writes_stamp_with_code_fingerprint(self, rel, monkeypatch, tmp_path):
        """gate 全绿后写「版本 + 树指纹 + verify 项数」戳，供 publish 复用。"""
        stamp = tmp_path / "stamp.json"
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", stamp)
        runner = FakeRunner(responses=[(["scripts/test-runner.py"], (0, "— 9,000 通过, 0 失败\n", ""))])
        assert rel.cmd_gate(ns(), runner=runner) == 0
        data = json.loads(stamp.read_text(encoding="utf-8"))
        assert data["version"] == "0.13.12"
        assert data["verify_passed"] == "9000"
        assert data["fingerprint"] == rel._code_fingerprint(runner)

    @staticmethod
    def _write_bench_stamp(rel, path, runner, *, version="0.13.12", covers_unit=True, fingerprint=None):
        path.write_text(
            json.dumps(
                {
                    "version": version,
                    "modes": ["unit", "dev-verify", "regression", "integration"],
                    "covers_unit": covers_unit,
                    "code_fingerprint": fingerprint if fingerprint is not None else rel._code_fingerprint(runner),
                }
            ),
            encoding="utf-8",
        )

    def test_gate_reuses_bench_unit_instead_of_verify(self, rel, monkeypatch, tmp_path):
        """bench 已跑 unit（verify 超集）且代码指纹一致 → gate 不再重复跑 verify。"""
        stamp = tmp_path / "bench.json"
        monkeypatch.setattr(rel, "BENCH_STAMP_FILE", stamp)
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "gate.json")
        runner = FakeRunner()
        self._write_bench_stamp(rel, stamp, runner)
        assert rel.cmd_gate(ns(), runner=runner) == 0
        modes = {_mode_arg(c) for c in runner.calls if any("test-runner.py" in p for p in c)}
        assert "verify" not in modes
        assert "regression" in modes
        gate_data = json.loads((tmp_path / "gate.json").read_text(encoding="utf-8"))
        assert gate_data["verify_source"] == "bench-unit"

    def test_gate_runs_verify_when_bench_stamp_stale(self, rel, monkeypatch, tmp_path):
        """代码指纹不一致或 covers_unit=False → 回落实跑 verify（绝不盲信）。"""
        stamp = tmp_path / "bench.json"
        monkeypatch.setattr(rel, "BENCH_STAMP_FILE", stamp)
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "gate.json")
        runner = FakeRunner()
        self._write_bench_stamp(rel, stamp, runner, fingerprint="stale")
        assert rel.cmd_gate(ns(), runner=runner) == 0
        modes = {_mode_arg(c) for c in runner.calls if any("test-runner.py" in p for p in c)}
        assert "verify" in modes

        stamp.write_text(
            json.dumps({"version": "0.13.12", "covers_unit": False, "code_fingerprint": "x"}), encoding="utf-8"
        )
        runner2 = FakeRunner()
        assert rel.cmd_gate(ns(), runner=runner2) == 0
        modes2 = {_mode_arg(c) for c in runner2.calls if any("test-runner.py" in p for p in c)}
        assert "verify" in modes2

    def test_gate_with_portability_runs_probe(self, rel, monkeypatch, tmp_path):
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "stamp.json")
        runner = FakeRunner()
        assert rel.cmd_gate(ns(with_portability=True), runner=runner) == 0
        modes = {_mode_arg(c) for c in runner.calls if any("test-runner.py" in p for p in c)}
        assert "portability" in modes

    def test_gate_stamp_records_code_files_for_publish_hint(self, rel, tmp_path, monkeypatch):
        """gate 戳存逐文件哈希：publish 指纹不一致时能点名「gate 之后哪些代码动过」。"""
        stamp = tmp_path / "gate.json"
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", stamp)
        rel._write_gate_stamp("0.12.6", "fp", "9000", code_files={"src/a.py": "aa"})
        data = json.loads(stamp.read_text(encoding="utf-8"))
        assert data["code_files"] == {"src/a.py": "aa"}
        assert rel._gate.diff_code_files(
            {"src/a.py": "aa", "src/b.py": "bb"}, {"src/a.py": "cc", "src/c.py": "dd"}
        ) == ["src/a.py", "src/b.py", "src/c.py"]

    def test_gate_returns_worst_guard_code(self, rel):
        responses = [
            (["scripts/test-runner.py"], (0, "", "")),
            ([rel.GUARD_SCRIPTS[3]], (2, "finding: x", "")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 2


# ─────────────────────────── gate 归档前置 ───────────────────────────


class TestGateArchivePrecondition:
    @pytest.fixture(autouse=True)
    def _sandbox(self, rel, monkeypatch, tmp_path):
        rf = tmp_path / "review-findings.md"
        rf.write_text("", encoding="utf-8")
        archived = tmp_path / "archived_review-findings.x.md"
        archived.write_text("", encoding="utf-8")
        monkeypatch.setattr(rel, "check_evolution_freshness", lambda *_a, **_k: [])
        monkeypatch.setattr(rel, "RF_FILE", rf)
        monkeypatch.setattr(rel, "read_app_version", lambda _t: "0.13.12")
        monkeypatch.setattr(rel, "ledger_archive_paths", lambda _v: (archived, tmp_path / "archived_plan.md"))
        monkeypatch.setattr(rel, "has_archive_section", lambda *_a, **_k: True)
        # changelog 归档段非空断言同样沙箱化（否则用例结论取决于仓库真实归档内容）
        changelog_archive = tmp_path / "archived_changelog.x.md"
        changelog_archive.write_text("## [0.13.12] - 2026-10-21\n\n- **条目**：内容\n", encoding="utf-8")
        monkeypatch.setattr(rel, "archive_paths_for", lambda _v: (changelog_archive, changelog_archive.name))
        monkeypatch.setattr(rel, "release_section_has_entries", lambda *_a, **_k: True)
        return archived

    def test_pending_rows_block_gate(self, rel, monkeypatch):
        """该版本仍有未迁档条目 → gate 在跑 regression 前即中止（不浪费 20s 门禁墙钟）。"""
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("pending", 3))
        runner = FakeRunner()
        assert rel.cmd_gate(ns(), runner=runner) == 2
        assert runner.calls == []  # 前置拦截：未触发任何子进程

    def test_missing_archive_section_blocks_gate(self, rel, monkeypatch):
        """主台账已留占位但归档缺本版批次节 → 同样前置中止（防半迁移）。"""
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("archived", 0))
        monkeypatch.setattr(rel, "has_archive_section", lambda *_a, **_k: False)
        runner = FakeRunner()
        assert rel.cmd_gate(ns(), runner=runner) == 2
        assert runner.calls == []

    def test_dev_version_blocks_gate(self, rel, monkeypatch):
        monkeypatch.setattr(rel, "read_app_version", lambda _t: "0.13.12-dev")
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("archived", 0))
        assert rel.cmd_gate(ns(), runner=FakeRunner()) == 2

    def test_absent_section_passes_gate(self, rel, monkeypatch, capsys):
        """本版无自审条目（缺节）不得拦截发布——只留提示，其余门禁照跑。"""
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("absent", 0))
        assert rel.cmd_gate(ns(), runner=FakeRunner()) == 0
        assert "无「开发期已修复」节" in capsys.readouterr().out

    def test_gate_success_leaves_repo_stamp_untouched(self, rel, monkeypatch, capsys):
        """回归：gate 成功用例不得改写仓库 `logs/` 下的真实通过戳。

        缺陷现场：本类沙箱曾漏隔离 `GATE_STAMP_FILE`，`test_absent_section_passes_gate`
        走完 gate 尾部写入，把真实戳写成夹具版本号（时间戳也被刷新），
        使「门禁通过戳」不可信——且每次跑单测都再污染一次。
        """
        real = Path(rel.__file__).resolve().parent.parent / "logs" / "release-gate-stamp.json"
        before = real.read_bytes() if real.exists() else None
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("absent", 0))
        assert rel.cmd_gate(ns(), runner=FakeRunner()) == 0
        after = real.read_bytes() if real.exists() else None
        assert after == before, "单测不得改写仓库 logs/release-gate-stamp.json"

    def test_empty_changelog_section_blocks_gate(self, rel, monkeypatch, capsys):
        """归档里的发布段只有标题/占位句 → 发布记录缺内容，前置中止。

        判定口径：prepare 已拦「占位句原样归档」，gate 侧兜旁路/人工归档写出的空段——
        归档一旦落盘，正文缺失就再也补不回来。
        """
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("archived", 0))
        monkeypatch.setattr(rel, "release_section_has_entries", lambda *_a, **_k: False)
        runner = FakeRunner()
        assert rel.cmd_gate(ns(), runner=runner) == 2
        assert runner.calls == []  # 未跑任何子进程（不浪费门禁墙钟）
        assert "没有实际条目" in capsys.readouterr().out

    def test_missing_changelog_archive_blocks_gate(self, rel, monkeypatch, tmp_path):
        """缺 changelog 归档文件 → 前置中止（而不是跑到 regression 之后才失败）。"""
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("archived", 0))
        monkeypatch.setattr(rel, "archive_paths_for", lambda _v: (tmp_path / "nope.md", "nope.md"))
        runner = FakeRunner()
        assert rel.cmd_gate(ns(), runner=runner) == 2
        assert runner.calls == []


class TestTimingTelemetry:
    """发布耗时台账：`_finish_timing` 写 `logs/release.jsonl`（观测面，不得阻断发布）。"""

    def _log(self, tmp_path: Path, rel, monkeypatch) -> Path:
        log = tmp_path / "logs" / "release.jsonl"
        monkeypatch.setattr(rel, "RELEASE_LOG_FILE", log)
        constants = tmp_path / "constants.py"
        constants.write_text('APP_VERSION = "1.2.3-dev"\n', encoding="utf-8")
        monkeypatch.setattr(rel, "CONSTANTS_FILE", constants)
        return log

    def _last_record(self, log: Path) -> dict:
        lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        return json.loads(lines[-1])

    def test_record_carries_command_steps_and_version(self, rel, tmp_path, monkeypatch):
        log = self._log(tmp_path, rel, monkeypatch)
        timer = rel._reset_timer()
        with timer.step("P2 场景回归"):
            pass
        rel._finish_timing("gate", 0)
        record = self._last_record(log)
        assert record["command"] == "gate"
        assert record["ok"] is True
        assert record["version"] == "1.2.3-dev"
        assert [entry["step"] for entry in record["steps"]] == ["P2 场景回归"]
        assert record["elapsed_s"] >= record["steps"][0]["elapsed_s"] >= 0
        assert timer.step_seconds("P2 场景回归") is not None
        assert "P2 场景回归" in timer.summary()
        assert timer.steps_total >= 0

    def test_failed_command_recorded_as_not_ok(self, rel, tmp_path, monkeypatch):
        """非零退出码如实入账（发布链折在哪一步，台账能看出来）。"""
        log = self._log(tmp_path, rel, monkeypatch)
        rel._reset_timer()
        rel._finish_timing("gate", 2)
        assert self._last_record(log)["ok"] is False

    def test_failure_record_carries_step_and_failed_tests(self, rel, tmp_path, monkeypatch):
        """失败台账自证原因：失败步 / 退出码 / 报告目录 / 失败用例名。"""
        log = self._log(tmp_path, rel, monkeypatch)
        rel._reset_timer()
        runner = FakeRunner(
            responses=[
                (
                    ["scripts/test-runner.py"],
                    (
                        1,
                        "  [..] 历史报告已归档: test-reports/archives/20261024/100000/\n"
                        "FAILED src/test/x.py::test_a - assert 1 == 2\n"
                        "FAILED src/test/y.py::test_b - boom\n",
                        "",
                    ),
                )
            ]
        )
        rc = rel._run_step(
            "测试量与耗时快照回填",
            [sys.executable, "scripts/test-runner.py", "--mode", "regression"],
            tmp_path,
            runner,
        )
        assert rc == 1
        rel._finish_timing("refresh", rc)
        record = self._last_record(log)
        assert record["ok"] is False
        failure = record["failure"]
        assert failure["step"] == "测试量与耗时快照回填"
        assert failure["rc"] == 1
        assert failure["report_dir"] == "test-reports/archives/20261024/100000"
        assert set(failure["failed_tests"]) == {"src/test/x.py::test_a", "src/test/y.py::test_b"}

    def test_failure_reads_debug_log_when_stdout_has_only_summary(self, rel, tmp_path, monkeypatch):
        """test-runner 只把 FAILED 写进归档 debug.log 时，台账仍能提取用例名。"""
        log = self._log(tmp_path, rel, monkeypatch)
        report_dir = tmp_path / "test-reports" / "archives" / "20261024" / "100000"
        report_dir.mkdir(parents=True)
        (report_dir / "phase_unit_debug.log").write_text(
            "FAILED src/test/x.py::test_a - assert 1 == 2\nE   assert 1 == 2\n",
            encoding="utf-8",
        )
        rel._reset_timer()
        runner = FakeRunner(
            responses=[
                (
                    ["scripts/test-runner.py"],
                    (
                        1,
                        "  [..] 历史报告已归档: test-reports/archives/20261024/100000/\n"
                        "11446 passed, 1 failed in 40s\n",
                        "",
                    ),
                )
            ]
        )
        rc = rel._run_step(
            "测试量与耗时快照回填",
            [sys.executable, "scripts/test-runner.py", "--mode", "unit"],
            tmp_path,
            runner,
        )
        assert rc == 1
        rel._finish_timing("refresh", rc)
        failure = self._last_record(log)["failure"]
        assert failure["failed_tests"] == ["src/test/x.py::test_a"]
        assert "assert 1 == 2" in failure["tail"]

    def test_failure_falls_back_to_latest_debug_log(self, rel, tmp_path, monkeypatch):
        """归档行指向上一次报告目录（本次档的 debug.log 还在 latest）时，台账仍能点名用例。"""
        log = self._log(tmp_path, rel, monkeypatch)
        # 归档目录存在但为空：对应「stdout 的归档行是上一次运行留下的」这一时序
        (tmp_path / "test-reports" / "archives" / "20261026" / "130224").mkdir(parents=True)
        latest = tmp_path / "test-reports" / "latest" / "dev-verify"
        latest.mkdir(parents=True)
        (latest / "dev-verify_debug.log").write_text(
            "FAILED src/test/unit/web/test_runs.py::TestConcurrency::test_concurrent_submits_isolated"
            " - AssertionError\n"
            "E   AssertionError: run m_1 未在 3.0s 内完成（status=queued）\n",
            encoding="utf-8",
        )
        rel._reset_timer()
        runner = FakeRunner(
            responses=[
                (
                    ["scripts/test-runner.py"],
                    (
                        1,
                        "  [..] 历史报告已归档: test-reports/archives/20261026/130224/\n"
                        "1 failed, 8448 passed, 118 subtests passed in 45.08s\n",
                        "",
                    ),
                )
            ]
        )
        rc = rel._run_step(
            "测试量与耗时快照回填",
            [sys.executable, "scripts/test-runner.py", "--mode", "dev-verify"],
            tmp_path,
            runner,
        )
        assert rc == 1
        rel._finish_timing("refresh", rc)
        failure = self._last_record(log)["failure"]
        assert failure["failed_tests"] == [
            "src/test/unit/web/test_runs.py::TestConcurrency::test_concurrent_submits_isolated"
        ]
        assert "status=queued" in failure["tail"]

    def test_stdout_failure_lines_take_precedence_over_latest_debug_log(self, rel, tmp_path, monkeypatch):
        """stdout 已给出本次失败用例时不再读 debug.log（避免 latest 里的旧失败被当成本次）。"""
        log = self._log(tmp_path, rel, monkeypatch)
        latest = tmp_path / "test-reports" / "latest" / "unit"
        latest.mkdir(parents=True)
        (latest / "unit_debug.log").write_text("FAILED src/test/stale.py::test_old - 上次的失败\n", encoding="utf-8")
        rel._reset_timer()
        runner = FakeRunner(
            responses=[
                (
                    ["scripts/test-runner.py"],
                    (1, "FAILED src/test/fresh.py::test_now - boom\n1 failed in 3s\n", ""),
                )
            ]
        )
        rel._run_step("测试量与耗时快照回填", [sys.executable, "scripts/test-runner.py"], tmp_path, runner)
        rel._finish_timing("refresh", 1)
        failure = self._last_record(log)["failure"]
        assert failure["failed_tests"] == ["src/test/fresh.py::test_now"]

    def test_first_failure_wins_over_later_steps(self, rel, tmp_path, monkeypatch):
        """一个命令内多处失败时保留第一现场（后续失败不覆盖根因）。"""
        rel._reset_timer()
        rel._record_failure("第一步", 1, "FAILED a::b", "")
        rel._record_failure("第二步", 2, "FAILED c::d", "")
        assert rel._failure_context()["step"] == "第一步"

    def test_appends_one_line_per_command(self, rel, tmp_path, monkeypatch):
        log = self._log(tmp_path, rel, monkeypatch)
        rel._reset_timer()
        rel._finish_timing("check", 0)
        rel._reset_timer()
        rel._finish_timing("gate", 0)
        commands = [json.loads(ln)["command"] for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert commands == ["check", "gate"]

    def test_log_is_bounded_and_atomic(self, rel, tmp_path, monkeypatch):
        """台账有上限且走原子追加原语：不因长期反复发布无界增长，也不留半行。"""
        _timing = load_script("_release/_timing.py")

        log = tmp_path / "logs" / "release.jsonl"
        for i in range(8):
            _timing.append_record(log, {"command": f"cmd{i}"}, max_lines=5)
        lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 5
        assert json.loads(lines[-1])["command"] == "cmd7"
        assert all(ln.startswith("{") and ln.endswith("}") for ln in lines)

    def test_log_write_failure_raises_for_caller_decision(self, rel, tmp_path):
        """写盘失败以异常如实上报（调用方据以打 [!]），不静默当成已写入。"""
        _timing = load_script("_release/_timing.py")

        blocker = tmp_path / "logs"
        blocker.write_text("占位文件", encoding="utf-8")
        with pytest.raises(OSError):
            _timing.append_record(blocker / "release.jsonl", {"command": "gate"})

    def test_unwritable_log_does_not_break_release(self, rel, tmp_path, monkeypatch, capsys):
        """台账写不进去（父路径被文件占位）只打 [!]，不得抛异常改写发布退出码。"""
        blocker = tmp_path / "logs"
        blocker.write_text("占位文件", encoding="utf-8")
        monkeypatch.setattr(rel, "RELEASE_LOG_FILE", blocker / "release.jsonl")
        rel._reset_timer()
        rel._finish_timing("gate", 0)  # 不抛即通过
        assert "耗时记录未写入" in capsys.readouterr().out
