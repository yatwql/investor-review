"""both 报告路径的结构契约测试。

断言的是**结构不变式**（把五个阶段拆成独立函数前后都必须成立），不是某次产物的内容：

  - 阶段名与顺序：perf 阶段序列 == 文档化契约（`perf_history` 跨版本可比性的口径）
  - 阶段配对：每个 `start` 都有配对的 `stop`，异常路径同样收口
  - 运行生命周期：`start_report_run` 先于首个阶段、`finish_report_run` 后于末个阶段
  - 双产物成败：HTML 与 Excel 互不连带，`report_generated` = 任一成功
  - 快照口径：经 `capture_snapshot` 捕获并透传 `snapshot_namespace`（不自行判定）
  - 健康检查：收尾统一收集（不阻塞主路径）

运行：
  pytest src/test/unit/report/test_report_both_stage_contract.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]

#: 五个主阶段（perf 口径）——改动即改历史可比性，须同步技术文档与 perf 分析
MAIN_STAGES = ("行情获取", "快照对比", "历史走势", "HTML 生成", "Excel 生成")
#: 阶段内子阶段（在所属主阶段内单独计时，出现在主阶段之后）
SUB_STAGES = ("判断依据块装配",)


class _RecordingPerf:
    """最小 PerfCollector 替身：记录 start/stop 序列与递归记录器。"""

    events: list[tuple[str, str]] = []

    def __init__(self, **_kwargs) -> None:
        pass

    def start(self, name: str) -> None:
        type(self).events.append(("start", name))

    def stop(self) -> None:
        type(self).events.append(("stop", ""))

    def recorder(self, _name: str):
        return MagicMock()

    def add(self, *_args, **_kwargs) -> None:
        pass


def _patches(*, html_error: bool = False, excel_error: bool = False, history_enabled: bool = True):
    """构造一组最小 patch：数据契约与产物落盘全部替身，只有编排逻辑真实执行。"""
    html_side = MagicMock(side_effect=RuntimeError("HTML 炸了")) if html_error else MagicMock(return_value="ok.html")
    excel_side = MagicMock(side_effect=RuntimeError("Excel 炸了")) if excel_error else MagicMock()
    start_run = MagicMock()
    finish_run = MagicMock()
    collect_health = MagicMock()

    return [
        # 数据获取与契约装配（全部替身，避免任何真实取数）
        patch("src.python.report._both_stages._compute_details", return_value=[MagicMock()]),
        patch("src.python.report.orchestrator.compute_valuation_data", return_value=None),
        patch("src.python.report.orchestrator.compute_market_temperature_data", return_value=None),
        patch("src.python.report.purchase_status.build_purchase_status_data", return_value=None),
        patch("src.python.report._both_stages._inject_evolution_data", side_effect=lambda data, **_: data),
        patch("src.python.report._both_stages._inject_snapshot_diff_data", side_effect=lambda data, **_: data),
        patch("src.python.report._experimental_seams.inject_holding_change_data"),
        patch(
            "src.python.core.holding_status.build_coverage_summary",
            return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
        ),
        patch(
            "src.python.core.data_freshness.build_freshness_summary",
            return_value={"available": True, "items": [], "abnormal_count": 0, "summary": ""},
        ),
        patch("src.python.report.pipeline_data_builder.merge_pipeline_data", side_effect=lambda data, **_kw: data),
        patch("src.python.report._snapshot.capture_snapshot", return_value={"diff": {}}),
        patch("src.python.report._snapshot.fetch_history_data", return_value={"dates": [], "bars": []}),
        patch("src.python.report._snapshot.assemble_history_augmented_data"),
        patch("src.python.report._snapshot.latest_quotes_from_detail_rows", return_value={}),
        patch("src.python.analysis.tail_risk.compute_tail_risk", return_value={"available": False}),
        patch("src.python.analysis.action_advisor.build_action_data", return_value={"available": True}),
        patch("src.python.analysis.metrics.compute_portfolio_peak_mv", return_value=None),
        patch("src.python.report.decision_basis.build_decision_basis_data", return_value={"available": True}),
        patch("src.python.report._experimental_seams.record_deterministic_decisions"),
        patch("src.python.report._experimental_seams.record_llm_decisions_and_review_block"),
        patch("src.python.report._experimental_seams.record_prosperity_diagnosis"),
        patch("src.python.report._report_aux_metrics.compute_market_sentiment_data", return_value=None),
        patch("src.python.report._both_stages._build_chart_datasets_for_report", return_value={}),
        # 产物落盘
        patch("src.python.report.html_writer.write_html_report", html_side),
        patch("src.python.report.excel_generator.generate_excel_report", excel_side),
        # 运行边界与健康检查
        patch("src.python.report._run_scope.start_report_run", new=start_run),
        patch("src.python.report._run_scope.finish_report_run", new=finish_run),
        patch("src.python.report._generation_both._spawn_health_checks", return_value="future"),
        patch("src.python.report._generation_both._collect_health_checks", new=collect_health),
        # 配置开关
        patch("src.python.config.is_enable_fund_deep_analysis", return_value=False),
        patch("src.python.config.is_enable_news", return_value=False),
        patch("src.python.config.is_enable_history", return_value=history_enabled),
        patch("src.python.config.is_enable_portfolio_evolution", return_value=False),
        patch("src.python.config.is_enable_action", return_value=False),
        patch("src.python.config.is_enable_cost_lots", return_value=False),
        patch("src.python.config.is_enable_stock_fundamentals", return_value=False),
        patch("src.python.config.features.is_feature_enabled", return_value=False),
        patch("src.python.core.registry.get_report_section_order", return_value=[]),
        # perf 替身
        patch("src.python.core.perf.PerfCollector", _RecordingPerf),
        # 门面级依赖（bind_* 记录用，不关心行为）
        patch("src.python.report._generation_both.bind_perf"),
        patch("src.python.report._generation_both.bind_health"),
    ], {"start_run": start_run, "finish_run": finish_run, "health": collect_health}


def _run(**kwargs):
    """跑一次 both 路径（无真实取数/落盘）。"""
    from src.python.report._generation_both import _generate_report_both

    patches, spies = _patches(**kwargs)
    _RecordingPerf.events = []
    for p in patches:
        p.start()
    try:
        result = _generate_report_both(
            holdings=[MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)],
            config={"output_dir": "reports", "news_top_count": 10},
            reporter=MagicMock(),
            fetch_history=True,
        )
    finally:
        for p in reversed(patches):
            p.stop()
    return result, spies


def _started_names() -> list[str]:
    return [name for kind, name in _RecordingPerf.events if kind == "start"]


def test_stage_names_and_order_match_contract():
    """阶段名与顺序 == 契约：主阶段按序出现，且不出现未登记的阶段名。

    子阶段（判断依据块装配）在所属主阶段内额外计时，故按「主阶段子序列 + 名字集合上界」断言，
    既能抓住重命名/换序，又不把条件子阶段的出现次数写死。
    """
    _run()
    started = _started_names()

    assert tuple(n for n in started if n in MAIN_STAGES) == MAIN_STAGES, f"主阶段顺序异常: {started}"
    assert set(started) <= set(MAIN_STAGES) | set(SUB_STAGES), f"出现未登记的阶段名: {started}"


def test_every_start_has_paired_stop():
    """每个 start 都有配对的 stop：计数相等，且事件序列是严格交替。"""
    _run()

    starts = [e for e in _RecordingPerf.events if e[0] == "start"]
    stops = [e for e in _RecordingPerf.events if e[0] == "stop"]
    assert len(starts) == len(stops), f"start/stop 未配对: {_RecordingPerf.events}"
    assert _RecordingPerf.events[0][0] == "start" and _RecordingPerf.events[-1][0] == "stop"


def test_stage_stop_happens_even_when_html_raises():
    """HTML 阶段抛异常：该阶段的 stop 仍然执行（阶段计时不留开口子）。"""
    result, _ = _run(html_error=True)

    assert result.html_ok is False
    starts = [e for e in _RecordingPerf.events if e[0] == "start"]
    stops = [e for e in _RecordingPerf.events if e[0] == "stop"]
    assert len(starts) == len(stops), f"异常路径 start/stop 未配对: {_RecordingPerf.events}"


def test_run_lifecycle_wraps_all_stages():
    """运行边界：start_report_run 在阶段之前、finish_report_run 在阶段之后（各一次）。"""
    _run()
    _, spies = _run()

    assert spies["start_run"].call_count == 1, "运行边界必须恰好开一次"
    assert spies["finish_run"].call_count == 1, "运行边界必须恰好收一次"


def test_html_and_excel_failures_are_independent():
    """双产物互不连带：HTML 失败不影响 Excel，反之亦然；report_generated = 任一成功。"""
    html_fail, _ = _run(html_error=True)
    assert (html_fail.html_ok, html_fail.excel_ok, html_fail.report_generated) == (False, True, True)
    assert any("HTML" in err for err in html_fail.errors)

    excel_fail, _ = _run(excel_error=True)
    assert (excel_fail.html_ok, excel_fail.excel_ok, excel_fail.report_generated) == (True, False, True)
    assert any("Excel" in err for err in excel_fail.errors)


def test_snapshot_capture_gets_namespace_passthrough():
    """快照口径：经 `capture_snapshot` 并透传命名空间（编排层不自行判定去留）。"""
    from src.python.report._generation_both import _generate_report_both

    patches, _ = _patches()
    for p in patches:
        p.start()
    try:
        with patch("src.python.report._snapshot.capture_snapshot", return_value={"diff": {}}) as capture:
            _generate_report_both(
                holdings=[MagicMock(code="SH600001", name="测试", shares=100, cost_price=10.0)],
                config={"output_dir": "reports", "news_top_count": 10},
                reporter=MagicMock(),
                snapshot_namespace="web",
            )
    finally:
        for p in reversed(patches):
            p.stop()

    assert capture.call_args.kwargs.get("snapshot_namespace") == "web"


def test_health_checks_collected_once_at_tail():
    """健康检查：启动后在收尾统一收集（不阻塞主路径，只收一次）。"""
    _run()
    _, spies = _run()
    spies["health"].assert_called_once()


def test_history_stage_skipped_when_disabled():
    """历史走势关闭：阶段不出现（阶段表按开关条件执行），且不调用历史取数。"""
    with patch("src.python.report._snapshot.fetch_history_data") as fetch:
        result, _ = _run(history_enabled=False)

    assert "历史走势" not in _started_names()
    assert not fetch.called
    assert result.report_generated is True
