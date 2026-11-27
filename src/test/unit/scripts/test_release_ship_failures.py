"""发布收尾阶段命令（`_release/_commands_ship.py`）的失败与降级分支测试。

既有 `test_release_tool_publish.py`/`test_release_tool_gate.py` 覆盖 publish/devbump 的
正常序；本文件只补失败面：提交/切分支/合并/打 tag/推送各步失败后的退出码与提示、
发布闭环校验（tag / master / dev 三者）的逐项报错，以及 evolution 的派生失败与统计同步失败。

子进程全经 `FakeRunner` 应答，不执行真实 git 操作、不推送。
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
    return load_script("release.py", module_name="release_tool_ship_failures")


@pytest.fixture(autouse=True)
def _isolate_release_runtime_paths(rel, monkeypatch, tmp_path):
    isolate_release_runtime_paths(rel, monkeypatch, tmp_path)


@pytest.fixture(name="release_repo")
def _release_repo(rel, tmp_path):
    """发布形态仓库（publish/devbump 的前置是版本已切成 X.Y.Z）。"""
    fixture = _ToolRepoFixture(rel, tmp_path)
    fixture.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
    return fixture


def _publish_runner(**overrides) -> FakeRunner:
    """预检/同步/verify 全过；默认树脏（走 release 提交路径），按需覆写单条。"""
    pairs: list[tuple] = [
        (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
        (["scripts/test-runner.py"], (0, "— 8,621 通过, 0 失败\n", "")),
    ]
    for matcher, response in overrides.items():
        pairs = [pair for pair in pairs if pair[0] != list(matcher.split("|"))] + [((matcher.split("|")), response)]
    return _ok_runner(pairs)


class TestPublishFailureBranches:
    """publish 每一步失败都必须停在原处并给出可执行的下一步。"""

    def test_worktree_status_failure_returns_one(self, rel, release_repo):
        runner = FakeRunner(
            responses=[
                (["git", "branch", "--show-current"], (0, "dev\n", "")),
                (["git", "rev-parse"], (1, "", "")),
                (["scripts/check-version-consistency.py"], (0, "[OK]\n", "")),
                (["git", "status", "--porcelain"], (128, "", "fatal: 仓库损坏")),
            ],
            default=(0, "", ""),
        )
        assert rel.cmd_publish(ns(title="主题", push=False), runner=runner) == 1

    def test_commit_failure_reports_and_returns_code(self, rel, release_repo, capsys):
        runner = _publish_runner(**{"git|commit": (1, "", "pre-commit 钩子失败\n")})
        assert rel.cmd_publish(ns(title="主题", push=False), runner=runner) == 1
        assert "release 提交失败" in capsys.readouterr().out

    def test_checkout_master_failure_aborts(self, rel, release_repo, capsys):
        runner = _publish_runner(**{"git|checkout|master": (1, "", "有未提交改动\n")})
        assert rel.cmd_publish(ns(title="主题", push=False), runner=runner) == 1
        assert "切换 master 失败" in capsys.readouterr().out

    def test_merge_failure_restores_dev_branch(self, rel, release_repo, capsys):
        runner = _publish_runner(**{"git|merge": (1, "", "CONFLICT\n")})
        assert rel.cmd_publish(ns(title="主题", push=False), runner=runner) == 1
        assert "合并失败" in capsys.readouterr().out
        assert any(call[:3] == ["git", "checkout", "dev"] for call in runner.calls), "合并失败须切回 dev"

    def test_tag_failure_restores_dev_branch(self, rel, release_repo, capsys):
        runner = _publish_runner(**{"git|tag|v0.12.6": (1, "", "tag 已存在\n")})
        assert rel.cmd_publish(ns(title="主题", push=False), runner=runner) == 1
        assert "打 tag 失败" in capsys.readouterr().out
        assert any(call[:3] == ["git", "checkout", "dev"] for call in runner.calls)

    def test_push_failure_stops_remaining_pushes(self, rel, release_repo, capsys):
        runner = _publish_runner(**{"git|push|origin|master": (1, "", "rejected\n")})
        assert rel.cmd_publish(ns(title="主题", push=True), runner=runner) == 1
        out = capsys.readouterr().out
        assert "git push origin master 失败" in out
        assert not any("--tags" in call for call in runner.calls), "推送失败后不再推 tag"


class TestEvolutionFailureBranches:
    """演进快照的两处外部依赖失败：派生失败与统计同步失败。"""

    def test_derivation_error_reports_and_returns_two(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.FOLDERS_FILE.write_text("# 无可定位演进表\n", encoding="utf-8")
        runner = FakeRunner(responses=[(["git", "ls-files"], (0, "README.md\n", ""))])
        assert rel.cmd_evolution(ns(release=False), runner=runner) == 2
        assert "[ERR]" in capsys.readouterr().out

    def test_stats_sync_failure_returns_code(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        runner = FakeRunner(
            responses=[
                (["git", "ls-files"], (0, "docs/managements/folders.md\n", "")),
                (["scripts/check-doc-drift.py"], (2, "", "统计不一致\n")),
            ]
        )
        assert rel.cmd_evolution(ns(release=False), runner=runner) == 2
        assert "统计不一致" in capsys.readouterr().out
        _ = fx


class TestReleaseClosureProblems:
    """发布闭环校验：tag 落在 master 历史内、master 跟版、dev 为下一开发版。"""

    def test_missing_tag_is_warning_only(self, rel, release_repo):
        runner = FakeRunner(responses=[(["git", "tag", "--list"], (0, "", ""))])
        errors, warnings = rel._cmd_ship._release_closure_problems(rel._env(), "0.12.6", "0.12.6", runner)
        assert errors == []
        assert warnings and "v0.12.6 不存在" in warnings[0]

    def test_tag_outside_master_history_is_error(self, rel, release_repo):
        runner = FakeRunner(
            responses=[
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (1, "", "")),
                (["git", "show"], (0, 'APP_VERSION = "0.12.6"\n', "")),
            ]
        )
        errors, _warnings = rel._cmd_ship._release_closure_problems(rel._env(), "0.12.6", "0.12.6", runner)
        assert any("不在 master 历史内" in item for item in errors)

    def test_master_constants_unreadable_is_error(self, rel, release_repo):
        runner = FakeRunner(
            responses=[
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (0, "", "")),
                (["git", "show"], (128, "", "path does not exist")),
            ]
        )
        errors, _warnings = rel._cmd_ship._release_closure_problems(rel._env(), "0.12.6", "0.12.6", runner)
        assert any("无法确认 master 版本" in item for item in errors)

    def test_master_version_behind_is_error(self, rel, release_repo):
        runner = FakeRunner(
            responses=[
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (0, "", "")),
                (["git", "show"], (0, 'APP_VERSION = "0.12.5"\n', "")),
            ]
        )
        errors, _warnings = rel._cmd_ship._release_closure_problems(rel._env(), "0.12.6", "0.12.6", runner)
        assert any("master 版本为 0.12.5" in item for item in errors)

    def test_master_constants_without_version_line_is_error(self, rel, release_repo):
        runner = FakeRunner(
            responses=[
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (0, "", "")),
                (["git", "show"], (0, "# 无版本行\n", "")),
            ]
        )
        errors, _warnings = rel._cmd_ship._release_closure_problems(rel._env(), "0.12.6", "0.12.6", runner)
        assert any("无 APP_VERSION 行" in item for item in errors)

    def test_dev_version_not_bumped_is_error(self, rel, release_repo):
        """切版后仍有写入/未切版 → dev 版本对不上，发布不可追溯。"""
        runner = FakeRunner(responses=[(["git", "tag", "--list"], (0, "", ""))])
        errors, _warnings = rel._cmd_ship._release_closure_problems(rel._env(), "0.12.6", "0.12.7-dev", runner)
        assert any("应为下一开发版 0.12.7-dev" in item for item in errors)


class TestDevBumpGuards:
    def test_non_dev_branch_rejected(self, rel, release_repo, capsys):
        runner = FakeRunner(responses=[(["git", "branch", "--show-current"], (0, "master\n", ""))])
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 2
        assert "devbump 仅在 dev 上执行" in capsys.readouterr().out

    def test_unparsable_version_rejected(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)  # 夹具常量文件写开发形态版本号
        runner = FakeRunner(responses=[(["git", "branch", "--show-current"], (0, "dev\n", ""))])
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 2
        assert "不是发布形态" in capsys.readouterr().out
        assert "0.12.6-dev" in fx.CONSTANTS_FILE.read_text(encoding="utf-8")

    def test_version_consistency_failure_returns_code(self, rel, release_repo, capsys):
        runner = FakeRunner(
            responses=[
                (["git", "branch", "--show-current"], (0, "dev\n", "")),
                (["scripts/check-version-consistency.py", "--fix"], (3, "", "16 处未收敛\n")),
            ]
        )
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 3
        assert "切版后版本一致性未收敛" in capsys.readouterr().out

    def test_open_closure_reports_errors_and_returns_one(self, rel, release_repo, capsys):
        """tag 打在别的分支：切版已落盘，但发布闭环未闭合 → 明确报错而非静默成功。"""
        runner = FakeRunner(
            responses=[
                (["git", "branch", "--show-current"], (0, "dev\n", "")),
                (["scripts/check-version-consistency.py", "--fix"], (0, "[OK]\n", "")),
                (["git", "status", "--porcelain"], (0, "", "")),
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (1, "", "")),
                (["git", "show"], (0, 'APP_VERSION = "0.12.6"\n', "")),
            ]
        )
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 1
        out = capsys.readouterr().out
        assert "不在 master 历史内" in out
        assert "发布闭环未闭合" in out

    def test_missing_tag_keeps_flow_green_with_warning(self, rel, release_repo, capsys):
        runner = FakeRunner(
            responses=[
                (["git", "branch", "--show-current"], (0, "dev\n", "")),
                (["scripts/check-version-consistency.py", "--fix"], (0, "[OK]\n", "")),
                (["git", "status", "--porcelain"], (0, "", "")),
                (["git", "tag", "--list"], (0, "", "")),
            ]
        )
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 0
        out = capsys.readouterr().out
        assert "v0.12.6 不存在" in out
        assert "发布闭环闭合" in out
