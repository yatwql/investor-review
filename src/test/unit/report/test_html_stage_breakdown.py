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


class TestCloseHtmlGenerationStage:
    """收口助手（full / both 共用）的直测：总值 + 慢段分流 + 无 recorder 直返。

    该助手把「整段记一个页面写入」与「按段告警」两件事收成单点，两条生成路径共用；
    此前只由端到端用例间接触及，分支（无 recorder / 无分段 / 有分段）未被逐条锁住。
    """

    def test_returns_early_without_recorder(self, caplog):
        """recorder 为 None（阶段记录未开启）→ 直接返回，不得告警、不得抛异常。"""
        import logging

        from src.python.report.html_writer import close_html_generation_stage

        with caplog.at_level(logging.WARNING, logger="invest"):
            close_html_generation_stage(None, 999.0, None)
        assert caplog.records == [], f"无 recorder 时不应产生任何告警：{[r.getMessage() for r in caplog.records]}"

    def test_records_total_and_warns_on_disk_span(self, tmp_path, caplog):
        import logging

        from src.python.report.html_writer import close_html_generation_stage

        class _Recorder:
            def __init__(self):
                self.recorded = []

            def record(self, name, seconds):
                self.recorded.append((name, seconds))

            def spans(self):
                return {"模板渲染": 0.01, "落盘": 99.0}

        rec = _Recorder()
        target = tmp_path / "r.html"
        target.write_bytes(b"x" * 1024)
        with caplog.at_level(logging.WARNING, logger="invest"):
            close_html_generation_stage(rec, 100.0, str(target))

        assert rec.recorded == [("页面写入", 100.0)], "总值必须记入父阶段（跨版本可比）"
        messages = [r.getMessage() for r in caplog.records]
        assert any("HTML 页面写入" in m and "99" in m for m in messages), (
            f"慢段告警应取「落盘」分段耗时而非总值：{messages}"
        )

    def test_render_span_warns_with_template_hint(self, caplog):
        import logging

        from src.python.report.html_writer import close_html_generation_stage

        class _Recorder:
            def record(self, name, seconds):
                pass

            def spans(self):
                return {"模板渲染": 99.0, "落盘": 0.001}

        with caplog.at_level(logging.WARNING, logger="invest"):
            close_html_generation_stage(_Recorder(), 99.5, None)

        messages = [r.getMessage() for r in caplog.records]
        render_msgs = [m for m in messages if "HTML 模板渲染" in m]
        assert render_msgs, f"渲染慢须单独告警：{messages}"
        # 告警方向必须指向模板（排查提示含「模板内…」），不能沿用落盘的「排查磁盘」口径
        assert any("排查模板" in m for m in render_msgs), f"渲染段告警方向须指向模板：{render_msgs}"
        assert not any("排查磁盘" in m for m in render_msgs), f"渲染段不得指向磁盘：{render_msgs}"

    def test_recorder_without_spans_falls_back_to_total(self, caplog):
        import logging

        from src.python.report.html_writer import close_html_generation_stage

        class _PlainRecorder:
            def __init__(self):
                self.recorded = []

            def record(self, name, seconds):
                self.recorded.append(name)

        rec = _PlainRecorder()
        with caplog.at_level(logging.WARNING, logger="invest"):
            close_html_generation_stage(rec, 99.0, None)

        assert rec.recorded == ["页面写入"]
        assert any("HTML 页面写入" in r.getMessage() for r in caplog.records), "无分段时按总值告警"
