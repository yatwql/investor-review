"""HTML 生成阶段的子步骤拆分（回归：整段只记一个「页面写入」无法定位慢在哪一步）。

现场：同一份 0.98MB 产物，阶段细分里「页面写入」在 0.02s / 6.15s / 21.0s 三档抖动，
而该段实际包含 模板渲染 → JS 资产内嵌 → 匿名化 → 落盘 IO 四件事，凭总值无法判断
是渲染慢、内嵌慢还是磁盘慢（本机手工写 1MB 实测 0.00s，不能凭总值归因磁盘）。

锁定：四步各自记入父阶段细分，慢写告警只看「落盘」那一步。
"""

from __future__ import annotations

import time

import pytest

from unittest.mock import patch

from src.python.core.models import Holding
from src.python.report.market_value import DetailRow

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]

_HOLDINGS = [
    Holding(name="招商银行", code="600036", shares=5000.0, cost_price=35.0, account="测试账户"),
    Holding(name="贵州茅台", code="600519", shares=200.0, cost_price=1800.0, account="测试账户"),
]

_DETAILS = [
    DetailRow(
        account="测试账户",
        name="招商银行",
        code="600036",
        price=35.0,
        shares=5000.0,
        market_value=175000.0,
        cost=175000.0,
        profit=10000.0,
        profit_rate=6.0,
    ),
    DetailRow(
        account="测试账户",
        name="贵州茅台",
        code="600519",
        price=1800.0,
        shares=200.0,
        market_value=360000.0,
        cost=360000.0,
        profit=50000.0,
        profit_rate=16.0,
    ),
]


def _offline_report_sources():
    """断开渲染期的指数/穿透取数（用例只验证阶段细分，不验证数据源）。"""
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch("src.python.report.html_renderers.fetch_indices", return_value={}))
    stack.enter_context(patch("src.python.report.html_renderers.fetch_us_indices", return_value={}))
    stack.enter_context(patch("src.python.report.html_renderers.compute_penetration_top10", return_value={}))
    return stack


class _Recorder:
    """阶段细分记录器替身（同 ``core.perf.PhaseBreakdownRecorder.record`` 语义）。"""

    def __init__(self) -> None:
        self.spans: dict[str, float] = {}

    def record(self, name: str, seconds: float) -> None:
        self.spans[name] = self.spans.get(name, 0.0) + float(seconds)


def test_write_html_report_records_four_substeps(tmp_path, monkeypatch):
    """渲染/内嵌/匿名化/落盘四步分别落细分，且内嵌耗时归到内嵌而非渲染。"""
    import src.python.report.html_writer as hw

    def _slow_inline(html: str) -> str:
        time.sleep(0.05)
        return html

    monkeypatch.setattr(hw, "_inline_js_assets", _slow_inline)
    recorder = _Recorder()

    with _offline_report_sources():
        hw.write_html_report(
            _HOLDINGS,
            output_dir=str(tmp_path),
            include_news=False,
            enable_llm=False,
            details=_DETAILS,
            stage_recorder=recorder,
        )

    assert {"模板渲染", "资产内嵌", "匿名化", "落盘"} <= set(recorder.spans), (
        f"四步须各自落细分，否则慢的时候无法归因: {sorted(recorder.spans)}"
    )
    assert recorder.spans["资产内嵌"] >= 0.04, "内嵌耗时须记在「资产内嵌」，不得被并入渲染段"
    assert list(tmp_path.glob("*.html")), "报告仍须正常落盘"


def test_stage_recorder_optional(tmp_path):
    """不传记录器时行为不变（只为诊断服务，不成为写入前提）。"""
    import src.python.report.html_writer as hw

    with _offline_report_sources():
        path = hw.write_html_report(
            _HOLDINGS,
            output_dir=str(tmp_path),
            include_news=False,
            enable_llm=False,
            details=_DETAILS,
        )

    assert path.endswith(".html")
