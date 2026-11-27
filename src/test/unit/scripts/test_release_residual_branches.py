"""测试：发布链残余分支 — 失败打印 / 降级 / 备用返回口径

补 `_gate` / `_commands_base` / `_archive_flow` 三处**失败与降级分支**的覆盖面
（正常路径已由 `test_release_tool*.py` / `test_release_archive.py` 覆盖）：

  - `_gate.run_gate`：归档前置 unfiled 拦截、场景回归失败、守护 finding（stderr）、
    设计护栏 finding（stderr）、`--with-portability` 的通过与失败
  - `_commands_base`：耗时记录里 APP_VERSION / token 统计两处降级、版本形态校验抛错、
    预检版本读取失败、git 查询失败按「非纯文档」兜底、戳缺失的备用返回
  - `_archive_flow`：引用改写落盘、归档文件缺件中止、docs/plan 无候选/无编号打印、
    台账已迁档与 plan 无完成节的跳过

全部子进程经 `FakeRunner` 替身应答，不执行真实 git/脚本；写入一律落在 `tmp_path`。
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

from src.test._script_loader import load_script
from src.test.unit.scripts._release_fixtures import (
    FakeRunner,
    _ok_runner,
    _ToolRepoFixture,
    isolate_release_runtime_paths,
    ns,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def rel():
    return load_script("release.py", module_name="release_residual_branches")


@pytest.fixture(autouse=True)
def _isolate_release_runtime_paths(rel, monkeypatch, tmp_path):
    """发布运行态文件（通过戳 / bench 戳 / 耗时台账）不重定向会污染仓库真实文件。"""
    isolate_release_runtime_paths(rel, monkeypatch, tmp_path)


# ─────────────────────────── gate 失败分支 ───────────────────────────


@pytest.fixture
def gate_stubbed(rel, monkeypatch, tmp_path):
    """把 gate 前置断言全部收敛为「通过」，只留待测的失败分支。"""
    rf = tmp_path / "review-findings.md"
    rf.write_text("## 已解决问题\n", encoding="utf-8")
    folders = tmp_path / "folders.md"
    folders.write_text("", encoding="utf-8")
    constants = tmp_path / "constants.py"
    constants.write_text('APP_VERSION = "0.13.12"\n', encoding="utf-8")
    changelog_archive = tmp_path / "archived_changelog.0.13.x.md"
    changelog_archive.write_text("## [0.13.12]\n\n- 条目\n", encoding="utf-8")
    monkeypatch.setattr(rel, "check_evolution_freshness", lambda *_a, **_k: [])
    monkeypatch.setattr(rel, "read_app_version", lambda _t: "0.13.12")
    monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("absent", 0))
    monkeypatch.setattr(rel, "has_archive_section", lambda *_a, **_k: True)
    monkeypatch.setattr(rel, "ledger_archive_paths", lambda _v: (tmp_path / "a.md", tmp_path / "b.md"))
    monkeypatch.setattr(rel, "archive_paths_for", lambda _v: (changelog_archive, changelog_archive.name))
    monkeypatch.setattr(rel, "release_section_has_entries", lambda *_a, **_k: True)
    monkeypatch.setattr(rel, "FOLDERS_FILE", folders)
    monkeypatch.setattr(rel, "CONSTANTS_FILE", constants)
    monkeypatch.setattr(rel, "RF_FILE", rf)
    return tmp_path


class TestGateFailureOutputs:
    """gate 各失败分支的终端说法与退出码（发布日志的第一现场）。"""

    def test_unfiled_rf_rows_block_gate(self, rel, gate_stubbed, monkeypatch, capsys):
        """「已解决」区台账行漏写版本节头 → 拦截并指明 archive 修法。"""
        monkeypatch.setattr(rel, "rf_archive_status", lambda *_a, **_k: ("unfiled", 4))
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 2
        out = capsys.readouterr().out
        assert "4 条台账行漏写版本节头" in out
        assert "整批漏搬" in out
        assert runner.calls == []  # 前置拦截：verify/回归一个不跑

    def test_scenario_regression_failure_prints_stderr(self, rel, gate_stubbed, capsys):
        """verify 通过、场景回归失败 → 打印 stderr 并以回归退出码中止。"""
        responses = [
            (["scripts/test-runner.py", "verify"], (0, "", "")),
            (["scripts/test-runner.py", "regression"], (1, "", "1 scenario failed")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 1
        out = capsys.readouterr().out
        assert "1 scenario failed" in out
        assert "场景回归未通过，P2 中止" in out

    def test_guard_finding_prints_stderr(self, rel, gate_stubbed, capsys):
        """守护清单某台以 stderr 报 finding → 打印 stderr 与脚本名，退出码传递。"""
        responses = [
            (["scripts/test-runner.py"], (0, "", "")),
            (["scripts/check-doc-links.py"], (2, "", "死锚点 x.md#bay")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 2
        out = capsys.readouterr().out
        assert "check-doc-links.py（退出码 2）" in out
        assert "死锚点 x.md#bay" in out
        assert "P2 守护存在 finding" in out

    def test_style_guardrail_finding_prints_stderr(self, rel, gate_stubbed, capsys):
        """设计护栏以 stderr 报 E 级 finding → 打印 stderr 后中止。"""
        responses = [
            (["scripts/test-runner.py"], (0, "", "")),
            (["scripts/check-style-guardrails.py"], (2, "", "E 级：强调色越权")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 2
        out = capsys.readouterr().out
        assert "E 级：强调色越权" in out
        assert "设计护栏未通过，P2 中止" in out

    def test_portability_probe_pass_prints_output_and_suffix(self, rel, gate_stubbed, capsys):
        """`--with-portability` 通过 → 打印探针输出，全绿文案带 portability 后缀。"""
        responses = [(["--mode", "portability"], (0, "portability 探针 3 项通过", ""))]
        rc = rel.cmd_gate(ns(with_portability=True), runner=FakeRunner(responses=responses))
        assert rc == 0
        out = capsys.readouterr().out
        assert "portability 探针 3 项通过" in out
        assert "portability" in out.split("P2 门禁全绿", 1)[1]

    def test_portability_probe_failure_aborts(self, rel, gate_stubbed, capsys):
        """`--with-portability` 失败 → 打印输出与 stderr 后以探针退出码中止。"""
        responses = [(["--mode", "portability"], (2, "locale 探针输出", "cp936 解码失败"))]
        rc = rel.cmd_gate(ns(with_portability=True), runner=FakeRunner(responses=responses))
        assert rc == 2
        out = capsys.readouterr().out
        assert "locale 探针输出" in out
        assert "cp936 解码失败" in out
        assert "portability 探针未通过，P2 中止" in out


# ─────────────────────── _commands_base 降级与备用返回 ───────────────────────


class TestCommandBaseDegrades:
    def test_finish_timing_survives_unreadable_constants(self, rel, tmp_path, capsys, monkeypatch):
        """APP_VERSION 读不到 → 版本号留空照写台账，不打断发布收尾。"""
        _ToolRepoFixture(rel, tmp_path)
        monkeypatch.setattr(rel, "CONSTANTS_FILE", tmp_path / "no-such-constants.py")
        rel._finish_timing("gate", 0)
        log = rel.RELEASE_LOG_FILE
        assert log.is_file()
        assert '"version": ""' in log.read_text(encoding="utf-8")
        assert "耗时已记录到" in capsys.readouterr().out

    def test_finish_timing_token_read_failure_is_hinted(self, rel, tmp_path, capsys, monkeypatch):
        """token 统计读取抛错 → 提示不影响结果（观测面不阻断发布）。"""
        _ToolRepoFixture(rel, tmp_path)
        base = getattr(rel, "_cmd_base")

        def _boom(_path):
            raise TypeError("行不是对象")

        monkeypatch.setattr(base, "_read_ledger_records", _boom)
        rel._finish_timing("gate", 0)
        assert "token 统计读取失败（不影响本次结果）" in capsys.readouterr().out

    def test_archive_paths_reject_non_release_version(self, rel):
        """非 X.Y.Z 发布形态无法推导归档名 → 抛 ReleaseError（而非拼出畸形路径）。"""
        for func in (rel.archive_paths_for, rel.ledger_archive_paths):
            with pytest.raises(rel.ReleaseError):
                func("0.13")

    def test_preflight_reports_unreadable_version(self, rel, tmp_path):
        """constants.py 读不到 → 预检「版本形态」项失败而非抛出。"""
        root = tmp_path / "repo"
        (root / "src" / "python" / "core").mkdir(parents=True)
        results = rel.run_preflight(root, expect_release=False, runner=_ok_runner())
        version_rows = [row for row in results if row[0] == "版本形态"]
        assert len(version_rows) == 1
        assert version_rows[0][1] is False
        assert "读取 APP_VERSION 失败" in version_rows[0][2]

    def test_docs_only_changes_git_failure_is_conservative(self, rel):
        """`git diff` 失败 → 按「有程序变更」返回（保守，必跑刷新）。"""
        base = getattr(rel, "_cmd_base")
        env = type("_Env", (), {"REPO_ROOT": rel.REPO_ROOT})()
        runner = FakeRunner(responses=[(["git", "diff", "--name-only"], (1, "", "fatal: bad revision"))])
        assert base._docs_only_changes_since("v0.13.0", env, runner) == (False, [])

    def test_changed_code_files_without_stamp_is_empty(self, rel):
        """没有 gate 戳 → 无「gate 之后改动的代码文件」可点名。"""
        base = getattr(rel, "_cmd_base")
        assert base._changed_code_files(None, None) == []

    def test_bench_covers_verify_without_stamp(self, rel, tmp_path):
        """无 bench 戳 → 不可替代 P1 verify（回落实跑，不盲信）。"""
        _ToolRepoFixture(rel, tmp_path)
        assert rel._bench_covers_verify(_ok_runner()) is None


# ─────────────────────────── 归档流程残余分支 ───────────────────────────


_ALREADY_ARCHIVED_RF = (
    "# 自审记录\n\n## 已解决问题\n\n### 归档档案\n\n"
    "- [`archived_review-findings.0.12.x.md`](../archive/v0.12.x/archived_review-findings.0.12.x.md)"
    " — v0.12.x 开发期已修复批次（2026-09-01 ~ 2026-10-05）\n"
)

_OPEN_ONLY_PLAN = (
    "# 计划\n\n"
    "## plan-77 在办任务\n\n- [ ] 待做\n\n"
    "## 归档\n\n"
    "- [`archived_plan.0.12.x.md`](../archive/v0.12.x/archived_plan.0.12.x.md)"
    " — v0.12.1 ~ v0.12.5（2026-10-03 ~ 2026-10-07）\n"
)


class TestArchiveFlowResiduals:
    def test_rewrite_refs_writes_new_path(self, tmp_path):
        """引用改写命中即落盘并返回改写次数。"""
        target = tmp_path / "changelog.md"
        target.write_text("见 [`design.md`](../plan/done/design.md) 与 docs/plan/done/design.md。\n", encoding="utf-8")
        from scripts._release._archive_flow import _rewrite_refs_in

        count = _rewrite_refs_in(target, ("docs/plan/done/design.md",), "docs/archive/v0.13.x/design/design.md")
        assert count == 1
        assert "docs/plan/done/design.md" not in target.read_text(encoding="utf-8")
        assert "docs/archive/v0.13.x/design/design.md" in target.read_text(encoding="utf-8")

    def test_missing_archive_file_aborts(self, rel, tmp_path, capsys):
        """归档文件缺件 → 中止并点名缺失路径（新小版本须先手工建归档）。"""
        fixture = _ToolRepoFixture(rel, tmp_path)
        fixture.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        plan_archive = tmp_path / "docs" / "archive" / "v0.12.x" / "archived_plan.0.12.x.md"
        plan_archive.unlink()
        assert rel.cmd_archive(ns(date="2026-10-08"), runner=_ok_runner()) == 2
        out = capsys.readouterr().out
        assert "归档文件不存在" in out
        assert plan_archive.name in out

    def test_nothing_to_migrate_reports_skips(self, rel, tmp_path, capsys):
        """台账已迁档 + plan 无完成节 + docs/plan 无可迁候选 → 逐条说明跳过。"""
        fixture = _ToolRepoFixture(rel, tmp_path)
        fixture.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        fixture.RF_FILE.write_text(_ALREADY_ARCHIVED_RF, encoding="utf-8")
        fixture.PLAN_FILE.write_text(_OPEN_ONLY_PLAN, encoding="utf-8")
        (fixture.PLAN_DOCS_DIR / "design-done.md").unlink()  # 去掉唯一的已归档候选
        (fixture.PLAN_DOCS_DIR / "design-plain.md").write_text("# 无编号设计\n\n正文。\n", encoding="utf-8")
        assert rel.cmd_archive(ns(date="2026-10-08", dry_run=True), runner=_ok_runner()) == 0
        out = capsys.readouterr().out
        assert "无引用编号已全部归档的设计文件" in out
        assert "未引用任何任务编号" in out and "design-plain.md" in out
        assert "该版本已迁档（占位已在），跳过" in out
        assert "无已完成任务节，跳过" in out

    def test_doc_snapshot_sync_failure_aborts(self, rel, tmp_path, capsys):
        """收尾统计同步失败 → 透传退出码并指向上方输出。"""
        fixture = _ToolRepoFixture(rel, tmp_path)
        fixture.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["scripts/check-doc-drift.py"], (1, "统计快照过期", ""))])
        assert rel.cmd_archive(ns(date="2026-10-08"), runner=runner) == 1
        out = capsys.readouterr().out
        assert "统计快照过期" in out
        assert "文档统计快照同步失败" in out
        # 同步失败即停：后续两台便宜守护一个不跑
        assert not any(any("check-doc-traces.py" in p for p in c) for c in runner.calls)

    def test_trailing_guard_failure_aborts(self, rel, tmp_path, capsys):
        """收尾守护未通过 → 打印其输出并以该退出码中止。"""
        fixture = _ToolRepoFixture(rel, tmp_path)
        fixture.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["scripts/check-doc-traces.py"], (2, "痕迹：旧实现", ""))])
        assert rel.cmd_archive(ns(date="2026-10-08"), runner=runner) == 2
        out = capsys.readouterr().out
        assert "痕迹：旧实现" in out
        assert "check-doc-traces.py 未通过" in out


# ─────────────────────────── CLI 分派与本地门禁探针 ───────────────────────────


class TestCliDispatch:
    def test_run_cli_dispatches_then_finishes_timing(self, rel):
        """子命令分派后无论成败都写耗时台账（观测面覆盏失败命令）。"""
        calls: list = []
        rc = rel.run_cli(
            ["gate"],
            {"gate": lambda _args: 0},
            reset_timer=lambda: calls.append("reset"),
            finish_timing=lambda cmd, code: calls.append((cmd, code)),
            release_error=rel.ReleaseError,
        )
        assert rc == 0
        assert calls == ["reset", ("gate", 0)]

    def test_run_cli_maps_release_error_to_two(self, rel, capsys):
        """ReleaseError 是「可读原因」而非栈：打印原因后返回 2。"""
        recorded: list = []

        def _boom(_args):
            raise rel.ReleaseError("归档缺件")

        rc = rel.run_cli(
            ["archive"],
            {"archive": _boom},
            reset_timer=lambda: None,
            finish_timing=lambda cmd, code: recorded.append((cmd, code)),
            release_error=rel.ReleaseError,
        )
        assert rc == 2
        assert "归档缺件" in capsys.readouterr().out
        assert recorded == [("archive", 2)]


class TestLocalGateRunner:
    """本地门禁探针的子进程包装：只用 subprocess 替身，不起真实进程。"""

    def _module(self):
        from scripts._release import _local_gate

        return _local_gate

    def test_run_merges_stdout_stderr(self, monkeypatch, tmp_path):
        """探针只关心尾部输出：stdout+stderr 合并返回（不看部分成功）。"""
        module = self._module()

        class _Proc:
            returncode = 1
            stdout = "快照过期\n"
            stderr = "细节\n"

        monkeypatch.setattr(module.subprocess, "run", lambda *_a, **_k: _Proc())
        assert module._run(["scripts/check-doc-drift.py", "--ci"], tmp_path) == (1, "快照过期\n细节\n")

    def test_run_degrades_when_exec_fails(self, monkeypatch, tmp_path):
        """解释器/脚本起不来 → 按失败返回并带原因，不向上抛。"""
        module = self._module()

        def _raise(*_a, **_k):
            raise OSError("无法执行")

        monkeypatch.setattr(module.subprocess, "run", _raise)
        rc, out = module._run(["scripts/check-doc-drift.py", "--ci"], tmp_path)
        assert rc == 1
        assert "执行失败" in out and "无法执行" in out


# ─────────────── 形态拒绝 / 超时 / OSError 兜底 / 空窗口（纯函数与最佳努力分支） ───────────────


def _module(name: str):
    """取 `scripts/_release/` 子模块（`scripts.` 口径，与本文件既有用例一致）。"""
    return importlib.import_module(f"scripts._release.{name}")


@pytest.fixture(name="versioning")
def fixture_versioning():
    return _module("_versioning")


@pytest.fixture(name="common")
def fixture_common():
    return _module("_common")


@pytest.fixture(name="hygiene")
def fixture_hygiene():
    return _module("_hygiene")


@pytest.fixture(name="archive_init")
def fixture_archive_init():
    return _module("_archive_init")


@pytest.fixture(name="timing")
def fixture_timing():
    return _module("_timing")


class TestVersioningRejectsMissingAnchorLines:
    """样式行（APP_VERSION / README 版本指针）缺失时必须报错，而不是静默返回原文。"""

    def test_render_app_version_without_app_version_line(self, versioning):
        with pytest.raises(versioning.ReleaseError, match="APP_VERSION"):
            versioning.render_app_version("# 无版本行\n", "0.12.7")

    def test_render_readme_version_without_version_pointer(self, versioning):
        with pytest.raises(versioning.ReleaseError, match="当前版本"):
            versioning.render_readme_version("# README\n\n无版本指针。\n", "0.12.7")

    def test_archive_name_for_rejects_dev_version(self, versioning):
        """归档名按发布版号派生；开发版号传进来必须拒绝（否则生成怪名归档文件）。"""
        with pytest.raises(versioning.ReleaseError, match="不是 X.Y.Z 发布版形态"):
            versioning.archive_name_for("0.12.7-dev")


class TestChangelogArchiveSectionGuard:
    def test_dev_section_without_archive_block_is_rejected(self, rel):
        """开发段之后必须有 `## 归档` 索引块，否则迁出后无处落索引行。"""
        text = "# 变更日志\n\n## [0.12.6-dev] - 开发中（未发布）\n\n- 条目一\n"
        with pytest.raises(rel.ReleaseError, match="开发段之后没有归档章节"):
            rel.apply_changelog_release(text, "0.12.6", "2026-10-08")


class TestExecCommandTimeout:
    def test_timeout_raises_release_error(self, common, monkeypatch, tmp_path):
        """无 runner 时的真实子进程分支：超时不得挂死，转成带命令行的 ReleaseError。"""

        def _timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd="git push", timeout=5)

        monkeypatch.setattr(common.subprocess, "run", _timeout)
        with pytest.raises(common.ReleaseError, match="命令超时（5s）：git push"):
            common.exec_command(["git", "push"], tmp_path, timeout=5)


class TestCleanStaleBytecodeOsErrors:
    """删除动作的 OSError 只影响该项统计，不中断清理（最佳努力语义）。"""

    def test_unlink_failure_skips_file(self, hygiene, tmp_path, monkeypatch):
        cache = tmp_path / "gone" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "gone.cpython-313.pyc").write_bytes(b"pyc")

        def _denied(_self):
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "unlink", _denied)
        assert hygiene.clean_stale_bytecode(tmp_path) == {"files": 0, "dirs": 0}

    def test_rmtree_failure_keeps_dir_out_of_count(self, hygiene, tmp_path, monkeypatch):
        cache = tmp_path / "gone" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "gone.cpython-313.pyc").write_bytes(b"pyc")

        def _busy(*_args, **_kwargs):
            raise OSError("device busy")

        monkeypatch.setattr(hygiene.shutil, "rmtree", _busy)
        assert hygiene.clean_stale_bytecode(tmp_path) == {"files": 1, "dirs": 0}
        assert cache.is_dir()  # 目录删不掉时保留，不计入目录数

    def test_non_empty_parent_dir_rmdir_failure_is_tolerated(self, hygiene, tmp_path):
        """源目录还有别的文件时 `rmdir` 失败属预期，计入目录数但不抛错。"""
        pkg = tmp_path / "gone"
        cache = pkg / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "gone.cpython-313.pyc").write_bytes(b"pyc")
        (pkg / "keep.txt").write_text("keep\n", encoding="utf-8")

        assert hygiene.clean_stale_bytecode(tmp_path) == {"files": 1, "dirs": 1}
        assert pkg.is_dir()
        assert not cache.exists()


class TestArchiveInitTreeGuards:
    def test_insert_tree_block_without_archive_subtree(self, archive_init):
        with pytest.raises(archive_init.ReleaseError, match="未找到任何 `vX.Y.x/` 归档子树"):
            archive_init.insert_tree_block("# 目录树\n\n├── docs/\n└── src/\n", "0.13")

    def test_insert_tree_block_rejects_older_minor(self, archive_init):
        """脚本只追加到末尾，新归档早于末位版本时必须人工插入而非静默错位。"""
        text = "# 目录树\n\n│   └── archive/\n│       ├── v0.11.x/            # 归档\n│       └── v0.12.x/            # 归档\n"
        with pytest.raises(archive_init.ReleaseError, match="早于目录树中最后一个版本 v0.12.x"):
            archive_init.insert_tree_block(text, "0.10")

    def test_init_archive_rejects_non_release_version(self, rel):
        """`0.13`（缺补丁位）在建任何文件前就被拦下。"""
        with pytest.raises(rel.ReleaseError, match="不是 X.Y.Z 发布版形态"):
            rel.init_archive(rel._archive_ctx("0.13.0"), "0.13", "2026-10-20")


class TestBuildEvolutionStatsFailures:
    def test_git_ls_files_failure_propagates(self, rel, tmp_path):
        runner = FakeRunner(responses=[(["git", "ls-files"], (128, "", "fatal: not a git repository"))])
        with pytest.raises(rel.ReleaseError, match="git ls-files 失败：fatal: not a git repository"):
            rel.build_evolution_stats(tmp_path, runner)


class TestReleaseTokenUsageWindows:
    def test_empty_window_after_devbump(self, timing):
        """最后一条是 devbump → 发布窗口未开始，用量为空（而不是负数）。"""
        assert timing.release_token_usage([{"command": "devbump", "session_usage": {"total": 5}}]) == {}

    def test_records_without_usage_are_skipped(self, timing):
        usage = timing.release_token_usage(
            [
                {"command": "devbump"},
                {"command": "gate"},
                {"command": "publish", "session_usage": {"input": 60, "output": 40, "total": 100}},
            ]
        )
        assert usage["total"] == 100
        assert usage["input"] == 60

    def test_unrecorded_step_has_no_seconds(self, timing):
        timer = timing.StepTimer()
        timer.mark_elapsed("已有的步骤", 0.0)
        assert timer.step_seconds("别的步骤") is None
