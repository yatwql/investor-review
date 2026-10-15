"""full 路径 HTML/Excel 阶段埋点回归测试。

回归场景：full 路径的 HTML/Excel 写出经 `_report_output.py` 两个 helper 完成，
而阶段计时只存在于 `_report_generation.py` 的 both 路径——full 运行因此**丢失**
`HTML 生成`/`Excel 生成` 两个阶段（实测 126 条历史记录中二者各仅 6 条，均早期版本），
渲染耗时对统计不可见。此处锁定「helper 内确实补了阶段计时」。

运行：
  pytest src/test/unit/report/test_report_output_spans.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import src.python.report._report_generation as rg
from src.python.report.orchestrator import ReportResult

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _RecordingPerf:
    """PerfCollector 替身：记录 start/stop 调用序列。"""

    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self, phase_name: str) -> None:
        self.events.append(f"start:{phase_name}")

    def stop(self) -> None:
        self.events.append("stop")


@pytest.fixture(name="prep_stub")
def fixture_prep_stub(tmp_path):
    return {
        "output_dir": str(tmp_path),
        "news_top_count": 10,
        "details": [],
        "a_indices": {},
        "us_indices": {},
    }


def _bind(monkeypatch, perf) -> None:
    """把替身 collector 绑到运行上下文（helper 经 current_perf() 取用）。"""
    import src.python.report.run_integrity as ri

    monkeypatch.setattr(ri, "current_perf", lambda: perf)


class TestFullPathPhaseSpans:
    """两个 helper 各自补阶段计时，且异常路径也收口（finally）。"""

    def test_html_helper_records_phase(self, monkeypatch, tmp_path, prep_stub):
        perf = _RecordingPerf()
        _bind(monkeypatch, perf)
        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda *a, **k: False)
        monkeypatch.setattr(rg, "_build_chart_datasets_for_report", lambda *a, **k: {})
        monkeypatch.setattr(
            "src.python.report.html_writer.write_html_report",
            lambda *a, **k: str(tmp_path / "report.html"),
        )

        ok = rg._generate_full_html_report(
            [],
            prep_stub,
            str(tmp_path),
            [],
            (None, None, None, None),
            [],
            {},
            True,
            None,
            MagicMock(),
            False,
            False,
            False,
            False,
            None,
            ReportResult(),
        )

        assert ok is True
        assert perf.events == ["start:HTML 生成", "stop"]

    def test_excel_helper_records_phase(self, monkeypatch, tmp_path, prep_stub):
        perf = _RecordingPerf()
        _bind(monkeypatch, perf)
        monkeypatch.setattr(
            "src.python.report.excel_generator.generate_excel_report",
            lambda *a, **k: None,
        )

        ok = rg._generate_full_excel_report(
            [],
            prep_stub,
            str(tmp_path),
            True,
            (None, None, None, None),
            [],
            {},
            [],
            None,
            None,
            MagicMock(),
            False,
            False,
            False,
            False,
            None,
            ReportResult(),
        )

        assert ok is True
        assert perf.events == ["start:Excel 生成", "stop"]

    def test_html_failure_still_closes_phase(self, monkeypatch, tmp_path, prep_stub):
        """渲染抛异常时阶段仍收口（finally），否则该阶段永久悬挂、后续计时错位。"""
        perf = _RecordingPerf()
        _bind(monkeypatch, perf)
        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda *a, **k: False)
        monkeypatch.setattr(rg, "_build_chart_datasets_for_report", lambda *a, **k: {})

        def _boom(*a, **k):
            raise RuntimeError("渲染失败")

        monkeypatch.setattr("src.python.report.html_writer.write_html_report", _boom)

        ok = rg._generate_full_html_report(
            [],
            prep_stub,
            str(tmp_path),
            [],
            (None, None, None, None),
            [],
            {},
            True,
            None,
            MagicMock(),
            False,
            False,
            False,
            False,
            None,
            ReportResult(),
        )

        assert ok is False
        assert perf.events == ["start:HTML 生成", "stop"]

    def test_no_run_context_skips_timing(self, monkeypatch, tmp_path, prep_stub):
        """无运行上下文（current_perf() 为 None）时零行为变化：不报错、照常产出。"""
        _bind(monkeypatch, None)
        monkeypatch.setattr(
            "src.python.report.excel_generator.generate_excel_report",
            lambda *a, **k: None,
        )

        ok = rg._generate_full_excel_report(
            [],
            prep_stub,
            str(tmp_path),
            True,
            (None, None, None, None),
            [],
            {},
            [],
            None,
            None,
            MagicMock(),
            False,
            False,
            False,
            False,
            None,
            ReportResult(),
        )

        assert ok is True
