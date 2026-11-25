"""Excel 生成器的页签级兜底隔离与可选明细页签装配。

覆盖三类「非关键页签失败不得中断报告」的隔离分支，以及此前从未被
装配过的可选明细页签（持仓变动 / 事件窗 / 调度回放 / 基本面）：

- 单个页签写入抛异常 → 只记 debug，后续页签继续写（隔离性）
- 汇总页脚实验清单 / 隐私脚注 / 返回汇总链接失败 → 同样不中断保存
- 环比对比摘要的持仓变动概要（>5 只时追加「等N只」）
- `load_report_modules` 返回空（excel_writer 缺失）→ 直接返回不建工作簿
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from openpyxl import Workbook

from src.python.report.excel_generator import (
    _finalize_and_save,
    _write_diff_summary_block,
    _write_optional_detail_sheets,
    _write_portfolio_history_drawdown_sheet,
    generate_excel_report,
)
from src.python.report.progress import SilentProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _wb():
    wb = Workbook()
    wb.remove(wb.active)
    return wb


def _sheets(*names: str) -> dict:
    """按页签名建一组真实 worksheet（页签写入依赖 max_row 等真实属性）。"""
    wb = _wb()
    return {name: wb.create_sheet(title=name[:31]) for name in names}


def test_history_drawdown_sheet_absent_is_noop() -> None:
    """页签未创建（开关关闭）→ 直接返回，不调用写入器。"""
    with patch("src.python.report.portfolio_history_drawdown_sheet.write_portfolio_history_drawdown_sheet") as writer:
        _write_portfolio_history_drawdown_sheet({"summary": MagicMock()}, None, None, None, None)

    writer.assert_not_called()


def test_all_optional_sheets_written_with_injected_contracts() -> None:
    """全部可选页签存在且契约齐备 → 各自写入一次，参数为对应契约数据。"""
    sheets = _sheets(
        "portfolio_history_drawdown",
        "portfolio_evolution",
        "holding_change",
        "news_correlation",
        "schedule_replay",
        "fundamental_snapshot",
        "action",
        "data_source_status",
    )
    pipeline_data = {
        "holding_change_data": {"events": [{"code": "600900"}]},
        "event_impact_data": {"events": [{"title": "降准"}]},
        "schedule_replay_data": {"periods": [{"label": "2024Q1"}]},
        "action_data": {"actions": [{"code": "600900", "action": "持有"}]},
        "decision_review_data": {"items": []},
        "prosperity_framework_data": {"stage": "扩张"},
        "market_sentiment_data": {"level": "中性"},
        "decision_basis_data": {"basis": "业绩"},
        "position_status": {"600900": "ok"},
        "data_freshness": {"600900": 1},
    }
    history_data = {"status": "ok", "bars": [{"date": "2024-01-02", "value": 1.0}], "terminal_staleness": 2}
    indicator = {"600900": {"roe": 0.15}}
    digest = {"600900": {"digest": "稳健"}}

    with (
        patch("src.python.report.portfolio_history_drawdown_sheet.write_portfolio_history_drawdown_sheet") as hist,
        patch("src.python.report.evolution_sheet.write_evolution_sheet") as evo,
        patch("src.python.report.holding_change_panel.write_holding_change_sheet") as hold,
        patch("src.python.report.event_impact_panel.write_event_impact_footer") as event,
        patch("src.python.report.schedule_replay_panel.write_schedule_replay_sheet") as replay,
        patch("src.python.report.fundamental_snapshot_sheet.write_fundamental_snapshot_sheet") as fund,
        patch("src.python.report.action_sheet.write_action_sheet") as action,
        patch("src.python.report.data_source_matrix.build_data_source_matrix") as matrix,
        patch("src.python.report.data_quality_sheet.write_data_quality_sheet") as quality,
    ):
        matrix.return_value = {"600900": {"sources": []}}
        _write_optional_detail_sheets(
            sheets, pipeline_data, history_data, indicator, digest, True, SilentProgressReporter()
        )

    hist.assert_called_once()
    assert hist.call_args.args[1]["terminal_staleness"] == 2
    evo.assert_called_once()
    assert evo.call_args.args[1] is None  # 未注入 evolution_data → 写占位
    hold.assert_called_once_with(sheets["holding_change"], pipeline_data["holding_change_data"])
    assert event.call_args.args[1] == pipeline_data["event_impact_data"]
    assert event.call_args.kwargs["start_row"] == sheets["news_correlation"].max_row + 2
    replay.assert_called_once_with(sheets["schedule_replay"], pipeline_data["schedule_replay_data"])
    assert fund.call_args.kwargs == {"indicator_data": indicator, "digest_data": digest}
    action.assert_called_once()
    assert action.call_args.kwargs["decision_basis_data"] == {"basis": "业绩"}
    assert quality.call_args.args[1] == {"600900": {"sources": []}}
    assert quality.call_args.args[4] == 2  # terminal_staleness 透传


def test_history_disabled_skips_drawdown_sheet() -> None:
    """enable_history=False → 走势回撤页签即使存在也不写。"""
    sheets = _sheets("portfolio_history_drawdown")
    with patch("src.python.report.portfolio_history_drawdown_sheet.write_portfolio_history_drawdown_sheet") as hist:
        _write_optional_detail_sheets(sheets, {}, None, None, None, False, SilentProgressReporter())

    hist.assert_not_called()


def test_single_sheet_failure_does_not_block_rest(caplog) -> None:
    """任一页签写入抛异常 → 仅记 debug，其余页签照常写入。"""
    sheets = _sheets("holding_change", "schedule_replay", "action")
    with (
        patch(
            "src.python.report.holding_change_panel.write_holding_change_sheet",
            side_effect=RuntimeError("boom"),
        ),
        patch("src.python.report.schedule_replay_panel.write_schedule_replay_sheet") as replay,
        patch("src.python.report.action_sheet.write_action_sheet") as action,
    ):
        with caplog.at_level("DEBUG", logger="invest"):
            _write_optional_detail_sheets(sheets, {"action_data": {}}, None, None, None, True, SilentProgressReporter())

    replay.assert_called_once()
    action.assert_called_once()
    assert "持仓变动复盘页签写入失败（非关键）" in caplog.text


@pytest.mark.parametrize(
    ("sheet_key", "writer_target", "error_text"),
    [
        (
            "portfolio_history_drawdown",
            "portfolio_history_drawdown_sheet.write_portfolio_history_drawdown_sheet",
            "组合历史走势与回撤页签写入失败",
        ),
        ("portfolio_evolution", "evolution_sheet.write_evolution_sheet", "组合演进页签写入失败"),
        ("news_correlation", "event_impact_panel.write_event_impact_footer", "事件窗对照区块写入失败"),
        ("schedule_replay", "schedule_replay_panel.write_schedule_replay_sheet", "调仓纪律回放页签写入失败"),
        (
            "fundamental_snapshot",
            "fundamental_snapshot_sheet.write_fundamental_snapshot_sheet",
            "持仓基本面页签写入失败",
        ),
        ("action", "action_sheet.write_action_sheet", "行动建议页签写入失败"),
        ("data_source_status", "data_quality_sheet.write_data_quality_sheet", "数据质量仪表盘页签写入失败"),
    ],
)
def test_each_optional_sheet_failure_is_isolated(sheet_key: str, writer_target: str, error_text: str, caplog) -> None:
    """逐页签注入异常：每次只吞掉自己的失败，日志点名该页签。"""
    sheets = _sheets(sheet_key)
    pipeline_data = {
        "event_impact_data": {"events": []},
        "action_data": {},
        "position_status": {},
        "data_freshness": {},
    }
    with patch(f"src.python.report.{writer_target}", side_effect=RuntimeError("boom")):
        with caplog.at_level("DEBUG", logger="invest"):
            _write_optional_detail_sheets(
                sheets, pipeline_data, {"status": "ok", "bars": []}, {}, {}, True, SilentProgressReporter()
            )

    assert error_text in caplog.text


def test_diff_summary_lists_long_change_set_with_count_suffix() -> None:
    """持仓变动 >5 只 → 只列前 5 名并追加「等N只」，不写全量清单。"""
    sheets = _sheets("summary")
    added = [{"name": f"标的{i}", "code": f"60{i:04d}"} for i in range(7)]
    pipeline_data = {"diff": {"added": added, "days_since_last_report": 3}}

    _write_diff_summary_block(sheets, pipeline_data, SilentProgressReporter())

    texts = [c.value for row in sheets["summary"].iter_rows() for c in row if c.value]
    assert "新增持仓" in texts
    added_row = next(t for t in texts if isinstance(t, str) and t.startswith("标的0("))
    assert added_row.startswith("标的0(600000), 标的1(600001)")
    assert added_row.endswith("等7只")
    assert "距上次报告" in texts
    assert "3 天" in texts


def test_diff_summary_absent_diff_is_noop() -> None:
    """无 diff / 无 summary 页签 → 零写入。"""
    sheets = _sheets("summary")
    _write_diff_summary_block(sheets, {"diff": None}, SilentProgressReporter())
    _write_diff_summary_block({}, {"diff": {"added": [{"name": "x", "code": "1"}]}}, SilentProgressReporter())

    assert sheets["summary"].max_row == 1
    assert all(c.value is None for row in sheets["summary"].iter_rows() for c in row)


def test_diff_summary_failure_is_swallowed(caplog) -> None:
    """汇总页签不可写（max_row 取不到）→ 摘要整块放弃，不中断报告生成。"""
    broken = MagicMock()
    type(broken).max_row = property(lambda self: (_ for _ in ()).throw(RuntimeError("坏页签")))

    with caplog.at_level("DEBUG", logger="invest"):
        _write_diff_summary_block(
            {"summary": broken}, {"diff": {"days_since_last_report": 2}}, SilentProgressReporter()
        )

    assert "Excel 环比对比摘要写入失败（非关键）" in caplog.text


def test_finalize_isolates_footer_failures(tmp_path, caplog) -> None:
    """汇总页脚 / 隐私脚注 / 返回链接三步各自兜底：全失败仍保存工作簿。"""
    wb = _wb()
    ws = wb.create_sheet(title="汇总")
    sheets = {"summary": ws}
    save_workbook = MagicMock(return_value=str(tmp_path / "r.xlsx"))
    data = {"total_mv": 1.0, "total_cost": 1.0, "total_profit": 0.0, "today_profit": 0.0}

    with (
        patch("src.python.report.excel_generator._write_summary_experimental_notice", side_effect=RuntimeError("a")),
        patch("src.python.report.excel_writer.write_privacy_footer", side_effect=RuntimeError("b")),
        patch("src.python.report.excel_sheet_factory.stamp_back_to_summary", side_effect=RuntimeError("c")),
        patch("src.python.config.anonymizer.get_anonymization_mode", return_value="off"),
    ):
        with caplog.at_level("DEBUG", logger="invest"):
            _finalize_and_save(wb, sheets, [], save_workbook, data, str(tmp_path), SilentProgressReporter())

    save_workbook.assert_called_once()
    assert "汇总页脚实验功能清单写入失败（非关键）" in caplog.text
    assert "页签 summary 写入隐私脚注失败（非关键）" in caplog.text
    assert "返回汇总链接写入失败（非关键）" in caplog.text


def test_generate_returns_early_when_excel_writer_missing() -> None:
    """excel_writer 模块缺失（load_report_modules 返回空）→ 直接返回，不触发保存。"""
    with (
        patch("src.python.report.excel_generator.load_report_modules", return_value={}),
        patch("src.python.report.excel_generator._finalize_and_save") as finalize,
    ):
        generate_excel_report([], progress=SilentProgressReporter())

    finalize.assert_not_called()
