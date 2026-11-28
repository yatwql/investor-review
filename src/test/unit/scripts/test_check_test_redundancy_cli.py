"""check-test-redundancy.py 的 CLI 入口：参数面、汇总打印与退出码契约。

覆盖 `main()` 的四条输出分支（`-v` 统计行、`--audit` 骨架审计、`--audit-all`
文件内组、`--ci` 裸 finding），`sys.exit(report(...))` 的 0/2 退出码，
以及 `scripts/` 不在 sys.path 时的导入期补路径分支。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import SCRIPTS_DIR, load_module_file, load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_STATS = {
    "files": 3,
    "cases": 7,
    "dead": 0,
    "assertion_free": 0,
    "duplicate": 0,
    "self_fulfilling": 0,
    "hardcoded_totals": 0,
    "trivial": 0,
    "dead_fixtures": 0,
    "weak_mock": 0,
    "date_bombs": 0,
    "markers": 0,
    "patch_surface": 0,
    "duplicate_skipped": 0,
}
_AUDIT_STATS = {"groups": 0, "intra_groups_total": 0}


@pytest.fixture(name="redundancy")
def fixture_redundancy(monkeypatch):
    """加载脚本并把 `run_checks` / `audit_similar_bodies` 换成可控桩。"""
    mod = load_script("check-test-redundancy.py")
    monkeypatch.setattr(
        mod, "run_checks", lambda include_live=False: ([], dict(_STATS, files=4 if include_live else 3))
    )
    monkeypatch.setattr(
        mod,
        "audit_similar_bodies",
        lambda include_live=False, include_intra=False: ([], dict(_AUDIT_STATS, groups=1, intra_groups_total=2)),
    )
    return mod


def _run(mod, monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["check-test-redundancy.py", *argv])
    with pytest.raises(SystemExit) as excinfo:
        mod.main()
    return int(excinfo.value.code)


class TestExitCodes:
    def test_clean_run_exits_zero(self, redundancy, monkeypatch, capsys):
        assert _run(redundancy, monkeypatch) == 0
        assert "[OK]" in capsys.readouterr().out

    def test_findings_exit_two_as_error_lines(self, redundancy, monkeypatch, capsys):
        monkeypatch.setattr(redundancy, "run_checks", lambda include_live=False: (["死用例 a.py:1"], dict(_STATS)))
        assert _run(redundancy, monkeypatch) == 2
        out = capsys.readouterr().out
        assert "[ERR] 死用例 a.py:1" in out
        assert "须修正后提交" in out

    def test_ci_mode_prints_bare_finding(self, redundancy, monkeypatch, capsys):
        monkeypatch.setattr(redundancy, "run_checks", lambda include_live=False: (["死用例 a.py:1"], dict(_STATS)))
        assert _run(redundancy, monkeypatch, "--ci") == 2
        out = capsys.readouterr().out
        assert "死用例 a.py:1" in out
        assert "[ERR]" not in out


class TestOutputBranches:
    def test_verbose_prints_scan_counts(self, redundancy, monkeypatch, capsys):
        assert _run(redundancy, monkeypatch, "-v") == 0
        out = capsys.readouterr().out
        assert "扫描测试文件 3 个" in out
        assert "live 目录跳过" in out
        assert "因不可解析的 self 间接调用而跳过重复比对" in out

    def test_verbose_marks_include_live(self, redundancy, monkeypatch, capsys):
        assert _run(redundancy, monkeypatch, "-v", "--include-live") == 0
        out = capsys.readouterr().out
        assert "扫描测试文件 4 个" in out
        assert "live 目录纳入" in out

    def test_audit_prints_group_count_and_hint(self, redundancy, monkeypatch, capsys):
        assert _run(redundancy, monkeypatch, "--audit") == 0
        out = capsys.readouterr().out
        assert "骨架审计" in out
        assert "文件内组 2 未列，--audit-all 可显示" in out

    def test_audit_does_not_change_exit_code(self, redundancy, monkeypatch):
        monkeypatch.setattr(
            redundancy,
            "audit_similar_bodies",
            lambda include_live=False, include_intra=False: (["同构组 x/y"], dict(_AUDIT_STATS, groups=1)),
        )
        assert _run(redundancy, monkeypatch, "--audit") == 0

    def test_audit_all_suppresses_hidden_hint(self, redundancy, monkeypatch, capsys):
        assert _run(redundancy, monkeypatch, "--audit", "--audit-all") == 0
        assert "未列" not in capsys.readouterr().out


class TestScriptsPathBootstrap:
    def test_scripts_dir_is_prepended_when_absent(self, monkeypatch):
        scripts = str(SCRIPTS_DIR)
        monkeypatch.setattr(sys, "path", [p for p in sys.path if p != scripts])
        load_module_file(SCRIPTS_DIR / "check-test-redundancy.py", "check_test_redundancy_bootstrap_probe")
        assert sys.path[0] == scripts
