"""`check-types.py` 的解析器定位与 `--changed` 快车道分支。

契约：pyright 定位顺序 PATH → 虚拟环境 → npx，三者皆无为环境缺失（退出 1）；
`--changed` 拿不到 git 清单时回落全量（宁可慢，不漏检）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod():
    return load_script("check-types.py", module_name="check_types_branches_under_test")


class TestPyrightLocation:
    """定位链与「环境缺失」退出码。"""

    def test_venv_pyright_is_used_when_path_has_none(self, mod, monkeypatch, tmp_path: Path):
        exe = tmp_path / "pyright"
        exe.write_text("#!/bin/sh\n", encoding="utf-8")
        monkeypatch.setattr(mod.sys, "executable", str(tmp_path / "python"))
        monkeypatch.setattr(mod.shutil, "which", lambda name: None)
        assert mod.venv_pyright_path() == exe
        assert mod.pyright_command() == [str(exe)]

    def test_npx_is_last_resort(self, mod, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(mod.sys, "executable", str(tmp_path / "python"))
        monkeypatch.setattr(mod.shutil, "which", lambda name: "/usr/bin/npx" if name == "npx" else None)
        assert mod.pyright_command() == ["/usr/bin/npx", "--no-install", "pyright"]

    def test_missing_environment_exits_one(self, mod, monkeypatch, tmp_path: Path, capsys):
        monkeypatch.setattr(mod.sys, "executable", str(tmp_path / "python"))
        monkeypatch.setattr(mod.shutil, "which", lambda name: None)
        assert mod.main([]) == 1
        assert "类型检查不可用" in capsys.readouterr().err


class TestChangedFastLane:
    """`--changed` 的回落语义。"""

    def test_git_failure_returns_none(self, mod, monkeypatch):
        def _boom(*args, **kwargs):
            raise OSError("git 不可用")

        monkeypatch.setattr(mod.subprocess, "run", _boom)
        assert mod.changed_guarded_files() is None

    def test_non_zero_git_status_returns_none(self, mod, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess,
            "run",
            lambda *a, **k: subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal"),
        )
        assert mod.changed_guarded_files() is None

    def test_only_guarded_python_files_are_kept(self, mod, monkeypatch):
        stdout = "src/python/core/a.py\nscripts/b.py\ndocs/c.md\nsrc/test/d.py\n"

        def _fake_run(cmd, **kwargs):
            first = "ls-files" not in cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=stdout if first else "", stderr="")

        monkeypatch.setattr(mod.subprocess, "run", _fake_run)
        assert mod.changed_guarded_files() == ["scripts/b.py", "src/python/core/a.py"]

    def test_git_unavailable_falls_back_to_full_scan(self, mod, monkeypatch):
        seen: dict = {}
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(mod, "changed_guarded_files", lambda: None)

        def _capture(cmd, targets, **kwargs):
            seen["targets"] = targets
            return {"generalDiagnostics": []}

        monkeypatch.setattr(mod, "run_pyright", _capture)
        assert mod.main(["--changed"]) == 0
        assert seen["targets"] == list(mod.DEFAULT_TARGETS)

    def test_changed_files_become_the_targets(self, mod, monkeypatch):
        seen: dict = {}
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(mod, "changed_guarded_files", lambda: ["scripts/a.py"])

        def _capture(cmd, targets, **kwargs):
            seen["targets"] = targets
            return {"generalDiagnostics": []}

        monkeypatch.setattr(mod, "run_pyright", _capture)
        assert mod.main(["--changed"]) == 0
        assert seen["targets"] == ["scripts/a.py"]

    def test_no_changed_files_skips_check(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(mod, "changed_guarded_files", lambda: [])
        assert mod.main(["--changed", "-v"]) == 0
        captured = capsys.readouterr()
        assert "无落在守护域内的变更文件" in captured.out

    def test_too_many_changed_files_falls_back_to_full_scan(self, mod, monkeypatch):
        many = [f"scripts/gen{i}.py" for i in range(mod.MAX_CHANGED_FILES + 1)]
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(mod, "changed_guarded_files", lambda: many)
        monkeypatch.setattr(mod, "run_pyright", lambda cmd, targets: {"generalDiagnostics": []})
        seen: dict = {}

        def _capture(cmd, targets, **kwargs):
            seen["targets"] = targets
            return {"generalDiagnostics": []}

        monkeypatch.setattr(mod, "run_pyright", _capture)
        assert mod.main(["--changed"]) == 0
        assert seen["targets"] == list(mod.DEFAULT_TARGETS)


class TestReportBranches:
    """报告解析与输出分支。"""

    def test_unparsable_output_is_environment_failure(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(mod, "run_pyright", lambda cmd, targets: None)
        assert mod.main([]) == 1
        assert "未能取得 JSON 报告" in capsys.readouterr().err

    def test_verbose_pass_prints_diagnostics_summary(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(
            mod,
            "run_pyright",
            lambda cmd, targets: {
                "generalDiagnostics": [],
                "summary": {"errorCount": 0, "warningCount": 3},
            },
        )
        assert mod.main(["-v"]) == 0
        assert "0 error / 3 warning" in capsys.readouterr().out

    def test_verbose_reports_resolver_and_targets(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, "pyright_command", lambda: ["/usr/bin/pyright"])
        monkeypatch.setattr(mod, "run_pyright", lambda cmd, targets: {"generalDiagnostics": []})
        assert mod.main(["-v", "src/python/llm"]) == 0
        out = capsys.readouterr().out
        assert "解析器：/usr/bin/pyright" in out
        assert "受检目标：src/python/llm" in out

    def test_error_diagnostics_exit_two(self, mod, monkeypatch):
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(
            mod,
            "run_pyright",
            lambda cmd, targets: {
                "generalDiagnostics": [
                    {
                        "severity": "error",
                        "file": str(Path(mod.REPO_ROOT) / "scripts" / "x.py"),
                        "range": {"start": {"line": 4, "character": 2}},
                        "rule": "reportUndefinedVariable",
                        "message": "未定义\n次行",
                    }
                ]
            },
        )
        assert mod.main(["--ci"]) == 2

    def test_long_finding_list_is_truncated(self, mod, monkeypatch, capsys):
        diagnostics = [
            {
                "severity": "error",
                "file": str(Path(mod.REPO_ROOT) / "scripts" / f"m{i}.py"),
                "range": {"start": {"line": i, "character": 0}},
                "rule": "error",
                "message": "坏",
            }
            for i in range(mod.MAX_REPORTED + 5)
        ]
        monkeypatch.setattr(mod, "pyright_command", lambda: ["pyright"])
        monkeypatch.setattr(mod, "run_pyright", lambda cmd, targets: {"generalDiagnostics": diagnostics})
        assert mod.main([]) == 2
        assert "其余 5 条已省略" in capsys.readouterr().out
