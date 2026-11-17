"""守护命中台账（`scripts/_shared/checklib.record_guard_run`）——记录形态与失败静默。

台账是 `probe-guard-hits.py` 的唯一读数源，但它绝不能影响检查结论：写入失败必须
静默（返回 None + 不抛），路径可用环境变量覆盖（测试/CI 隔离）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


def _load_checklib():
    """按文件路径单独载入一份 checklib（避免与被其它用例改过状态的共享实例串扰）。"""
    from src.test._script_loader import load_script

    return load_script("_shared/checklib.py", module_name="checklib_probe")


class TestRecordGuardRun:
    def test_appends_one_json_line_with_details(self, tmp_path, monkeypatch):
        fresh = _load_checklib()
        ledger = tmp_path / "hits.jsonl"
        monkeypatch.setenv("INVEST_GUARD_HITS_LEDGER", str(ledger))
        fresh.record_guard_run(2, {"check_x": 2})
        record = json.loads(ledger.read_text(encoding="utf-8").strip())
        assert record["findings"] == 2
        assert record["details"] == {"check_x": 2}
        assert record["script"]

    def test_default_details_is_empty_mapping(self, tmp_path, monkeypatch):
        fresh = _load_checklib()
        ledger = tmp_path / "hits.jsonl"
        monkeypatch.setenv("INVEST_GUARD_HITS_LEDGER", str(ledger))
        fresh.record_guard_run(0)
        record = json.loads(ledger.read_text(encoding="utf-8").strip())
        assert record["details"] == {}
        assert record["findings"] == 0

    def test_write_failure_is_silent(self, monkeypatch):
        """台账路径不可写（此处为目录）→ 静默返回，不抛、不影响退出码。"""
        fresh = _load_checklib()
        monkeypatch.setenv("INVEST_GUARD_HITS_LEDGER", str(Path(__file__).resolve().parent))
        assert fresh.record_guard_run(1) is None

    def test_report_records_run_and_keeps_exit_semantics(self, tmp_path, monkeypatch, capsys):
        fresh = _load_checklib()
        ledger = tmp_path / "hits.jsonl"
        monkeypatch.setenv("INVEST_GUARD_HITS_LEDGER", str(ledger))
        assert fresh.report(["file:desc"], "[OK] 通过", ci=True) == 2
        assert fresh.report([], "[OK] 通过", ci=True) == 0
        lines = ledger.read_text(encoding="utf-8").splitlines()
        assert [json.loads(line)["findings"] for line in lines] == [1, 0]
        assert "file:desc" in capsys.readouterr().out


class TestLedgerGrowth:
    def test_oversized_ledger_is_trimmed_keeping_recent_lines(self, tmp_path, monkeypatch):
        """台账超过体积上限 → 只保留最近 `_GUARD_HITS_KEEP_LINES` 行（防无界增长）。"""
        fresh = _load_checklib()
        ledger = tmp_path / "hits.jsonl"
        ledger.write_text(
            "".join(json.dumps({"script": f"old-{i}", "findings": 0}) + "\n" for i in range(50)), encoding="utf-8"
        )
        monkeypatch.setenv("INVEST_GUARD_HITS_LEDGER", str(ledger))
        monkeypatch.setattr(fresh, "_GUARD_HITS_MAX_BYTES", 1)
        monkeypatch.setattr(fresh, "_GUARD_HITS_KEEP_LINES", 5)

        fresh.record_guard_run(0)

        lines = ledger.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 6, "最近 5 行 + 本次追加"
        assert json.loads(lines[-1])["findings"] == 0
        assert not ledger.with_name(ledger.name + ".tmp").exists(), "临时文件不得残留"

    def test_small_ledger_is_appended_not_rewritten(self, tmp_path, monkeypatch):
        fresh = _load_checklib()
        ledger = tmp_path / "hits.jsonl"
        ledger.write_text(json.dumps({"script": "a", "findings": 0}) + "\n", encoding="utf-8")
        monkeypatch.setenv("INVEST_GUARD_HITS_LEDGER", str(ledger))
        fresh.record_guard_run(3)
        assert len(ledger.read_text(encoding="utf-8").splitlines()) == 2
