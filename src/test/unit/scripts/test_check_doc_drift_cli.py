"""测试：check-doc-drift.py 的缓存输入面、verbose 统计段与 --sync 回写编排。

覆盖：
  - `_cache_inputs`：git tracked + 未跟踪（排除忽略）并集去重；非 git 环境
    （返回码非 0 / 调用超时）→ None（跳过缓存，直接全量检查）
  - `_run_checks_phase` 的 -v 统计段（受检文档数/章节与开关数/开关表行/
    目录树与实测文件数/统计快照逐项/章节-区块矩阵行数）与退出码
  - `main --sync`：回写结果打印 + git add 入暂存；git add 超时降级提示
  - 导入期 `sys.path` 自助修补（REPO_ROOT 不在路径上时由脚本补入）

git 调用一律替换为探针桩（不执行真实 git 写），文档解析入口亦替换为最小假文档。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_module_file, load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(scope="module")
def drift():
    return load_script("check-doc-drift.py")


class TestCacheInputs:
    """结论缓存输入面（git tracked + 未跟踪全集）。"""

    def _stub(self, monkeypatch, drift, results):
        calls: list[list[str]] = []

        def _run(cmd, **kwargs):
            calls.append(list(cmd))
            return results.pop(0)

        monkeypatch.setattr(drift.subprocess, "run", _run)
        return calls

    def test_merges_tracked_and_untracked_deduped(self, drift, monkeypatch):
        ok_a = SimpleNamespace(returncode=0, stdout="a.py\nb.py\n", stderr="")
        ok_b = SimpleNamespace(returncode=0, stdout="b.py\nc.py\n", stderr="")  # b.py 重复
        calls = self._stub(monkeypatch, drift, [ok_a, ok_b])
        inputs = drift._cache_inputs()
        assert inputs is not None
        assert [p.name for p in inputs] == ["a.py", "b.py", "c.py"]
        assert all(p.is_absolute() for p in inputs)
        # 第二次调用带未跟踪文件参数（--others --exclude-standard）
        assert "--others" in calls[1]

    def test_git_failure_returns_none(self, drift, monkeypatch):
        failed = SimpleNamespace(returncode=128, stdout="", stderr="")
        self._stub(monkeypatch, drift, [failed, failed])
        assert drift._cache_inputs() is None

    def test_git_timeout_returns_none(self, drift, monkeypatch):
        def _run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 120)

        monkeypatch.setattr(drift.subprocess, "run", _run)
        assert drift._cache_inputs() is None


class TestVerbosePhase:
    """-v 统计段与 report 退出码。"""

    @pytest.fixture
    def fake_docs(self, drift, monkeypatch):
        docs = {
            drift._HOW_TO_CONFIG_MD: "",
            drift._FOLDERS_MD: "",
            drift._TECHNICAL_MD: "",
        }
        monkeypatch.setattr(drift, "_scan_docs", lambda: docs)
        monkeypatch.setattr(drift, "run_checks", lambda **kwargs: [])
        monkeypatch.setattr(drift, "_stats_actual", lambda: {"主程序": (3, 120)})
        monkeypatch.setattr(drift, "_actual_files", lambda: [])
        return docs

    def test_verbose_prints_statistics(self, drift, fake_docs, capsys):
        args = SimpleNamespace(verbose=True, ci=False, with_test_count=False)
        rc = drift._run_checks_phase(args)
        out = capsys.readouterr().out
        assert rc == 0
        assert "受检文档" in out
        assert "报告章节" in out and "功能开关" in out
        assert "目录树解析" in out
        assert "主程序: 3 文件 / 120 行" in out
        assert "章节-区块矩阵解析" in out

    def test_non_verbose_skips_statistics(self, drift, fake_docs, monkeypatch, capsys):
        monkeypatch.setattr(drift, "_stats_actual", lambda: pytest.fail("非 verbose 不应统计"))
        args = SimpleNamespace(verbose=False, ci=False, with_test_count=False)
        assert drift._run_checks_phase(args) == 0
        assert "受检文档" not in capsys.readouterr().out


class TestSync:
    """`main --sync`：统计回写与入暂存（含 git 超时降级）。"""

    def _run_main(self, drift, monkeypatch, applied, run_git):
        monkeypatch.setattr(sys, "argv", ["check-doc-drift.py", "--sync"])
        monkeypatch.setattr(drift, "sync_project_stats", lambda: applied)
        monkeypatch.setattr(drift, "_run_checks_phase", lambda args: 0)
        monkeypatch.setattr(drift.subprocess, "run", run_git)
        with pytest.raises(SystemExit) as excinfo:
            drift.main()
        return excinfo.value.code

    def test_applied_lines_printed_and_staged(self, drift, monkeypatch, capsys):
        calls: list[list[str]] = []

        def _run(cmd, **kwargs):
            calls.append(list(cmd))
            return SimpleNamespace(returncode=0)

        rc = self._run_main(drift, monkeypatch, ["主程序行数 1 → 2"], _run)
        out = capsys.readouterr().out
        assert rc == 0
        assert "[sync]" in out and "主程序行数 1 → 2" in out
        assert calls and calls[0][:2] == ["git", "add"]

    def test_nothing_to_sync_reports_consistent(self, drift, monkeypatch, capsys):
        rc = self._run_main(drift, monkeypatch, [], lambda cmd, **kwargs: pytest.fail("无回写不应调用 git"))
        assert rc == 0
        assert "无需回写" in capsys.readouterr().out

    def test_git_add_timeout_degrades(self, drift, monkeypatch, capsys):
        def _run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 120)

        rc = self._run_main(drift, monkeypatch, ["行回写"], _run)
        assert rc == 0
        assert "git add 超时" in capsys.readouterr().out


class TestImportPathRepair:
    """导入期 sys.path 自助修补：REPO_ROOT 不在路径上时由脚本补入（任意 cwd 可跑）。"""

    def test_inserts_repo_root_when_missing(self, drift):
        repo_root = str(drift.REPO_ROOT)
        original = list(sys.path)
        sys.path[:] = [p for p in sys.path if p != repo_root]
        try:
            fresh = load_module_file(SCRIPTS_DIR / "check-doc-drift.py", "doc_drift_pathprobe")
            assert repo_root in sys.path
            assert fresh.REPO_ROOT == drift.REPO_ROOT
        finally:
            sys.path[:] = original
            sys.modules.pop("doc_drift_pathprobe", None)


class TestDocPaths:
    """常量面：受检文档均指向仓库内文件（回写/断言目标不悬空）。"""

    def test_doc_paths_exist(self, drift):
        paths = [drift._FOLDERS_MD, drift._HOW_TO_CONFIG_MD, drift._TECHNICAL_MD]
        assert all(isinstance(p, Path) and p.exists() for p in paths)
