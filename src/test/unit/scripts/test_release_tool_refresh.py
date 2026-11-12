"""测试：refresh 条件化与归档骨架命令 — release.py 第五部分

覆盖（设备见同目录 `_release_fixtures.py`）：
  - refresh：三步顺序执行、首步失败即停、bench 模式范围、纯文档变更跳过
  - archive-init：三份归档 + 目录树块 + 三处索引行一次建齐且幂等
  - prepare：`--version` 与开发链推导值不一致时中止并给可执行指引

共享设备见同目录 `_release_fixtures.py`（子进程替身 / 临时仓库夹具 / 台账样例）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.test._script_loader import load_script
from src.test.unit.scripts._release_fixtures import (
    FakeRunner,
    _mode_arg,
    _ok_runner,
    _ToolRepoFixture,
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
    return load_script("release.py", module_name="release_tool_refresh")


@pytest.fixture(autouse=True)
def _isolate_release_runtime_paths(rel, monkeypatch, tmp_path):
    """发布运行态文件（通过戳/bench 戳/耗时台账）一律重定向到 tmp。

    回归背景：`TestGateArchivePrecondition` 曾未隔离 `GATE_STAMP_FILE`——gate 成功
    用例走完尾部写入，把仓库真实的 `logs/release-gate-stamp.json` 写成夹具版本号
    （发布时间戳也被改写），使「门禁通过戳」不可信；且每次跑单测都会再污染一次。
    """
    isolate_release_runtime_paths(rel, monkeypatch, tmp_path)


# ─────────────────────────── refresh / evolution 命令 ───────────────────────────


class TestRefresh:
    """refresh 条件化：自上一 release tag 起仅文档变更 → 跳过 bench/collect
    （doc-drift --sync 恒跑）；有程序/测试变更或 --force-refresh → 三步全跑。"""

    @staticmethod
    def _steps(runner, skip: int = 0) -> list[list[str]]:
        """去掉「代码指纹」的 git 探测。

        指纹口径是**内容哈希**（`git ls-files --cached --others --exclude-standard -z`），
        与提交状态无关；refresh 自身的变更检测仍走 `git diff --name-only` /
        `git ls-files`（用于「有无未跟踪程序文件」）。
        """

        def _is_fingerprint(cmd: list[str]) -> bool:
            return cmd[:2] == ["git", "ls-files"] and "-z" in cmd

        return [c for c in runner.calls if not _is_fingerprint(c)][skip:]

    _TAG = (["describe"], (0, "v0.13.9", ""))
    _PROGRAM_CHANGE = (["diff", "--name-only"], (0, "src/python/x.py\n", ""))
    _DOCS_ONLY = (["diff", "--name-only"], (0, "README.md\ndocs/plan/y.md\n", ""))

    def test_three_steps_in_order_when_program_changed(self, rel):
        runner = FakeRunner(responses=[self._TAG, self._PROGRAM_CHANGE])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = self._steps(runner, skip=3)  # 前 3 个调用：describe / diff / ls-files
        assert len(steps) == 3
        assert "--update-docs" in steps[0]
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)
        assert any("test-collect-coverage" in p for p in steps[1])
        assert any("check-doc-drift" in p for p in steps[2])

    def test_docs_only_skips_bench_and_collect(self, rel):
        runner = FakeRunner(responses=[self._TAG, self._DOCS_ONLY])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = self._steps(runner, skip=3)
        assert len(steps) == 1  # 仅 sync
        assert any("check-doc-drift" in p for p in steps[0])

    def test_force_refresh_runs_all_steps(self, rel):
        runner = FakeRunner()
        rc = rel.cmd_refresh(ns(force_refresh=True), runner=runner)
        assert rc == 0
        calls = self._steps(runner)  # 无 git 判定，直接三步（+ 代码指纹探测）
        assert len(calls) == 3
        assert "--update-docs" in calls[0]
        assert _mode_arg(calls[0]) == ",".join(rel.RELEASE_BENCH_MODES)
        assert any("test-collect-coverage" in p for p in calls[1])

    def test_missing_tag_conservatively_refreshes(self, rel):
        runner = FakeRunner(responses=[(["describe"], (128, "", "no tag here"))])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = self._steps(runner, skip=1)
        assert len(steps) == 3  # 无 tag → 保守全刷
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)

    def test_untracked_program_file_triggers_refresh(self, rel):
        """未跟踪程序文件（git diff 不含）也计入变更 → 必跑。"""
        runner = FakeRunner(
            responses=[
                self._TAG,
                (["diff", "--name-only"], (0, "README.md\n", "")),
                (["ls-files", "--others"], (0, "src/python/new_mod.py\n", "")),
            ]
        )
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = self._steps(runner, skip=3)
        assert len(steps) == 3
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)

    def test_full_bench_flag_runs_all_modes(self, rel):
        """`--full-bench` 走 bench 别名（全量 14 档）——重测全表耗时的手动入口。"""
        runner = FakeRunner()
        rc = rel.cmd_refresh(ns(force_refresh=True, full_bench=True), runner=runner)
        assert rc == 0
        assert _mode_arg(runner.calls[0]) == "bench"

    def test_bench_run_writes_stamp_for_gate_reuse(self, rel, tmp_path, monkeypatch):
        """bench 实跑且全绿 → 写 bench 戳（含 covers_unit 与代码指纹），供 gate 复用。"""
        stamp = tmp_path / "bench.json"
        monkeypatch.setattr(rel, "BENCH_STAMP_FILE", stamp)
        runner = FakeRunner(responses=[self._TAG, self._PROGRAM_CHANGE])
        assert rel.cmd_refresh(ns(), runner=runner) == 0
        data = json.loads(stamp.read_text(encoding="utf-8"))
        assert data["covers_unit"] is True
        assert set(data["modes"]) == set(rel.RELEASE_BENCH_MODES)
        assert data["code_fingerprint"]

    def test_docs_only_refresh_writes_no_bench_stamp(self, rel, tmp_path, monkeypatch):
        """纯文档 → bench 跳过 → 不得写戳（gate 必须实跑 verify）。"""
        stamp = tmp_path / "bench.json"
        monkeypatch.setattr(rel, "BENCH_STAMP_FILE", stamp)
        runner = FakeRunner(responses=[self._TAG, self._DOCS_ONLY])
        assert rel.cmd_refresh(ns(), runner=runner) == 0
        assert not stamp.exists()

    def test_release_bench_modes_are_real_modes(self, rel):
        """子集模式必须是 test-runner 的真实模式键：拼错会让 bench 直接报错退出，
        表不回填、发布链在 refresh 就断（结构与实现双向对齐）。"""
        runner_mod = load_script("test-runner.py", module_name="test_runner_bench_modes")
        assert set(rel.RELEASE_BENCH_MODES) <= set(runner_mod.MODES)
        assert "bench" not in rel.RELEASE_BENCH_MODES  # 别名不得混入子集

    def test_short_decisive_modes_run_before_bulk(self, rel):
        """场景/集成档先于 unit/dev-verify：fail-fast 只在「尚未启动」的档上生效，
        长尾档压后才能在场景失败时立刻中止，而不是白等完整 unit。"""
        modes = rel.RELEASE_BENCH_MODES
        assert modes.index("regression") < modes.index("unit")
        assert modes.index("integration") < modes.index("unit")
        assert modes.index("dev-verify") > modes.index("unit")

    def test_first_step_failure_stops_chain(self, rel):
        runner = FakeRunner(
            responses=[
                self._TAG,
                self._PROGRAM_CHANGE,
                (["scripts/test-runner.py"], (5, "", "x")),
            ]
        )
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 5
        assert len(runner.calls) == 4  # 3 git + 首步即止


class TestArchiveInit:
    """新小版本归档骨架一次建齐（三份归档 + 目录树块 + 三处索引行，幂等）。"""

    def _ctx(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        # 模拟「上一个 train 已归档」的初始态：去掉 0.12.x 之外的索引与树块，再清空 0.13 骨架
        fx.RF_FILE.write_text(
            "# 台账\n\n## 已解决问题\n\n### 归档档案\n"
            "- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md)"
            " — v0.12.x（2026-09-01 ~ 2026-10-05）\n",
            encoding="utf-8",
        )
        fx.PLAN_FILE.write_text(
            "# 计划\n\n## 归档档案\n"
            "- [`archived_plan.0.12.x.md`](../archive/v0.12.x/archived_plan.0.12.x.md) — v0.12.x（2026-09-01 ~ 2026-10-05）\n",
            encoding="utf-8",
        )
        fx.CHANGELOG_FILE.write_text(
            "# 变更日志\n\n> **最近发布 [0.12.5]**（2026-10-07）——已发布版本段随发布移入 "
            "[`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)；本文件只保留当前开发版本段与归档索引。\n\n"
            "## 归档\n\n- [`archived_changelog.0.12.x.md`](../archive/v0.12.x/archived_changelog.0.12.x.md)"
            " — v0.12.1 ~ v0.12.5（2026-10-03 ~ 2026-10-07）\n",
            encoding="utf-8",
        )
        fx.FOLDERS_FILE.write_text(
            "````\n└── docs/\n    └── archive/                         # 归档\n"
            "        └── v0.12.x/                     # v0.12.x 归档\n"
            "            └── archived_plan.0.12.x.md # 计划\n````\n",
            encoding="utf-8",
        )
        return fx

    def test_creates_files_tree_and_indexes(self, rel, tmp_path):
        fx = self._ctx(rel, tmp_path)
        actions = rel.init_archive(rel._archive_ctx("0.13.0"), "0.13.0", "2026-10-21")

        assert len(actions) >= 5  # 三份文件 + 目录树块 + 三处索引（允许合并计数）
        assert rel.archive_prerequisites("0.13.0") == []  # check 前置就绪
        for text in (fx.RF_FILE.read_text(encoding="utf-8"), fx.PLAN_FILE.read_text(encoding="utf-8")):
            assert "archived_" in text and "0.13.x.md" in text
        assert "v0.13.x/" in fx.FOLDERS_FILE.read_text(encoding="utf-8")
        rf_archive = fx.root / "docs" / "archive" / "v0.13.x" / "archived_review-findings.0.13.x.md"
        assert rel.archive_header_findings(rf_archive.read_text(encoding="utf-8")) == []

    def test_idempotent_second_run(self, rel, tmp_path):
        self._ctx(rel, tmp_path)
        rel.init_archive(rel._archive_ctx("0.13.0"), "0.13.0", "2026-10-21")
        assert rel.init_archive(rel._archive_ctx("0.13.0"), "0.13.0", "2026-10-21") == []


class TestPrepareVersionMismatchGuidance:
    """`prepare --version` 与开发链推导值不一致时须中止并给出可执行指引（不中途报错）。"""

    def test_mismatch_aborts_with_guidance(self, rel, tmp_path, capsys):
        _ToolRepoFixture(rel, tmp_path)
        rel.CONSTANTS_FILE.write_text('APP_VERSION = "0.13.13-dev"\n', encoding="utf-8")
        rc = rel.cmd_prepare(ns(version="0.14.0", date="2026-10-21", no_archive=True), runner=_ok_runner())
        out = capsys.readouterr().out
        assert rc == 2
        assert "推导的发布版 0.13.13" in out
        assert "check-version-consistency.py --fix" in out
        # 未写入任何文件（版本链保持开发态）
        assert rel.read_app_version(rel.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.13.13-dev"
