"""`probe-release-ledger.py` / `probe-guard-hits.py` 的容错分支与输出分支。

覆盖：脏台账字段的容错、缺版本记录跳过、verbose 明细、空台账文案与 `--ci` 输出口径；
两个脚本都**不是门禁**，退出码只表达「台账可读与否」。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="release_mod")
def fixture_release_mod():
    return load_script("probe-release-ledger.py", module_name="probe_release_ledger_under_test")


@pytest.fixture(name="hits_mod")
def fixture_hits_mod():
    return load_script("probe-guard-hits.py", module_name="probe_guard_hits_branches_under_test")


def _write_ledger(path: Path, rows: list[dict], *, blank_line: bool = False) -> Path:
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    if blank_line:
        text = "\n" + text + "\n"
    path.write_text(text + "\n", encoding="utf-8")
    return path


class TestReleaseLedgerRobustness:
    """脏台账不打断汇总：非数值耗时记 0、缺版本记录跳过、缺 usage 记录无 token 增量。"""

    def test_non_numeric_elapsed_counts_as_zero(self, release_mod):
        assert release_mod._as_float("n/a") == 0.0
        assert release_mod._as_float(3) == 3.0

    def test_session_total_requires_numeric_total_and_str_session(self, release_mod):
        record = {"session_usage": {"total": "x"}, "agent": {"session_id": "s"}}
        assert release_mod._session_total(record) is None
        assert release_mod._session_total({"session_usage": None}) is None

    def test_records_without_version_are_skipped(self, release_mod):
        assert release_mod.summarize([{"command": "check", "elapsed_s": 1.0}]) == []

    def test_token_delta_accumulates_per_session(self, release_mod):
        records = [
            {
                "version": "0.12.6-dev",
                "command": "check",
                "session_usage": {"total": 100},
                "agent": {"session_id": "a"},
            },
            {
                "version": "0.12.6",
                "command": "publish",
                "ok": True,
                "session_usage": {"total": 160},
                "agent": {"session_id": "a"},
            },
        ]
        summary = release_mod.summarize(records)
        assert [item["version"] for item in summary] == ["0.12.6"]
        # 新会话首行只记基线（增量 0），故本版 token = 第二行相对第一行的差
        assert summary[0]["tokens"] == 60
        assert summary[0]["published"] is True


class TestReleaseLedgerCli:
    """CLI 输出分支：verbose 明细行、空台账文案、`--ci` 静默说明段。"""

    @staticmethod
    def _rows() -> list[dict]:
        return [
            {
                "version": "0.12.6-dev",
                "command": "prepare",
                "ok": False,
                "elapsed_s": 12.0,
                "ts": "2026-10-01T10:00:00",
                "steps": [{"step": "archive", "elapsed_s": 5.0}],
                "failure": {"step": "archive", "rc": 2},
                "session_usage": {"total": 10},
                "agent": {"session_id": "a"},
            }
        ]

    def test_verbose_prints_per_command_and_step_detail(self, release_mod, tmp_path: Path, capsys):
        ledger = _write_ledger(tmp_path / "release.jsonl", self._rows())
        assert release_mod.main(["--ledger", str(ledger), "-v"]) == 0
        out = capsys.readouterr().out
        assert "prepare" in out
        assert "archive: 5.00s" in out

    def test_empty_ledger_is_not_a_failure(self, release_mod, tmp_path: Path, capsys):
        ledger = tmp_path / "empty.jsonl"
        ledger.write_text("", encoding="utf-8")
        assert release_mod.main(["--ledger", str(ledger)]) == 0
        assert "没有可汇总的发布记录" in capsys.readouterr().out

    def test_empty_ledger_ci_prints_nothing(self, release_mod, tmp_path: Path, capsys):
        ledger = tmp_path / "empty.jsonl"
        ledger.write_text("", encoding="utf-8")
        assert release_mod.main(["--ledger", str(ledger), "--ci"]) == 0
        assert capsys.readouterr().out.strip() == ""

    def test_unreadable_ledger_exits_one(self, release_mod, tmp_path: Path, monkeypatch, capsys):
        def _boom(path):
            raise OSError("权限不足")

        monkeypatch.setattr(release_mod, "_read_ledger", _boom)
        assert release_mod.main(["--ledger", str(tmp_path / "x.jsonl")]) == 1
        assert "台账不可读" in capsys.readouterr().err


class TestGuardHitsCli:
    """守护命中统计：空行忽略、空台账提示、非空台账给出降频建议。"""

    def test_blank_lines_are_ignored(self, hits_mod, tmp_path: Path):
        ledger = _write_ledger(
            tmp_path / "guard-hits.jsonl", [{"script": "check-a.py", "findings": 0}], blank_line=True
        )
        records, broken = hits_mod._load(ledger)
        assert (len(records), broken) == (1, 0)

    def test_broken_lines_are_counted(self, hits_mod, tmp_path: Path):
        ledger = tmp_path / "guard-hits.jsonl"
        ledger.write_text("{ bad json\n", encoding="utf-8")
        assert hits_mod._load(ledger) == ([], 1)

    def test_empty_ledger_prints_hint(self, hits_mod, tmp_path: Path, monkeypatch, capsys):
        ledger = tmp_path / "guard-hits.jsonl"
        ledger.write_text("", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["probe-guard-hits.py", "--ledger", str(ledger)])
        with pytest.raises(SystemExit) as excinfo:
            hits_mod.main()
        assert excinfo.value.code == 0
        assert "台账暂无记录" in capsys.readouterr().out

    def test_downgrade_advice_lists_clean_rules(self, hits_mod, tmp_path: Path, monkeypatch, capsys):
        ledger = _write_ledger(
            tmp_path / "guard-hits.jsonl",
            [{"script": "check-a.py", "findings": 0}] * 2,
        )
        monkeypatch.setattr(
            sys,
            "argv",
            ["probe-guard-hits.py", "--ledger", str(ledger), "--min-runs", "1"],
        )
        with pytest.raises(SystemExit) as excinfo:
            hits_mod.main()
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert "建议降频 1 项：check-a.py" in out
        assert "共 2 次运行记录" in out
