"""守护命中统计（`scripts/probe-guard-hits.py`）——台账聚合与处置建议口径。

本工具不是门禁：它的价值在于把「哪项守护真拦过东西」变成可读读数。用例锁：
  - 脚本级聚合（运行次数 / 命中次数 / finding 总数）与子项级（`details`）明细；
  - 处置三态（保留 / 建议降频 / 样本不足）的判据；
  - 台账缺失与损坏行的容错（首次使用不该报错，坏行只计数）。
"""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_PROBE = "probe-guard-hits.py"


def _probe_module():
    from src.test._script_loader import load_script

    return load_script(_PROBE, module_name="probe_guard_hits")


def _record(script: str, findings: int, details: dict | None = None) -> dict:
    return {"script": script, "findings": findings, "details": details or {}}


class TestLoading:
    def test_missing_ledger_is_treated_as_empty(self, tmp_path):
        module = _probe_module()
        records, broken = module._load(tmp_path / "absent.jsonl")
        assert records == []
        assert broken == 0

    def test_broken_lines_are_counted_not_fatal(self, tmp_path):
        module = _probe_module()
        ledger = tmp_path / "hits.jsonl"
        ledger.write_text(json.dumps(_record("check-a.py", 0)) + "\n{不是 json}\n[1,2]\n", encoding="utf-8")
        records, broken = module._load(ledger)
        assert len(records) == 1
        assert broken == 2


class TestSummarize:
    def test_script_level_counts(self):
        module = _probe_module()
        summary = module.summarize([_record("check-a.py", 0), _record("check-a.py", 3), _record("check-a.py", 1)])
        (row,) = summary["scripts"]
        assert row["runs"] == 3
        assert row["hits"] == 2
        assert row["findings"] == 4
        assert row["dispose"] == module._KEEP

    def test_disposition_follows_run_threshold(self):
        module = _probe_module()
        few = module.summarize([_record("check-x.py", 0)] * 2, min_runs=5)
        enough = module.summarize([_record("check-x.py", 0)] * 5, min_runs=5)
        assert few["scripts"][0]["dispose"] == module._NEED_MORE
        assert enough["scripts"][0]["dispose"] == module._DOWNGRADE

    def test_details_are_aggregated_per_item(self):
        module = _probe_module()
        summary = module.summarize(
            [
                _record("check-doc-drift.py", 2, {"check_dir_tree": 2, "check_switch_table": 0}),
                _record("check-doc-drift.py", 0, {"check_dir_tree": 0, "check_switch_table": 0}),
            ]
        )
        items = {row["name"]: row for row in summary["items"]}
        assert items["check_dir_tree"]["runs"] == 2
        assert items["check_dir_tree"]["hits"] == 1
        assert items["check_switch_table"]["hits"] == 0
        assert items["check_dir_tree"]["script"] == "check-doc-drift.py"

    def test_sorted_by_hits_then_runs(self):
        module = _probe_module()
        summary = module.summarize(
            [_record("never.py", 0)] * 5 + [_record("hitter.py", 1)] + [_record("busy.py", 0)] * 6
        )
        assert [row["name"] for row in summary["scripts"]][0] == "hitter.py"


class TestTableAndCli:
    def test_table_has_header_and_rows(self):
        module = _probe_module()
        summary = module.summarize([_record("check-a.py", 1, {"check_x": 1})])
        lines = module.format_table(summary, verbose=True)
        assert lines[0].startswith("守护脚本")
        assert any("check-a.py" in line for line in lines)
        assert any(line.startswith("check_x") for line in lines)

    def test_cli_prints_table_and_exits_zero(self, tmp_path, monkeypatch, capsys):
        module = _probe_module()
        ledger = tmp_path / "hits.jsonl"
        ledger.write_text(json.dumps(_record("check-a.py", 0)) + "\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", [_PROBE, "--ledger", str(ledger), "--ci"])
        with pytest.raises(SystemExit) as excinfo:
            module.main()
        assert excinfo.value.code == 0
        assert "check-a.py" in capsys.readouterr().out

    def test_unreadable_ledger_exits_one(self, tmp_path, monkeypatch, capsys):
        """台账路径是目录（读取必失败）→ 退出码 1，与「没有记录」区分。"""
        module = _probe_module()
        monkeypatch.setattr("sys.argv", [_PROBE, "--ledger", str(tmp_path)])
        with pytest.raises(SystemExit) as excinfo:
            module.main()
        assert excinfo.value.code == 1
        assert "台账不可读" in capsys.readouterr().out
