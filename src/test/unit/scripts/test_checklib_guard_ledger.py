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
