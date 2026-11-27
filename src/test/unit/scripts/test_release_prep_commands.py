"""测试：发布准备阶段命令（`_release/_commands_prep.py`）命令层分支。

与 `test_release_tool.py` 共用 `_release_fixtures` 设备，本文件只补命令层未覆盖面：
  - `check`：本地门禁两项前置（统计快照 / dev-verify）的通过与拦截、`--no-local-gate`
    跳过、changelog 发布段派生预演失败前的提前中止
  - `archive-init`：骨架新建（动作逐条打印）、幂等无改动、`--dry` 零写入、版本形态拒绝、
    初始化异常降级、收尾统计同步失败透传退出码
  - `prepare`：版本一致性 `--fix` 与统计同步 `--sync` 失败的退出码与提示、异常路径回滚、
    回滚本身的失败与残留未跟踪文件提示

全部子进程经 `FakeRunner` 替身应答，不执行真实 git/脚本；写入一律落在 `tmp_path`。
"""

from __future__ import annotations

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
    return load_script("release.py", module_name="release_tool_prep_commands")


@pytest.fixture(autouse=True)
def _isolate_release_runtime_paths(rel, monkeypatch, tmp_path):
    """发布运行态文件（通过戳 / bench 戳 / 耗时台账）不写仓库真实路径。"""
    isolate_release_runtime_paths(rel, monkeypatch, tmp_path)


_PLAN_WITH_ARCHIVE_INDEX = (
    "# 计划\n\n"
    "## plan-77 在办任务\n\n- [ ] 待做\n\n"
    "## 归档\n\n"
    "- [`archived_plan.0.12.x.md`](../archive/v0.12.x/archived_plan.0.12.x.md)"
    " — v0.12.1 ~ v0.12.5（2026-10-03 ~ 2026-10-07）\n"
)


def _plan_with_archive_index(fx) -> None:
    """夹具的 plan.md 是最小节（无归档索引列表），archive-init 需按既有索引行定位插入点。"""
    fx.PLAN_FILE.write_text(_PLAN_WITH_ARCHIVE_INDEX, encoding="utf-8")


def _patch_local_gate(monkeypatch, *, snapshot=(True, ""), tests=(True, "")):
    """替换本地门禁两项前置探针，返回记录调用顺序的列表（不真跑 30s 门禁）。"""
    import scripts._release._local_gate as local_gate

    order: list[str] = []

    def _snapshot(_root):
        order.append("snapshot")
        return snapshot

    def _tests(_root):
        order.append("tests")
        return tests

    monkeypatch.setattr(local_gate, "check_doc_snapshot", _snapshot)
    monkeypatch.setattr(local_gate, "check_local_tests", _tests)
    return order


class TestCheckCommandGates:
    """`check` 的本地门禁前置：过去「进 gate 才发现」的返工源前移到秒级阶段。"""

    def test_all_gates_pass_reports_ready(self, rel, tmp_path, capsys, monkeypatch):
        _ToolRepoFixture(rel, tmp_path)
        order = _patch_local_gate(monkeypatch)
        assert rel.cmd_check(ns(), runner=_ok_runner()) == 0
        out = capsys.readouterr().out
        assert "prepare 文档派生预演通过" in out
        assert "统计快照与实测一致" in out and "dev-verify 全绿" in out
        assert "预检通过 — 可执行 prepare" in out
        # 快照同步先于 dev-verify（便宜的先跑，失败即不必等 30s 门禁）
        assert order == ["snapshot", "tests"]

    def test_stale_doc_snapshot_blocks_before_tests(self, rel, tmp_path, capsys, monkeypatch):
        _ToolRepoFixture(rel, tmp_path)
        order = _patch_local_gate(monkeypatch, snapshot=(False, "folders.md 统计过期"))
        assert rel.cmd_check(ns(), runner=_ok_runner()) == 2
        out = capsys.readouterr().out
        assert "folders.md 统计过期" in out
        assert order == ["snapshot"], "快照未过时不得再跑 dev-verify"

    def test_local_verify_failure_blocks(self, rel, tmp_path, capsys, monkeypatch):
        _ToolRepoFixture(rel, tmp_path)
        _patch_local_gate(monkeypatch, tests=(False, "test_a / test_b 失败"))
        assert rel.cmd_check(ns(), runner=_ok_runner()) == 2
        assert "test_a / test_b 失败" in capsys.readouterr().out

    def test_no_local_gate_flag_skips_both_probes(self, rel, tmp_path, capsys, monkeypatch):
        _ToolRepoFixture(rel, tmp_path)
        import scripts._release._local_gate as local_gate

        def _boom(_root):  # 跳过时探针一次都不该被调用
            raise AssertionError("--no-local-gate 下不得执行本地门禁探针")

        monkeypatch.setattr(local_gate, "check_doc_snapshot", _boom)
        monkeypatch.setattr(local_gate, "check_local_tests", _boom)
        assert rel.cmd_check(ns(no_local_gate=True), runner=_ok_runner()) == 0
        assert "本地门禁前置已跳过" in capsys.readouterr().out

    def test_changelog_derivation_failure_aborts_before_writes(self, rel, tmp_path, capsys, monkeypatch):
        """派生预演失败 → 在归档骨架/台账手术之前中止（不必先动文件再回滚）。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        _patch_local_gate(monkeypatch)
        # 去掉开发段头：prepare 会在写入前因「发布段无处可迁」中止，check 把它前移
        fx.CHANGELOG_FILE.write_text(
            "# 变更日志\n\n## 归档\n\n- [`x.md`](../archive/v0.12.x/x.md) — v0.12.1（2026-10-03）\n",
            encoding="utf-8",
        )
        original = fx.CHANGELOG_FILE.read_text(encoding="utf-8")
        assert rel.cmd_check(ns(), runner=_ok_runner()) == 2
        out = capsys.readouterr().out
        assert "派生预演失败" in out and "先修 changelog" in out
        assert fx.CHANGELOG_FILE.read_text(encoding="utf-8") == original, "check 只算不写"


class TestArchiveInitCommand:
    """`archive-init`：新小版本首发的一次建齐（幂等，`--dry` 零写入）。"""

    def test_new_minor_creates_archive_skeleton(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        _plan_with_archive_index(fx)
        runner = _ok_runner()
        assert rel.cmd_archive_init(ns(version="0.13.0", date="2026-10-20", dry=False), runner=runner) == 0
        out = capsys.readouterr().out
        archive_dir = fx.root / "docs" / "archive" / "v0.13.x"
        assert (archive_dir / "archived_changelog.0.13.x.md").is_file()
        assert (archive_dir / "archived_review-findings.0.13.x.md").is_file()
        assert (archive_dir / "archived_plan.0.13.x.md").is_file()
        assert "新建归档文件" in out and "归档骨架就绪" in out
        # 三处索引行各自补齐（台账 / 计划 / changelog）
        assert "archived_plan.0.13.x.md" in fx.PLAN_FILE.read_text(encoding="utf-8")
        assert "archived_changelog.0.13.x.md" in fx.CHANGELOG_FILE.read_text(encoding="utf-8")
        assert "archived_review-findings.0.13.x.md" in fx.RF_FILE.read_text(encoding="utf-8")
        # 收尾必须同步统计快照（目录树新增了归档子树，行数口径随之变化）
        assert any(any("check-doc-drift.py" in part for part in call) and "--sync" in call for call in runner.calls)

    def test_second_run_is_idempotent(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        _plan_with_archive_index(fx)
        args = ns(version="0.13.0", date="2026-10-20", dry=False)
        assert rel.cmd_archive_init(args, runner=_ok_runner()) == 0
        capsys.readouterr()
        first = {p.name: p.read_text(encoding="utf-8") for p in (fx.root / "docs" / "archive" / "v0.13.x").iterdir()}
        assert rel.cmd_archive_init(args, runner=_ok_runner()) == 0
        out = capsys.readouterr().out
        assert "无需改动（骨架已就绪，幂等）" in out
        second = {p.name: p.read_text(encoding="utf-8") for p in (fx.root / "docs" / "archive" / "v0.13.x").iterdir()}
        assert second == first

    def test_dry_run_writes_nothing(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        _plan_with_archive_index(fx)
        runner = _ok_runner()
        assert rel.cmd_archive_init(ns(version="0.13.0", date="2026-10-20", dry=True), runner=runner) == 0
        out = capsys.readouterr().out
        assert "试运行" in out and "新建归档文件" in out
        assert not (fx.root / "docs" / "archive" / "v0.13.x").exists()
        # 试运行不落盘也就无需统计同步
        assert not any("check-doc-drift.py" in part for call in runner.calls for part in call)

    def test_release_shaped_version_rejected_when_malformed(self, rel, tmp_path, capsys):
        _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner()
        assert rel.cmd_archive_init(ns(version="0.13", date=None, dry=False), runner=runner) == 2
        assert "不是 X.Y.Z 发布版形态" in capsys.readouterr().out
        assert runner.calls == [], "版本形态不过时不得执行任何子进程"

    def test_missing_index_anchor_degrades_to_exit_two(self, rel, tmp_path, capsys):
        """plan.md 无归档索引列表 → 定位不到插入点，人工确认格式（不猜写法）。"""
        _ToolRepoFixture(rel, tmp_path)  # 夹具 plan.md 即无索引行
        assert rel.cmd_archive_init(ns(version="0.13.0", date="2026-10-20", dry=False), runner=_ok_runner()) == 2
        assert "归档索引行" in capsys.readouterr().out

    def test_init_error_degrades_to_exit_two(self, rel, tmp_path, capsys, monkeypatch):
        from _release._common import ReleaseError

        _ToolRepoFixture(rel, tmp_path)

        def _raise(*_args, **_kwargs):
            raise ReleaseError("归档目录不可写")

        monkeypatch.setattr(rel._cmd_prep, "init_archive", _raise)
        assert rel.cmd_archive_init(ns(version="0.13.0", date="2026-10-20", dry=False), runner=_ok_runner()) == 2
        assert "归档目录不可写" in capsys.readouterr().out

    def test_sync_failure_propagates_exit_code(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        _plan_with_archive_index(fx)
        runner = FakeRunner(responses=[(["scripts/check-doc-drift.py"], (2, "", "统计表数字不一致\n"))])
        assert rel.cmd_archive_init(ns(version="0.13.0", date="2026-10-20", dry=False), runner=runner) == 2
        out = capsys.readouterr().out
        assert "统计表数字不一致" in out
        assert "文档统计同步未通过" in out


class TestPrepareFailurePaths:
    """`prepare` 写入链路的两处外部脚本失败必须中止并透传退出码。"""

    def test_version_consistency_fix_failure_stops_prepare(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner()
        # 预检阶段的一致性检查通过，prepare 内的 `--fix` 收敛失败 → 命中 --fix 分支
        runner.responses.insert(0, (["scripts/check-version-consistency.py", "--fix"], (3, "", "16 处版本头未收敛\n")))
        assert rel.cmd_prepare(ns(version=None, date="2026-10-08"), runner=runner) == 3
        out = capsys.readouterr().out
        assert "16 处版本头未收敛" in out
        assert "版本一致性 --fix 未收敛" in out
        # 不一致即止步：不继续跑统计同步与归档迁移
        assert not any("check-doc-drift.py" in part for call in runner.calls for part in call)
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.6"

    def test_doc_snapshot_sync_failure_stops_prepare(self, rel, tmp_path, capsys):
        _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner([(["scripts/check-doc-drift.py"], (2, "", "folders.md 行数不一致\n"))])
        assert rel.cmd_prepare(ns(version=None, date="2026-10-08"), runner=runner) == 2
        out = capsys.readouterr().out
        assert "folders.md 行数不一致" in out
        assert "文档统计快照同步失败" in out
        assert not any("mv" in call for call in runner.calls), "同步失败不得继续设计文件迁档"

    def test_exception_rolls_back_when_worktree_was_clean(self, rel, tmp_path, monkeypatch):
        """实现抛异常 → 干净起点自动回滚后把异常继续抛出（不吞成退出码）。"""
        _ToolRepoFixture(rel, tmp_path)
        runner = _ok_runner()
        original_run = runner.run
        state = {"dirty": False}

        def _run(cmd, root, capture=True):
            if cmd[:3] == ["git", "status", "--porcelain"]:
                return (0, " M docs/x.md\n" if state["dirty"] else "", "")
            return original_run(cmd, root, capture)

        runner.run = _run

        def _explode(*_args, **_kwargs):
            state["dirty"] = True
            raise RuntimeError("写盘后崩溃")

        monkeypatch.setattr(rel._cmd_prep, "_prepare_impl", _explode)
        with pytest.raises(RuntimeError, match="写盘后崩溃"):
            rel.cmd_prepare(ns(version=None, date="2026-10-08"), runner=runner)
        assert any(call[:3] == ["git", "reset", "--hard"] for call in runner.calls)

    def test_no_rollback_when_start_was_dirty(self, rel, tmp_path, monkeypatch):
        """起点已脏则无法区分自动改动与用户改动，保守不回滚。"""
        _ToolRepoFixture(rel, tmp_path)
        runner = FakeRunner(
            responses=[(["git", "status", "--porcelain"], (0, " M docs/user.md\n", ""))],
        )
        monkeypatch.setattr(rel._cmd_prep, "_prepare_impl", lambda *_a, **_k: 2)
        assert rel.cmd_prepare(ns(version=None, date="2026-10-08"), runner=runner) == 2
        assert not any(call[:3] == ["git", "reset", "--hard"] for call in runner.calls)


class TestRollbackReporting:
    """`_rollback_prepare` 的两条告警分支（回滚失败 / 回滚后仍有残留）。"""

    def test_reset_failure_reports_manual_action(self, rel, tmp_path, capsys):
        _ToolRepoFixture(rel, tmp_path)
        runner = FakeRunner(responses=[(["git", "reset", "--hard"], (128, "", "fatal: 无 HEAD\n"))])
        rel._cmd_prep._rollback_prepare(rel._env(), runner)
        out = capsys.readouterr().out
        assert "自动回滚未完成" in out and "fatal: 无 HEAD" in out
        assert "手动检查 git status" in out
        # 回滚失败后不再继续探测残留状态
        assert not any(call[:3] == ["git", "status", "--porcelain"] for call in runner.calls)

    def test_untracked_after_reset_reported_not_deleted(self, rel, tmp_path, capsys):
        _ToolRepoFixture(rel, tmp_path)
        runner = FakeRunner(
            responses=[
                (["git", "reset", "--hard"], (0, "", "")),
                (["git", "status", "--porcelain"], (0, "?? docs/tmp/report.html\n", "")),
            ]
        )
        rel._cmd_prep._rollback_prepare(rel._env(), runner)
        out = capsys.readouterr().out
        assert "工作树已回滚到 prepare 前" in out
        assert "?? docs/tmp/report.html" in out
        assert "未自动删除" in out
