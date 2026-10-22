"""测试：发布流程的门禁与编排子命令 — release.py 第二部分

覆盖（设备见同目录 `_release_fixtures.py`）：
  - 门禁：守护清单与 scripts/ 实体同源且互异、regression 先行、失败即停、
    最坏退出码传递、并行度随核数收敛、设计护栏、耗时埋点
  - refresh：三步顺序执行、首步失败即停、bench 模式范围、纯文档变更跳过
  - publish：提交→verify→合并→tag 顺序与合并信息含 verify 项数、verify 失败中止、
    已提交时跳过、--push 才执行推送、标题归一
  - devbump：切开发版落盘与分支拒绝
  - gate 归档前置：未迁档 / 缺批次节 / 仍是开发版 三类拦截 + 无自审条目放行
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
        """门禁三步（并行 verify+回归 / 十守护 / 设计护栏）入计时器。"""
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "stamp.json")
        rel._reset_timer()
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        labels = [entry["step"] for entry in rel._timer().steps]
        assert labels == ["P2 verify+regression（并行）", "P2 十守护", "P2 设计护栏"]
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
        """gate 同时跑 P1 verify 与 P2 regression（并行），且都在十守护之前。"""
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
        """发布门禁包含设计护栏（E 级拦 / W 级观察统计；不并入十守护清单）。"""
        runner = FakeRunner()
        rc = rel.cmd_gate(ns(), runner=runner)
        assert rc == 0
        guardrail_calls = [c for c in runner.calls if any("style-guardrails" in part for part in c)]
        assert len(guardrail_calls) == 1
        assert "--ci" in guardrail_calls[0]
        # 护栏在十守护之后执行（守护清单语义独立）
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
        assert not any(any("check-" in p for p in c) for c in runner.calls)  # 回归/verify 失败 → 十守护一个不跑

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

    def test_gate_writes_stamp_with_tree_fingerprint(self, rel, monkeypatch, tmp_path):
        """gate 全绿后写「版本 + 树指纹 + verify 项数」戳，供 publish 复用。"""
        stamp = tmp_path / "stamp.json"
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", stamp)
        runner = FakeRunner(responses=[(["scripts/test-runner.py"], (0, "— 9,000 通过, 0 失败\n", ""))])
        assert rel.cmd_gate(ns(), runner=runner) == 0
        data = json.loads(stamp.read_text(encoding="utf-8"))
        assert data["version"] == "0.13.12"
        assert data["verify_passed"] == "9000"
        assert data["fingerprint"] == rel._tree_fingerprint(runner)

    def test_gate_with_portability_runs_probe(self, rel, monkeypatch, tmp_path):
        monkeypatch.setattr(rel, "GATE_STAMP_FILE", tmp_path / "stamp.json")
        runner = FakeRunner()
        assert rel.cmd_gate(ns(with_portability=True), runner=runner) == 0
        modes = {_mode_arg(c) for c in runner.calls if any("test-runner.py" in p for p in c)}
        assert "portability" in modes

    def test_gate_returns_worst_guard_code(self, rel):
        responses = [
            (["scripts/test-runner.py"], (0, "", "")),
            ([rel.GUARD_SCRIPTS[3]], (2, "finding: x", "")),
        ]
        rc = rel.cmd_gate(ns(), runner=FakeRunner(responses=responses))
        assert rc == 2


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

    def test_reuses_gate_stamp_when_tree_fingerprint_matches(self, rel, tmp_path):
        """gate 已跑 verify 且树指纹一致 → publish 跳过 verify（不重复 28s）。"""
        fx = self._fixture(rel, tmp_path, "0.12.6")
        runner = self._dirty_runner()
        fingerprint = rel._tree_fingerprint(runner)
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

    def test_rejects_non_dev_branch(self, rel, tmp_path):
        fx = _ToolRepoFixture(rel, tmp_path)
        fx.CONSTANTS_FILE.write_text('APP_VERSION = "0.12.6"\n', encoding="utf-8")
        runner = _ok_runner([(["git", "branch", "--show-current"], (0, "master\n", ""))])
        rc = rel.cmd_devbump(ns(push=False), runner=runner)
        assert rc == 2
        assert rel.read_app_version(fx.CONSTANTS_FILE.read_text(encoding="utf-8")) == "0.12.6"


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


# ─────────────────────────── refresh / evolution 命令 ───────────────────────────


class TestRefresh:
    """refresh 条件化：自上一 release tag 起仅文档变更 → 跳过 bench/collect
    （doc-drift --sync 恒跑）；有程序/测试变更或 --force-refresh → 三步全跑。"""

    _TAG = (["describe"], (0, "v0.13.9", ""))
    _PROGRAM_CHANGE = (["diff", "--name-only"], (0, "src/python/x.py\n", ""))
    _DOCS_ONLY = (["diff", "--name-only"], (0, "README.md\ndocs/plan/y.md\n", ""))

    def test_three_steps_in_order_when_program_changed(self, rel):
        runner = FakeRunner(responses=[self._TAG, self._PROGRAM_CHANGE])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = runner.calls[3:]  # 前 3 个调用：describe / diff / ls-files
        assert len(steps) == 3
        assert "--update-docs" in steps[0]
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)
        assert any("test-collect-coverage" in p for p in steps[1])
        assert any("check-doc-drift" in p for p in steps[2])

    def test_docs_only_skips_bench_and_collect(self, rel):
        runner = FakeRunner(responses=[self._TAG, self._DOCS_ONLY])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = runner.calls[3:]
        assert len(steps) == 1  # 仅 sync
        assert any("check-doc-drift" in p for p in steps[0])

    def test_force_refresh_runs_all_steps(self, rel):
        runner = FakeRunner()
        rc = rel.cmd_refresh(ns(force_refresh=True), runner=runner)
        assert rc == 0
        assert len(runner.calls) == 3  # 无 git 判定，直接三步
        assert "--update-docs" in runner.calls[0]
        assert _mode_arg(runner.calls[0]) == ",".join(rel.RELEASE_BENCH_MODES)
        assert any("test-collect-coverage" in p for p in runner.calls[1])

    def test_missing_tag_conservatively_refreshes(self, rel):
        runner = FakeRunner(responses=[(["describe"], (128, "", "no tag here"))])
        rc = rel.cmd_refresh(ns(), runner=runner)
        assert rc == 0
        steps = runner.calls[1:]
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
        steps = runner.calls[3:]
        assert len(steps) == 3
        assert _mode_arg(steps[0]) == ",".join(rel.RELEASE_BENCH_MODES)

    def test_full_bench_flag_runs_all_modes(self, rel):
        """`--full-bench` 走 bench 别名（全量 14 档）——重测全表耗时的手动入口。"""
        runner = FakeRunner()
        rc = rel.cmd_refresh(ns(force_refresh=True, full_bench=True), runner=runner)
        assert rc == 0
        assert _mode_arg(runner.calls[0]) == "bench"

    def test_release_bench_modes_are_real_modes(self, rel):
        """子集模式必须是 test-runner 的真实模式键：拼错会让 bench 直接报错退出，
        表不回填、发布链在 refresh 就断（结构与实现双向对齐）。"""
        runner_mod = load_script("test-runner.py", module_name="test_runner_bench_modes")
        assert set(rel.RELEASE_BENCH_MODES) <= set(runner_mod.MODES)
        assert "bench" not in rel.RELEASE_BENCH_MODES  # 别名不得混入子集

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
        from _release import _timing

        log = tmp_path / "logs" / "release.jsonl"
        for i in range(8):
            _timing.append_record(log, {"command": f"cmd{i}"}, max_lines=5)
        lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) == 5
        assert json.loads(lines[-1])["command"] == "cmd7"
        assert all(ln.startswith("{") and ln.endswith("}") for ln in lines)

    def test_log_write_failure_raises_for_caller_decision(self, rel, tmp_path):
        """写盘失败以异常如实上报（调用方据以打 [!]），不静默当成已写入。"""
        from _release import _timing

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
