"""测试：`scripts/_probes/sector_flow.py` — 行业资金流向双通道探测（取数层注入，不联网）。

覆盖：
  - `build_parser`：`--count` 缺省取探测次数、可覆盖
  - `_probe_channel`：成功/空榜/通道不可用/未知异常四类描述与计数
  - `run`：判读 A（主通道可用）/ B（备用顶上）/ C（全受限）三条结论与退出码，
    `--count` 非法值（0 / 缺省）归一
"""

from __future__ import annotations

import argparse

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="probe")
def fixture_probe():
    return load_script("_probes/sector_flow.py", module_name="_probes_sector_flow_under_test")


@pytest.fixture(name="extras")
def fixture_extras(probe, monkeypatch):
    """把 `run()` 内 `from src.python.providers import akshare_extras` 的三个注册表换成替身。"""
    from src.python.providers import akshare_extras

    channels = ("主通道", "备用通道")
    fetchers: dict[str, object] = {}
    monkeypatch.setattr(akshare_extras, "_SECTOR_FLOW_CHANNELS", channels)
    monkeypatch.setattr(akshare_extras, "_SECTOR_FLOW_CHANNEL_LABELS", {"主通道": "东财 push2"})
    monkeypatch.setattr(akshare_extras, "_SECTOR_FLOW_FETCHERS", fetchers)
    return fetchers


def _rows(count: int) -> list[dict[str, object]]:
    return [{"name": f"行业{i}"} for i in range(count)]


class TestBuildParser:
    def test_default_count_from_probe_budget(self, probe):
        args = probe.build_parser().parse_args([])
        assert args.count == probe._PROBES

    def test_explicit_count_overrides(self, probe):
        assert probe.build_parser().parse_args(["--count", "3"]).count == 3

    def test_invalid_count_rejected(self, probe):
        with pytest.raises(SystemExit) as excinfo:
            probe.build_parser().parse_args(["--count", "many"])
        assert excinfo.value.code == 2, "参数错误按 argparse 契约退出 2"


class TestProbeChannel:
    def test_counts_success_and_reports_row_total(self, probe):
        ok, detail = probe._probe_channel("主通道", lambda: _rows(4), 2)
        assert ok == 2
        assert all("行业数=4" in line for line in detail)

    def test_empty_board_not_counted(self, probe):
        ok, detail = probe._probe_channel("主通道", lambda: [], 1)
        assert ok == 0
        assert "空榜" in detail[0]

    def test_unavailable_reports_kind(self, probe):
        from src.python.providers.akshare_extras import _SectorFlowUnavailable

        def _raise():
            raise _SectorFlowUnavailable("connection", "主通道")

        ok, detail = probe._probe_channel("主通道", _raise, 1)
        assert ok == 0
        assert "不可用" in detail[0] and "connection" in detail[0]

    def test_unexpected_exception_reports_type_and_message(self, probe):
        def _raise():
            raise ValueError("接口改了字段")

        ok, detail = probe._probe_channel("主通道", _raise, 1)
        assert ok == 0
        assert "ValueError" in detail[0] and "接口改了字段" in detail[0]


class TestRunVerdicts:
    """三条判读结论：主通道可用（0）／备用顶上（0）／全受限（1）。"""

    def test_primary_available_needs_no_backup(self, probe, extras, capsys):
        extras["主通道"] = lambda: _rows(3)
        extras["备用通道"] = lambda: []
        assert probe.run(argparse.Namespace(count=2)) == 0
        out = capsys.readouterr().out
        assert "行业资金流向通道探测" in out
        assert "东财 push2" in out, "未登记标签的通道回落到通道名"
        assert "备用通道" in out, "未登记标签时显示原名"
        assert "无需备用通道介入" in out
        assert "成功率: 2/2" in out

    def test_backup_channel_carries_when_primary_limited(self, probe, extras, capsys):
        extras["主通道"] = lambda: []
        extras["备用通道"] = lambda: _rows(2)
        assert probe.run(argparse.Namespace(count=2)) == 0
        out = capsys.readouterr().out
        assert "备用通道可用" in out
        assert "东财 push2: 0/2" in out

    def test_all_channels_limited_exits_one(self, probe, extras, capsys):
        extras["主通道"] = lambda: []
        extras["备用通道"] = lambda: []
        assert probe.run(argparse.Namespace(count=2)) == 1
        out = capsys.readouterr().out
        assert "全部通道均受限" in out
        assert "勿改代码" in out

    def test_zero_count_falls_back_to_probe_budget(self, probe, extras):
        calls: list[int] = []

        def _fetch():
            calls.append(1)
            return _rows(1)

        extras["主通道"] = _fetch
        extras["备用通道"] = _fetch
        assert probe.run(argparse.Namespace(count=0)) == 0
        assert len(calls) == 2 * probe._PROBES, "count=0 视为未指定，取每通道探测次数"

    def test_negative_count_normalised_to_single_probe(self, probe, extras):
        calls: list[int] = []

        def _fetch():
            calls.append(1)
            return _rows(1)

        extras["主通道"] = _fetch
        extras["备用通道"] = _fetch
        assert probe.run(argparse.Namespace(count=-5)) == 0
        assert len(calls) == 2, "负值归一为每通道 1 次"
