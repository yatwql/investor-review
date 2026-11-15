"""测试：发布终局命令（publish / devbump / check 前置） — release.py 第四部分

覆盖（设备见同目录 `_release_fixtures.py`）：
  - publish：提交→verify→合并→tag 顺序与合并信息含 verify 项数、verify 失败中止、
    已提交时跳过、--push 才执行推送、标题归一
  - devbump：切开发版落盘与分支拒绝
  - check 的本地门禁前置：统计快照 + dev-verify 先跑，返工挡在秒级

共享设备见同目录 `_release_fixtures.py`（子进程替身 / 临时仓库夹具 / 台账样例）。
"""

from __future__ import annotations

import json
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

_REPO_ROOT = Path(__file__).resolve().parents[4]

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def rel():
    return load_script("release.py", module_name="release_tool_publish")


@pytest.fixture(autouse=True)
def _isolate_release_runtime_paths(rel, monkeypatch, tmp_path):
    """发布运行态文件（通过戳/bench 戳/耗时台账）一律重定向到 tmp。

    回归背景：`TestGateArchivePrecondition` 曾未隔离 `GATE_STAMP_FILE`——gate 成功
    用例走完尾部写入，把仓库真实的 `logs/release-gate-stamp.json` 写成夹具版本号
    （发布时间戳也被改写），使「门禁通过戳」不可信；且每次跑单测都会再污染一次。
    """
    isolate_release_runtime_paths(rel, monkeypatch, tmp_path)


class TestPublish:
    def _fixture(self, rel_mod, tmp_path, version: str):
        fx = _ToolRepoFixture(rel_mod, tmp_path)
        fx.CONSTANTS_FILE.write_text(f'APP_VERSION = "{version}"\n', encoding="utf-8")
        return fx

    @staticmethod
    def _dirty_runner(verify_out="— 8,621 通过, 0 失败\n", verify_rc=0) -> FakeRunner:
        return _ok_runner(
            [
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
                (["scripts/test-runner.py"], (verify_rc, verify_out, "")),
            ]
        )

    def test_normalize_release_title_variants(self, rel):
        # 带前缀 / 单破折号前缀 → 纯描述；纯描述不变；剥离后为空回退原值
        assert rel.normalize_release_title("release: v0.12.6 —— 发布主题") == "发布主题"
        assert rel.normalize_release_title("release: v0.12.6 — 发布主题") == "发布主题"
        assert rel.normalize_release_title("纯描述") == "纯描述"
        assert rel.normalize_release_title("release: v0.12.6 ——") == "release: v0.12.6 ——"

    def test_normalize_release_title_strips_bare_version_prefix(self, rel):
        """裸版本前缀同样剥掉：人工把版本号写进 `--title` 是自然写法，
        不剥时 release 提交标题会拼出两遍版本号。"""
        assert rel.normalize_release_title("v0.12.6 —— 发布主题") == "发布主题"
        assert rel.normalize_release_title("v0.12.6 — 发布主题") == "发布主题"
        assert rel.normalize_release_title("v0.15.4-dev —— 发布主题") == "发布主题"
        # 非版本形态的数字串不动（避免误伤「v2 版方案」这类正文）
        assert rel.normalize_release_title("v2 —— 发布主题") == "v2 —— 发布主题"

    def test_title_prefix_normalized_to_single_subject(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        rc = rel.cmd_publish(ns(title="release: v0.12.6 —— 发布主题", push=False), runner=runner)
        assert rc == 0
        commit = next(c for c in runner.calls if len(c) > 2 and c[1] == "commit")
        assert commit[-1] == "release: v0.12.6 —— 发布主题"
        assert commit[-1].count("release: v0.12.6 ——") == 1  # 不得双前缀

    def test_commit_verify_merge_tag_order(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        rc = rel.cmd_publish(ns(title="主题", push=False), runner=runner)
        assert rc == 0
        commit_idx = next(i for i, c in enumerate(runner.calls) if len(c) > 2 and c[1] == "commit")
        verify_idx = next(i for i, c in enumerate(runner.calls) if any("test-runner.py" in p for p in c))
        merge_idx = next(i for i, c in enumerate(runner.calls) if len(c) > 2 and c[1] == "merge")
        tag_idx = next(i for i, c in enumerate(runner.calls) if len(c) > 2 and c[1] == "tag")
        assert "release: v0.12.6 —— 主题" in runner.calls[commit_idx][-1]
        assert commit_idx < verify_idx < merge_idx < tag_idx
        merge_msg = runner.calls[merge_idx][runner.calls[merge_idx].index("-m") + 1]
        assert "8621 项已全绿" in merge_msg
        assert not any("push" in c for c in runner.calls)  # 默认不推送

    def test_reuses_gate_stamp_when_code_fingerprint_matches(self, rel, tmp_path):
        """gate 已跑 verify 且树指纹一致 → publish 跳过 verify（不重复 28s）。"""
        fx = self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        fingerprint = rel._code_fingerprint(runner)
        fx.GATE_STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        fx.GATE_STAMP_FILE.write_text(
            json.dumps({"version": "0.12.6", "fingerprint": fingerprint, "verify_passed": "9000"}),
            encoding="utf-8",
        )
        rc = rel.cmd_publish(ns(title="t", push=False), runner=runner)
        assert rc == 0
        assert not any(any("test-runner.py" in p for p in c) for c in runner.calls)
        merge = next(c for c in runner.calls if len(c) > 2 and c[1] == "merge")
        assert "9000 项已全绿" in merge[merge.index("-m") + 1]

    def test_publish_explains_why_verify_reruns(self, rel, tmp_path, capsys):
        """gate 后代码有改动 → publish 明说「哪些文件动了、将实跑 verify」，不是白跑。"""
        fx = self._fixture(rel, tmp_path, "0.12.6")
        fx.GATE_STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        fx.GATE_STAMP_FILE.write_text(
            json.dumps(
                {
                    "version": "0.12.6",
                    "fingerprint": "stale",
                    "verify_passed": "1",
                    "code_files": {"src/python/x.py": "aa"},
                }
            ),
            encoding="utf-8",
        )
        runner = self._dirty_runner()
        assert rel.cmd_publish(ns(title="主题", push=False), runner=runner) == 0
        printed = capsys.readouterr().out
        assert "个代码文件改动" in printed
        assert "src/python/x.py" in printed
        assert "实跑 P1 verify" in printed

    def test_code_fingerprint_ignores_docs_changes(self, rel):
        """发布戳用代码指纹：文档统计同步不会让 gate 的 verify 失效（全树指纹会）。"""
        runner = FakeRunner(
            responses=[
                (["git", "status", "--porcelain", "--", "src"], (0, "", "")),
                (["git", "diff", "HEAD", "--", "src"], (0, "", "")),
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
            ]
        )
        assert rel._code_fingerprint(runner) != rel._tree_fingerprint(runner)

    def test_code_fingerprint_independent_of_commit_state(self, rel, tmp_path):
        """回归：指纹必须与「改动是否已提交」无关（publish 会先提交再算指纹）。

        判定口径：用 `git diff HEAD` + `git status` 哈希会把「同一份代码」在提交前后
        算成两个指纹（gate 打戳时 prepare 的改动未提交，publish 先提交再算），
        复用分支按构造永不命中——故指纹必须取文件内容哈希。
        """
        code_fingerprint = load_script("_release/_gate.py").code_fingerprint

        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        listing = "src/a.py\0"

        def _exec_before_commit(cmd, root, runner=None):
            if cmd[:2] == ["git", "ls-files"]:
                return (0, listing, "")
            return (0, " M src/a.py\n", "")  # 未提交态：diff/status 有内容

        def _exec_after_commit(cmd, root, runner=None):
            if cmd[:2] == ["git", "ls-files"]:
                return (0, listing, "")
            return (0, "", "")  # 已提交：diff/status 干净

        before = code_fingerprint(_exec_before_commit, str(tmp_path))
        after = code_fingerprint(_exec_after_commit, str(tmp_path))
        assert before and before == after, "同一份代码在提交前后必须得到同一指纹"

        (tmp_path / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
        assert code_fingerprint(_exec_before_commit, str(tmp_path)) != before, "代码内容变化必须改变指纹"

    def test_runs_verify_when_stamp_fingerprint_mismatches(self, rel, tmp_path):
        """指纹不一致（gate 后改过代码）→ 不盲信戳，实跑 verify。"""
        fx = self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        fx.GATE_STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        fx.GATE_STAMP_FILE.write_text(
            json.dumps({"version": "0.12.6", "fingerprint": "stale", "verify_passed": "1"}),
            encoding="utf-8",
        )
        assert rel.cmd_publish(ns(title="t", push=False), runner=runner) == 0
        assert any(any("test-runner.py" in p for p in c) for c in runner.calls)

    def test_verify_failure_aborts_before_merge(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner(verify_out="", verify_rc=1)
        rc = rel.cmd_publish(ns(title="t", push=False), runner=runner)
        assert rc == 1
        heads = [c[1] for c in runner.calls if c[0] == "git"]
        assert "merge" not in heads and "tag" not in heads and "checkout" not in heads

    def test_skips_commit_when_tree_clean(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = _ok_runner([(["scripts/test-runner.py"], (0, "— 10 通过, 0 失败\n", ""))])
        rc = rel.cmd_publish(ns(title="t", push=False), runner=runner)
        assert rc == 0
        assert not any(len(c) > 2 and c[1] in {"add", "commit"} for c in runner.calls)

    def test_syncs_stats_before_commit_with_hook_parity_args(self, rel, tmp_path):
        """提交前必须按 pre-commit 钩子同源参数同步统计快照。

        回归：钩子对含 `src/test` 变更的提交走 `--sync --ci --with-test-count`，
        而只跑 `--sync` 时 test-coverage.md 的收集派生计数不被校验——本地「通过」、
        钩子里仍红，publish 白跑一轮（实测曾连败两次）。
        """
        self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        assert rel.cmd_publish(ns(title="t", push=False), runner=runner) == 0
        sync_idx = next(i for i, c in enumerate(runner.calls) if any("check-doc-drift.py" in p for p in c))
        sync_call = runner.calls[sync_idx]
        assert {"--sync", "--ci", "--with-test-count"} <= set(sync_call)
        commit_idx = next(i for i, c in enumerate(runner.calls) if len(c) > 2 and c[1] == "commit")
        assert sync_idx < commit_idx  # 同步必须先于提交，否则钩子仍会拦

    def test_stats_sync_failure_aborts_before_commit(self, rel, tmp_path):
        """统计同步失败即中止：不得带着陈旧计数去撞钩子。"""
        self._fixture(rel, tmp_path, "0.12.6")
        runner = _ok_runner(
            [
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
                (["scripts/check-doc-drift.py"], (2, "test-coverage.md:16 覆盖项数不一致\n", "")),
            ]
        )
        rc = rel.cmd_publish(ns(title="t", push=False), runner=runner)
        assert rc == 2
        assert not any(len(c) > 2 and c[1] in {"add", "commit", "merge", "tag"} for c in runner.calls)

    def test_push_flag_gates_push_calls(self, rel, tmp_path):
        self._fixture(rel, tmp_path, "0.12.6")
        runner = _ok_runner([(["scripts/test-runner.py"], (0, "— 10 通过, 0 失败\n", ""))])
        rc = rel.cmd_publish(ns(title="t", push=True), runner=runner)
        assert rc == 0
        pushed = [c for c in runner.calls if "push" in c]
        assert len(pushed) == 3  # dev / master / --tags


class TestDevBump:
    def test_writes_next_dev_and_commits(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "status", "--porcelain"], (0, " M docs/x.md\n", ""))])
        rc = rel.cmd_devbump(ns(push=False), runner=runner)
        assert rc == 0
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.7-dev"
        commit = next(c for c in runner.calls if len(c) > 2 and c[1] == "commit")
        assert commit[-1] == "chore: 切 0.12.7-dev 开发版本（v0.12.6 发布后）"
        assert not any("push" in c for c in runner.calls)

    def test_pushes_dev_by_default(self, rel, tmp_path):
        """默认推送 dev：发布闭环的收尾要把切版提交同步到远端（上一版需人工补 push）。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "status", "--porcelain"], (0, " M docs/x.md\n", ""))])
        assert rel.cmd_devbump(ns(), runner=runner) == 0
        pushes = [c for c in runner.calls if c[:3] == ["git", "push", "origin"]]
        assert pushes == [["git", "push", "origin", "dev"]]

    def test_no_push_skips_push(self, rel, tmp_path, capsys):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "status", "--porcelain"], (0, " M docs/x.md\n", ""))])
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 0
        assert not any("push" in c for c in runner.calls)
        assert "git push origin dev" in capsys.readouterr().out

    def test_push_failure_keeps_commit_and_reports(self, rel, tmp_path):
        """推送失败不得回滚切版提交，但要明确报错并给出重试命令。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner(
            [
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
                (["git", "push"], (1, "", "network unreachable")),
            ]
        )
        assert rel.cmd_devbump(ns(), runner=runner) == 1
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.7-dev"

    def test_cli_defaults_to_push(self, rel):
        """CLI 默认值即「推送」；`--no-push` 才关闭（文档口径与代码同一事实位）。"""
        parser = rel.build_parser()
        assert parser.parse_args(["devbump"]).push is True
        assert parser.parse_args(["devbump", "--no-push"]).push is False
        assert parser.parse_args(["devbump", "--push"]).push is True  # 兼容别名

    def test_clears_previous_release_placeholder(self, rel, tmp_path):
        """切开发版时清掉上一版迁档占位节（新周期台账从空开始）。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        fx.RF_FILE.write_text(
            "# 台账\n\n## 已解决问题\n\n### 开发期已修复（0.12.6-dev）\n\n"
            "（本版开发期已修复项已随 v0.12.6 发布迁入归档档案）\n\n### 归档档案\n- 索引行\n",
            encoding="utf-8",
        )
        runner = _ok_runner([(["git", "status", "--porcelain"], (0, " M docs/x.md\n", ""))])
        rc = rel.cmd_devbump(ns(push=False), runner=runner)
        assert rc == 0
        text = fx.RF_FILE.read_text(encoding="utf-8")
        assert "发布迁入归档档案" not in text
        assert "（0.12.6-dev）" not in text
        assert "### 归档档案" in text

    def test_devbump_records_step_timings(self, rel, tmp_path):
        """devbump 也要留下分步耗时（台账此前只有总墙钟，无法定位推送/切版提交占比）。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "status", "--porcelain"], (0, " M docs/x.md\n", ""))])
        rel._reset_timer()
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 0
        labels = [entry["step"] for entry in rel._timer().steps]
        assert "版本全链改写 + 一致性收敛" in labels
        assert "切版提交" in labels
        assert "发布闭环校验" in labels

    def test_closure_check_passes_when_tag_and_master_aligned(self, rel, tmp_path, capsys):
        """闭环闭合：tag 存在且在 master 历史内、master 为发布版。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner(
            [
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (0, "", "")),
                (["git", "show"], (0, 'APP_VERSION = "0.12.6"\n', "")),
            ]
        )
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 0
        assert "[OK] 发布闭环闭合" in capsys.readouterr().out

    def test_closure_check_flags_master_version_mismatch(self, rel, tmp_path, capsys):
        """master 未跟版（只打 tag 不更新 master）是可追溯性缺口，必须硬失败。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner(
            [
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (0, "", "")),
                (["git", "show"], (0, 'APP_VERSION = "0.12.5"\n', "")),
            ]
        )
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 1
        assert "master 版本为 0.12.5" in capsys.readouterr().out

    def test_closure_check_flags_tag_outside_master(self, rel, tmp_path, capsys):
        """tag 不在 master 历史内（打在别的分支）同样硬失败。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner(
            [
                (["git", "status", "--porcelain"], (0, " M docs/x.md\n", "")),
                (["git", "tag", "--list"], (0, "v0.12.6\n", "")),
                (["git", "merge-base"], (1, "", "")),
                (["git", "show"], (0, 'APP_VERSION = "0.12.6"\n', "")),
            ]
        )
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 1
        assert "不在 master 历史内" in capsys.readouterr().out

    def test_closure_check_missing_tag_is_warning_only(self, rel, tmp_path, capsys):
        """无 tag 只告警：`--no-push` 试跑/非发布库不该因缺 tag 让切版失败。"""
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "status", "--porcelain"], (0, " M docs/x.md\n", ""))])
        assert rel.cmd_devbump(ns(push=False), runner=runner) == 0
        out = capsys.readouterr().out
        assert "v0.12.6 不存在" in out
        assert "发布闭环闭合" in out

    def test_rejects_non_dev_branch(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "branch", "--show-current"], (0, "master\n", ""))])
        rc = rel.cmd_devbump(ns(push=False), runner=runner)
        assert rc == 2
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.6"


class TestCheckLocalGate:
    """`release.py check` 的本地门禁前置（统计快照 + dev-verify）。

    真实事故：一次发布里 refresh 失败 1 次、gate 失败 3 次，累计白跑 ≈150s 门禁
    墙钟——根因是改完代码只跑局部测试就进 gate，统计快照也没同步。两条前置把
    这类返工挡在 check（秒级~30s）。
    """

    def test_doc_snapshot_passes_through_success(self, monkeypatch, tmp_path):
        """成功路径：底层 rc=0 → 无 findings（真跑全仓由 CI 的 guards job 覆盖）。"""
        import scripts._release._local_gate as lg

        monkeypatch.setattr(lg, "_run", lambda cmd, root: (0, ""))
        ok, msg = lg.check_doc_snapshot(tmp_path)
        assert ok is True and msg == ""

    def test_doc_snapshot_reports_fix_hint(self, monkeypatch, tmp_path):
        import scripts._release._local_gate as lg

        monkeypatch.setattr(lg, "_run", lambda cmd, root: (2, "docs/managements/folders.md: 行数不一致"))
        ok, msg = lg.check_doc_snapshot(tmp_path)
        assert ok is False
        assert "test-collect-coverage.py --update-docs" in msg
        assert "行数不一致" in msg

    def test_local_tests_passes_through_success(self, monkeypatch, tmp_path):
        """成功路径：dev-verify rc=0 → 无 findings（不在此处真跑 30s，CI 覆盖）。"""
        import scripts._release._local_gate as lg

        monkeypatch.setattr(lg, "_run", lambda cmd, root: (0, ""))
        ok, msg = lg.check_local_tests(tmp_path)
        assert ok is True and msg == ""

    def test_local_tests_surfaces_failures(self, monkeypatch, tmp_path):
        import scripts._release._local_gate as lg

        out = "  [ERR] test_a 失败\n  [ERR] test_b 失败\n"
        monkeypatch.setattr(lg, "_run", lambda cmd, root: (1, out))
        ok, msg = lg.check_local_tests(tmp_path)
        assert ok is False
        assert "test-extract-failures" in msg
        assert "[ERR] test_a 失败" in msg

    def test_check_command_skips_gate_with_flag(self):
        """`--no-local-gate` 跳过两项前置（只看文档派生时用）。"""
        import inspect

        from scripts._release import _cli, _commands_prep

        assert "--no-local-gate" in inspect.getsource(_cli)
        assert "no_local_gate" in inspect.getsource(_commands_prep)
