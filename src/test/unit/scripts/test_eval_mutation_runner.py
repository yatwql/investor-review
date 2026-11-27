"""`_eval_mutation/runner.py` 单测：执行协议（备份/还原/分类/安全阀）。

**绝不碰仓库真实源码**：每个用例在 `tmp_path` 里造临时模块，`run_slice(repo_root=tmp_path)`；
pytest 子进程一律由桩替代（离线、秒级），桩里顺便断言「跑测试时磁盘上确实是变异版」。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

#: 临时模块的源码：3 个变异点（一处比较取反 + 两处返回值替换）
MODULE_SOURCE = '"""演示模块（临时目录内）。"""\n\n\ndef pick(a, b):\n    if a > b:\n        return a\n    return b\n'


@pytest.fixture(name="mutation")
def fixture_mutation():
    """加载入口脚本（每次全新模块实例：模块级备份登记表不外溢）。"""
    return load_script("eval-mutation-score.py")


def _write_module(root: Path, relative: str, source: str = MODULE_SOURCE) -> Path:
    """在临时仓库根下写一个源码文件（目录按需创建）。"""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _target(mutation, *, paths, tests=("tests/test_demo.py",)):
    """临时切片（路径相对临时仓库根）。"""
    return mutation.MutationTarget(name="tmp-slice", paths=paths, tests=tests, rationale="单测用切片")


def _stub_run(monkeypatch, mutation, *, returncode: int, seen: list[Path] | None = None, path: Path | None = None):
    """把 pytest 子进程换成固定退出码的桩；`seen` 收「跑测试那一刻的磁盘内容」。"""
    calls: list[dict] = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        if seen is not None and path is not None:
            seen.append(path.read_bytes())
        return subprocess.CompletedProcess(args=list(command), returncode=returncode, stdout="", stderr="")

    monkeypatch.setattr(mutation.subprocess, "run", fake_run)
    return calls


class TestBackupAndRestore:
    """备份/还原是唯一的安全底线：跑完（含异常路径）源码必须与原文逐字节一致。"""

    def test_killed_mutant_is_on_disk_during_test_run_and_restored_after(self, mutation, tmp_path, monkeypatch):
        path = _write_module(tmp_path, "pkg/mod.py")
        original = path.read_bytes()
        seen: list[bytes] = []
        _stub_run(monkeypatch, mutation, returncode=1, seen=seen, path=path)

        run = mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path)

        assert run.counts.killed == run.counts.executed == len(seen)
        assert all(content != original for content in seen)  # 跑测试时磁盘上是变异版
        assert path.read_bytes() == original  # 跑完逐字节还原

    def test_survived_mutant_is_reported_with_its_label(self, mutation, tmp_path, monkeypatch):
        path = _write_module(tmp_path, "pkg/mod.py")
        _stub_run(monkeypatch, mutation, returncode=0)

        run = mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path)

        assert run.counts.survived == run.counts.executed
        assert run.counts.score == 0.0
        assert run.survivors
        assert all(outcome.mutant.path == "pkg/mod.py" for outcome in run.survivors)
        assert path.read_bytes() == _write_bytes(MODULE_SOURCE)

    def test_timeout_is_counted_separately_and_restores(self, mutation, tmp_path, monkeypatch):
        path = _write_module(tmp_path, "pkg/mod.py")
        original = path.read_bytes()

        def raise_timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=1)

        monkeypatch.setattr(mutation.subprocess, "run", raise_timeout)
        run = mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path, mutant_timeout=1)

        assert run.counts.timed_out == run.counts.executed > 0
        assert run.counts.evaluated == 0  # 超时不进分母
        assert run.counts.score is None
        assert path.read_bytes() == original

    @pytest.mark.parametrize("returncode", [2, 3, 4, 5])
    def test_non_one_failure_code_counts_as_error(self, mutation, tmp_path, monkeypatch, returncode):
        path = _write_module(tmp_path, "pkg/mod.py")
        original = path.read_bytes()
        _stub_run(monkeypatch, mutation, returncode=returncode)

        run = mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path)

        assert run.counts.errored == run.counts.executed > 0
        assert run.counts.evaluated == 0
        assert path.read_bytes() == original

    def test_launch_failure_counts_as_error_and_restores(self, mutation, tmp_path, monkeypatch):
        path = _write_module(tmp_path, "pkg/mod.py")
        original = path.read_bytes()

        def raise_oserror(*_args, **_kwargs):
            raise OSError("no such executable")

        monkeypatch.setattr(mutation.subprocess, "run", raise_oserror)
        run = mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path)

        assert run.counts.errored == run.counts.executed > 0
        assert path.read_bytes() == original

    def test_restore_verification_failure_is_loud(self, mutation, tmp_path, monkeypatch):
        path = _write_module(tmp_path, "pkg/mod.py")
        _stub_run(monkeypatch, mutation, returncode=1)
        real_write = Path.write_bytes

        def tampering_write(self, data):
            return real_write(self, bytes(data) + "\n# 篡改\n".encode())

        monkeypatch.setattr(Path, "write_bytes", tampering_write)
        with pytest.raises(mutation.RestoreError):
            mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path)
        assert path.exists()  # 文件仍在（只校验失败，不删文件）


def _write_bytes(source: str) -> bytes:
    """期望的磁盘字节（与 runner 写入口径一致：UTF-8）。"""
    return source.encode("utf-8")


class TestBounds:
    """安全阀：变异体上限、切片时限、并行度都要如实反映在计数与 note 里。"""

    def test_max_mutants_truncates_and_reports_both_numbers(self, mutation, tmp_path, monkeypatch):
        _write_module(tmp_path, "pkg/mod.py")
        calls = _stub_run(monkeypatch, mutation, returncode=1)

        run = mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path, max_mutants=1)

        assert len(calls) == 1
        assert run.counts.executed == 1
        assert run.counts.generated is not None and run.counts.generated > 1
        assert any("截断" in note for note in run.notes)

    def test_slice_deadline_skips_remaining_mutants(self, mutation, tmp_path, monkeypatch):
        _write_module(tmp_path, "pkg/mod.py")
        calls = _stub_run(monkeypatch, mutation, returncode=1)

        run = mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path, slice_timeout=0)

        assert calls == []
        assert run.counts.executed == 0
        assert any("时限" in note for note in run.notes)

    def test_parallel_run_covers_every_file_of_the_slice(self, mutation, tmp_path, monkeypatch):
        _write_module(tmp_path, "pkg/one.py")
        _write_module(tmp_path, "pkg/two.py")
        _stub_run(monkeypatch, mutation, returncode=1)

        run = mutation.run_slice(_target(mutation, paths=("pkg/one.py", "pkg/two.py")), repo_root=tmp_path, jobs=2)

        assert run.counts.executed == run.counts.generated
        assert run.counts.killed == run.counts.executed
        assert any("并行度" in note for note in run.notes)
        assert (tmp_path / "pkg" / "one.py").read_text(encoding="utf-8") == MODULE_SOURCE
        assert (tmp_path / "pkg" / "two.py").read_text(encoding="utf-8") == MODULE_SOURCE


class TestSubprocessContract:
    """子进程契约：只跑切片声明的测试、命中首个失败即停、绝不写 `.pyc`。"""

    def test_command_is_scoped_to_the_slice_tests_and_cannot_write_bytecode(self, mutation, tmp_path, monkeypatch):
        _write_module(tmp_path, "pkg/mod.py")
        calls = _stub_run(monkeypatch, mutation, returncode=1)
        target = _target(mutation, paths=("pkg/mod.py",), tests=("tests/test_demo.py",))

        mutation.run_slice(target, repo_root=tmp_path, max_mutants=1)

        command = calls[0]["command"]
        assert "-B" in command
        assert "tests/test_demo.py" in command
        assert "-x" in command
        assert calls[0]["encoding"] == "utf-8"
        assert calls[0]["env"]["PYTHONDONTWRITEBYTECODE"] == "1"

    def test_test_command_lists_every_declared_test_path(self, mutation):
        target = _target(mutation, paths=("pkg/mod.py",), tests=("tests/a.py", "tests/b.py"))
        command = mutation.test_command(target, python_executable="python")
        assert command.count("tests/a.py") == 1
        assert command.count("tests/b.py") == 1


class TestWorktreeGate:
    """工作树前置：脏即拒跑（否则还原会把用户未提交的编辑一起写掉）。"""

    def test_dirty_paths_reports_changed_lines(self, mutation, monkeypatch):
        completed = subprocess.CompletedProcess(args=["git"], returncode=0, stdout=" M pkg/mod.py\n", stderr="")
        monkeypatch.setattr(mutation.subprocess, "run", lambda *_args, **_kwargs: completed)
        assert mutation.dirty_paths(("pkg/mod.py",)) == (" M pkg/mod.py",)

    def test_dirty_paths_is_empty_when_worktree_is_clean(self, mutation, monkeypatch):
        completed = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
        monkeypatch.setattr(mutation.subprocess, "run", lambda *_args, **_kwargs: completed)
        assert mutation.dirty_paths(("pkg/mod.py",)) == ()

    def test_mutation_paths_covers_sources_and_tests(self, mutation):
        target = _target(mutation, paths=("pkg/mod.py",), tests=("tests/test_demo.py",))
        paths = mutation.mutation_paths([target])
        assert "pkg/mod.py" in paths
        assert "tests/test_demo.py" in paths


class TestCollection:
    """切片文件枚举与不可解析源码的处理。"""

    def test_glob_paths_expand_to_real_source_files_only(self, mutation, tmp_path):
        _write_module(tmp_path, "pkg/one.py")
        _write_module(tmp_path, "pkg/two.py")
        (tmp_path / "pkg" / "notes.txt").write_text("不是源码", encoding="utf-8")
        mutants, notes = mutation.collect_mutants(_target(mutation, paths=("pkg/*.py",)), repo_root=tmp_path)
        assert notes == []
        assert {mutant.path for mutant in mutants} == {"pkg/one.py", "pkg/two.py"}

    def test_unparsable_file_is_skipped_with_a_note(self, mutation, tmp_path):
        _write_module(tmp_path, "pkg/mod.py")
        _write_module(tmp_path, "pkg/broken.py", source="def f(:\n    pass\n")
        mutants, notes = mutation.collect_mutants(
            _target(mutation, paths=("pkg/*.py",)),
            repo_root=tmp_path,
        )
        assert mutants  # 好文件照常产出变异体
        assert any("broken.py" in note and "无法解析" in note for note in notes)


class TestTerminationGuard:
    """被 SIGTERM/kill 结束时也要还原：`atexit` 对 SIGTERM 不生效，只靠它会留下变异版源码。

    白盒用例：直接驱动 `_eval_mutation.runner` 的备份登记表与信号处理器（安全性兜底本身
    就是被测对象，包装成黑盒反而验不到「信号路径真的会还原」）。
    """

    def test_signal_handler_restores_mutated_source_and_exits(self, mutation, tmp_path, monkeypatch):
        from _eval_mutation import runner as runner_module

        path = _write_module(tmp_path, "pkg/mod.py")
        original = path.read_bytes()
        installed: list[tuple[int, object]] = []
        monkeypatch.setattr(runner_module.signal, "signal", lambda signum, handler: installed.append((signum, handler)))
        monkeypatch.setattr(runner_module, "_TERMINATION_GUARD_INSTALLED", False)
        runner_module.install_termination_guard()

        assert installed
        assert installed[0][0] == runner_module.signal.SIGTERM
        handler = installed[0][1]
        runner_module._REGISTRY.register(path, original)
        path.write_bytes("def f(:\n".encode())  # 模拟「变异已落盘、进程此刻被强杀」
        with pytest.raises(SystemExit):
            handler(runner_module.signal.SIGTERM, None)  # type: ignore[operator]
        assert path.read_bytes() == original

    def test_run_slice_installs_the_guard(self, mutation, tmp_path, monkeypatch):
        from _eval_mutation import runner as runner_module

        _write_module(tmp_path, "pkg/mod.py")
        _stub_run(monkeypatch, mutation, returncode=1)
        installed: list[int] = []
        monkeypatch.setattr(runner_module.signal, "signal", lambda signum, handler: installed.append(signum))
        monkeypatch.setattr(runner_module, "_TERMINATION_GUARD_INSTALLED", False)

        mutation.run_slice(_target(mutation, paths=("pkg/mod.py",)), repo_root=tmp_path, max_mutants=1)

        assert runner_module.signal.SIGTERM in installed
