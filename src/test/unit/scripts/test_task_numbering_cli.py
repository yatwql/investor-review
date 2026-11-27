"""check-task-numbering.py 的 CLI 入口与归档枚举分支。

覆盖 `main()` 的参数面（`--kind` / `--ci` / `-v`）、退出码契约
（0 = 全部通过，2 = 有违规）、编号源标记的详细输出分支，
以及 `_all_numbering_files()` 对归档目录的真实 glob 过滤与
`_max_number_in()` 跳过不可读文件的降级路径。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_PLAN_DOC = "> **编号源**：`plan-next = 12`\n\n## 待办\n\n- plan-9 已完成\n"
_RF_DOC = "> **编号源**：`rf-next = 8`\n\n## 待办\n\n- rf-6 已完成\n"


@pytest.fixture(name="numbering")
def fixture_numbering(tmp_path, monkeypatch):
    """加载脚本并把三处目录常量指到临时树（不读写真实管理文档）。"""
    mod = load_script("check-task-numbering.py")
    monkeypatch.setattr(mod, "MANAGEMENTS_DIR", tmp_path)
    monkeypatch.setattr(mod, "ARCHIVE_DIR", tmp_path / "archive")
    (tmp_path / "plan.md").write_text(_PLAN_DOC, encoding="utf-8")
    (tmp_path / "review-findings.md").write_text(_RF_DOC, encoding="utf-8")
    return mod


def _run(mod, monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["check-task-numbering.py", *argv])
    return mod.main()


class TestMainExitCodes:
    def test_all_kinds_pass_returns_zero(self, numbering, monkeypatch, capsys):
        assert _run(numbering, monkeypatch) == 0
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "全部编号序列通过" in out

    def test_ci_mode_passes_without_progress_line(self, numbering, monkeypatch, capsys):
        assert _run(numbering, monkeypatch, "--ci") == 0
        assert "[..]" not in capsys.readouterr().out

    def test_single_kind_restricts_scan(self, numbering, monkeypatch, capsys):
        seen: list[str] = []
        monkeypatch.setattr(numbering, "check_kind", lambda kind, ci_mode, verbose=False: seen.append(kind) or [])
        assert _run(numbering, monkeypatch, "--kind", "rf") == 0
        assert seen == ["rf"]

    def test_missing_marker_fails_with_two(self, numbering, monkeypatch, capsys):
        (numbering.MANAGEMENTS_DIR / "plan.md").write_text("无标记文档\n", encoding="utf-8")
        assert _run(numbering, monkeypatch, "--kind", "plan") == 2
        assert "缺少编号源标记" in capsys.readouterr().out

    def test_ci_mode_prints_bare_finding(self, numbering, monkeypatch, capsys):
        (numbering.MANAGEMENTS_DIR / "plan.md").write_text("无标记文档\n", encoding="utf-8")
        assert _run(numbering, monkeypatch, "--kind", "plan", "--ci") == 2
        out = capsys.readouterr().out
        assert "缺少编号源标记" in out
        assert "[ERR]" not in out


class TestVerboseOutput:
    def test_verbose_reports_marker_value(self, numbering, monkeypatch, capsys):
        assert _run(numbering, monkeypatch, "-v") == 0
        out = capsys.readouterr().out
        assert "plan-next = 12" in out
        assert "已用最大" in out

    def test_verbose_suppressed_in_ci_mode(self, numbering, monkeypatch, capsys):
        assert _run(numbering, monkeypatch, "-v", "--ci") == 0
        assert "已用最大" not in capsys.readouterr().out


class TestArchiveEnumeration:
    def test_only_plan_and_review_findings_archives(self, numbering, tmp_path):
        archive = tmp_path / "archive" / "v1"
        archive.mkdir(parents=True)
        for name in ("archived_plan.v1.md", "archived_review-findings.v1.md", "archived_changelog.v1.md"):
            (archive / name).write_text("x\n", encoding="utf-8")
        numbering.ARCHIVE_DIR = tmp_path / "archive"
        names = sorted(path.name for path in numbering._all_numbering_files())
        assert names == ["archived_plan.v1.md", "archived_review-findings.v1.md"]

    def test_unreadable_path_is_skipped(self, numbering, tmp_path):
        unreadable = tmp_path / "dir-as-file.md"
        unreadable.mkdir()
        readable = tmp_path / "plan.md"
        readable.write_text("plan-3\n", encoding="utf-8")
        assert numbering._max_number_in([unreadable, readable], r"plan-\d+") == 3
