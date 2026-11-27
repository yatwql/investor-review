"""测试：`_perf_history.cli.main` —— 参数解析 → 记录过滤 → 机读/Markdown 输出 → 存盘。

覆盖：
  - 空历史：提示并退出 1（不进过滤/渲染）
  - 机读输出：`--json` / `--csv` 各自把过滤结果与时段聚合交给 `_machine_readable`；
    机读模式下 `--save` 被拒绝（只告警，不写文件）
  - Markdown 输出：全部参数（报告类型/条数/离群剔除/时段聚合/版本对比/概览/离群系数/版本）
    原样透传给 `build_trend_report`，返回内容打印到 stdout
  - `--save`：报告写入目标路径并提示（路径重定向到 `tmp_path`）

`load_history` / `_filter_records` / `build_trend_report` / `_machine_readable` 全部打桩，
输出路径常量重定向到 `tmp_path`——不读真实 `data/state/perf_history.jsonl`，不写 `docs/tmp/`。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="cli")
def fixture_cli():
    """加载 `scripts/perf-history.py`（入口把 `scripts/` 载入）后取实现模块。"""
    load_script("perf-history.py", module_name="perf_history_entry_probe")
    from _perf_history import cli  # pyright: ignore[reportMissingImports]  # scripts/ 由 load_script 注入 sys.path

    return cli


class _CliHarness:
    """`main()` 协作件桩集合：记录过滤/渲染入参，可直接返回预设输出。"""

    def __init__(self, cli_module, monkeypatch, tmp_path) -> None:
        self.cli = cli_module
        self.records: list[dict] = [{"version": "0.1.0", "report_type": "full"}]
        self.scoped: list[dict] = [{"version": "0.1.0", "report_type": "full"}]
        self.calls: dict[str, object] = {}
        monkeypatch.setattr(cli_module, "load_history", self._load_history)
        monkeypatch.setattr(cli_module, "_filter_records", self._filter_records)
        monkeypatch.setattr(cli_module, "build_trend_report", self._build_trend_report)
        monkeypatch.setattr(cli_module, "_machine_readable", self._machine_readable)
        monkeypatch.setattr(cli_module, "_TMP_DIR", str(tmp_path))
        monkeypatch.setattr(cli_module, "_TREND_REPORT_PATH", str(tmp_path / "perf_trend.md"))

    def _load_history(self):
        return list(self.records)

    def _filter_records(self, records, report_type, last_n, exclude_outlier, outlier_k, version):
        self.calls["filter"] = {
            "records": list(records),
            "report_type": report_type,
            "last_n": last_n,
            "exclude_outlier": exclude_outlier,
            "outlier_k": outlier_k,
            "version": version,
        }
        return list(self.scoped)

    def _build_trend_report(self, records, **kwargs):
        self.calls["report"] = {"records": list(records), **kwargs}
        return "# trend report"

    def _machine_readable(self, scoped, fmt, outlier_k, by=None):
        self.calls["machine"] = {"scoped": list(scoped), "fmt": fmt, "outlier_k": outlier_k, "by": by}
        return f"machine:{fmt}"

    def run(self, argv: list[str], monkeypatch) -> int:
        monkeypatch.setattr(sys, "argv", ["perf-history.py", *argv])
        return self.cli.main()


@pytest.fixture(name="harness")
def fixture_harness(cli, monkeypatch, tmp_path):
    """`main()` 的协作件全部打桩，路径常量重定向到 `tmp_path`。"""
    return _CliHarness(cli, monkeypatch, tmp_path)


class TestEmptyHistory:
    def test_no_records_exits_one_with_hint(self, harness, monkeypatch, capsys):
        harness.records = []
        assert harness.run([], monkeypatch) == 1
        out = capsys.readouterr().out
        assert "暂无性能历史数据" in out
        assert "filter" not in harness.calls and "report" not in harness.calls


class TestMachineReadableOutput:
    def test_json_forwards_scoped_records(self, harness, monkeypatch, capsys):
        assert harness.run(["--json", "--by", "day", "--outlier-k", "4.5"], monkeypatch) == 0
        assert harness.calls["machine"] == {
            "scoped": harness.scoped,
            "fmt": "json",
            "outlier_k": 4.5,
            "by": "day",
        }
        assert "machine:json" in capsys.readouterr().out
        assert "report" not in harness.calls

    def test_csv_selects_csv_format(self, harness, monkeypatch, capsys):
        assert harness.run(["--csv"], monkeypatch) == 0
        assert harness.calls["machine"]["fmt"] == "csv"
        assert harness.calls["machine"]["by"] is None
        assert "machine:csv" in capsys.readouterr().out

    def test_save_rejected_in_machine_mode(self, harness, monkeypatch, capsys, tmp_path):
        assert harness.run(["--json", "--save"], monkeypatch) == 0
        captured = capsys.readouterr()
        assert "--save 在机读模式下不适用" in captured.err
        assert not (tmp_path / "perf_trend.md").exists()

    def test_json_wins_over_csv_when_both_given(self, harness, monkeypatch):
        assert harness.run(["--csv", "--json"], monkeypatch) == 0
        assert harness.calls["machine"]["fmt"] == "json"


class TestMarkdownOutput:
    def test_all_options_forwarded_to_renderer(self, harness, monkeypatch, capsys):
        code = harness.run(
            [
                "--report-type",
                "full",
                "--version",
                "0.13.4",
                "--last",
                "30",
                "--exclude-outlier",
                "--by",
                "week",
                "--compare",
                "0.13.3",
                "0.13.4",
                "--summary",
                "--outlier-k",
                "2.5",
            ],
            monkeypatch,
        )
        assert code == 0
        assert harness.calls["report"] == {
            "records": harness.records,
            "report_type": "full",
            "last_n": 30,
            "exclude_outlier": True,
            "by": "week",
            "compare": ("0.13.3", "0.13.4"),
            "summary": True,
            "outlier_k": 2.5,
            "version": "0.13.4",
        }
        assert harness.calls["filter"]["version"] == "0.13.4"
        assert harness.calls["filter"]["last_n"] == 30
        assert "machine" not in harness.calls
        assert "# trend report" in capsys.readouterr().out

    def test_compare_absent_passes_none(self, harness, monkeypatch):
        assert harness.run([], monkeypatch) == 0
        assert harness.calls["report"]["compare"] is None
        assert harness.calls["filter"]["outlier_k"] == harness.cli._OUTLIER_K

    def test_save_writes_report_and_reports_path(self, harness, monkeypatch, capsys, tmp_path):
        assert harness.run(["--save"], monkeypatch) == 0
        target = tmp_path / "perf_trend.md"
        assert target.read_text(encoding="utf-8") == "# trend report"
        assert f"[OK] 已写入: {target}" in capsys.readouterr().out
