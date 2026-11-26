# -*- coding: utf-8 -*-
"""调仓纪律回放面板（schedule_replay_panel）分支覆盖。

覆盖：持仓行归一（对象/dict/零份额）、净值取数异常与空序列兜底、费率索引异常降级、
开关/空持仓/全取数失败三类占位、提示词块渲染与零贡献回退、双端视图的分支
（成本未知、阈值触发 >5 次、chart 数据缺失、notes 去重、取数失败提示）、
Excel 页签的数据/占位两态写入。

取数（历史净值 / 费率 / 场内判定）全部经替身注入，零网络、零真实文件。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from openpyxl import Workbook

from src.python.report import schedule_replay_panel as panel_mod
from src.python.report.schedule_replay_panel import (
    LIMITATIONS_NOTE,
    build_schedule_replay_panel,
    build_schedule_replay_view,
    write_schedule_replay_sheet,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _sheet_text(ws) -> str:
    return "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)


def _period(date_text: str, *, cost_known: bool, cost: float = 12.5) -> dict:
    return {
        "date": date_text,
        "trades": 3,
        "turnover": 0.25,
        "cost": cost,
        "cost_known": cost_known,
    }


def _run(*, fired: list[str], periods: list[dict], notes: list[str], with_series: bool = True) -> dict:
    run = {
        "available": True,
        "reason": "",
        "cost_note": "已逐笔计入",
        "metrics": {
            "replay": {
                "total_return": 0.1234,
                "annualized": 0.0567,
                "max_drawdown": -0.0812,
                "sharpe": 1.234,
            },
            "buyhold": {
                "total_return": 0.1,
                "annualized": 0.04,
                "max_drawdown": -0.05,
                "sharpe": 0.9,
            },
        },
        "periods": periods,
        "trigger": {"fired": fired, "count": len(fired)},
        "notes": notes,
    }
    if with_series:
        run["series"] = {
            "dates": ["2026-09-01", "2026-10-01"],
            "replay": [100.0, 112.34],
            "buyhold": [100.0, 108.12],
        }
    return run


def _panel(**overrides) -> dict:
    panel = {
        "available": True,
        "reason": "",
        "window": {"start": "2026-09-01", "end": "2026-10-30", "points": 40},
        "gap_pct": 0.0125,
        "cost_note": "已逐笔计入",
        "rules": {
            "monthly": _run(
                fired=["2026-09-02", "2026-10-02"], periods=[_period("2026-09-02", cost_known=True)], notes=["A"]
            ),
            "threshold": _run(fired=[], periods=[], notes=["A", "B"]),
        },
        "fetch_failed": ["某基金(000001)"],
        "prompt_block": "",
    }
    panel.update(overrides)
    return panel


class TestCoerceRows:
    def test_dict_and_object_rows_normalized(self):
        holdings = [
            {"code": "600900", "shares": 100, "cost_price": 20.5},
            {"code": "", "shares": 100},
            SimpleNamespace(code="005827", name="蓝筹精选", shares=200.0, cost_price=2.0),
            SimpleNamespace(code="000002", shares=0),
        ]
        rows = panel_mod._coerce_rows(holdings)
        assert [r["code"] for r in rows] == ["600900", "005827"]
        assert rows[0]["name"] == "600900"  # dict 缺 name → 回落代码
        assert rows[0]["cost"] == pytest.approx(20.5)  # cost_price 别名
        assert rows[1]["name"] == "蓝筹精选"


class TestFetchNavSeries:
    def test_exception_and_empty_series_go_to_failed(self):
        boom = Mock(side_effect=RuntimeError("行情源不可用"))
        empty = Mock(return_value=[])
        calc = Mock()
        calc.calculate_for_holding.side_effect = [
            [{"date": "2026-09-01 00:00:00", "close": 1.5}, {"date": "2026-09-02", "close": 0}],
            boom.side_effect,
            empty.return_value,
            [{"date": "2026-09-03", "close": 0}],
        ]
        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator", return_value=calc):
            navs, failed = panel_mod._fetch_nav_series(
                [
                    {"code": "600900", "name": "长江电力", "shares": 100.0, "cost": 1.0},
                    {"code": "000001", "name": "某基金", "shares": 100.0, "cost": 1.0},
                    {"code": "005827", "name": "蓝筹精选", "shares": 100.0, "cost": 1.0},
                    {"code": "000002", "name": "全零收盘", "shares": 100.0, "cost": 1.0},
                ],
                90,
            )
        # 只有正收盘价进序列（close=0 被过滤）；空返回与全无效收盘分别落到两种失败文案
        assert navs == {"600900": {"2026-09-01": 1.5}}
        assert failed == ["某基金(000001)", "蓝筹精选(005827)", "全零收盘(000002)(空序列)"]


class TestBuildPanelPlaceholders:
    def test_feature_disabled(self):
        with patch("src.python.config.features.is_feature_enabled", return_value=False):
            panel = build_schedule_replay_panel([{"code": "600900", "shares": 100}])
        assert panel["available"] is False
        assert "rebalance_schedule_replay" in panel["reason"]
        assert panel["rules"] == {}

    def test_no_rows(self):
        with patch("src.python.config.features.is_feature_enabled", return_value=True):
            panel = build_schedule_replay_panel([{"code": "600900", "shares": 0}])
        assert panel["available"] is False
        assert panel["reason"] == "无可回放持仓（持仓为空）"

    def test_all_nav_failed(self):
        with (
            patch("src.python.config.features.is_feature_enabled", return_value=True),
            patch.object(panel_mod, "_fetch_nav_series", return_value=({}, ["长江电力(600900)"])),
        ):
            panel = build_schedule_replay_panel([{"code": "600900", "shares": 100}])
        assert panel["available"] is False
        assert panel["reason"] == "历史净值获取失败（全部品种无行情），回放不可用"


class TestBuildPanelSuccess:
    def test_fee_index_exception_degrades_to_unmodeled(self):
        run = _run(fired=[], periods=[], notes=[])
        holdings = [{"code": "600900", "name": "长江电力", "shares": 100, "cost": 20.0}]
        with (
            patch("src.python.config.features.is_feature_enabled", return_value=True),
            patch.object(panel_mod, "_fetch_nav_series", return_value=({"600900": {"2026-09-01": 20.0}}, [])),
            patch("src.python.report.whatif_cost_panel.is_unmodeled_cost_code", return_value=False),
            patch("src.python.fetcher.fund_fee.fetch_fee_index", side_effect=RuntimeError("费率源 500")),
            patch.object(panel_mod, "run_schedule_replay", return_value=run) as replay,
        ):
            panel = build_schedule_replay_panel(holdings, window_days=60)
        # 费率异常 → fee_index 降级 None，但两条规则照常跑
        assert panel["available"] is True
        assert replay.call_count == 2
        monthly_kwargs = replay.call_args_list[0].kwargs
        assert monthly_kwargs["fee_index"] is None
        assert monthly_kwargs["window_days"] == 60
        threshold_rule = replay.call_args_list[1].args[2]
        assert threshold_rule == {"rule_type": "threshold", "threshold_pp": 5.0}

    def test_unmodeled_codes_skip_fee_fetch_and_failed_logged(self):
        navs = {"600900": {"2026-09-01": 20.0}, "005827": {"2026-09-01": 2.0}}
        run = _run(fired=[], periods=[], notes=[])
        holdings = [
            {"code": "600900", "name": "长江电力", "shares": 100, "cost": 20.0},
            {"code": "005827", "name": "蓝筹精选", "shares": 200, "cost": 2.0},
        ]
        with (
            patch("src.python.config.features.is_feature_enabled", return_value=True),
            patch.object(panel_mod, "_fetch_nav_series", return_value=(navs, ["某某(000002)"])),
            patch(
                "src.python.report.whatif_cost_panel.is_unmodeled_cost_code",
                side_effect=lambda name, code: code == "600900",
            ),
            patch("src.python.fetcher.fund_fee.fetch_fee_index", return_value={"005827": {"buy": 0.0015}}) as fee,
            patch.object(panel_mod, "run_schedule_replay", return_value=run) as replay,
        ):
            panel = build_schedule_replay_panel(holdings)
        # 场内品种不进费率索引请求
        fee.assert_called_once_with(["005827"])
        assert replay.call_args_list[0].kwargs["fee_index"] == {"005827": {"buy": 0.0015}}
        assert replay.call_args_list[0].kwargs["unmodeled_codes"] == {"600900"}
        # 取数失败清单进契约，prompt_block 按同一视图渲染（可用态非空）
        assert panel["available"] is True
        assert panel["fetch_failed"] == ["某某(000002)"]
        assert panel["prompt_block"].startswith("【调仓纪律回放")
        assert LIMITATIONS_NOTE in panel["prompt_block"]


class TestFormatHelpers:
    def test_fmt_num_none_and_thousands(self):
        assert panel_mod._fmt_num(None) == "—"
        assert panel_mod._fmt_num(1234.5) == "1,234.50"


class TestPromptBlock:
    def test_unavailable_returns_empty(self):
        assert panel_mod._build_prompt_block({"available": False}) == ""

    def test_renders_metric_and_period_rows(self):
        view = build_schedule_replay_view(_panel())
        block = panel_mod._build_prompt_block(view)
        assert block.startswith("【调仓纪律回放")
        assert "指标对照：" in block
        assert "规则 A 月度定期" in block
        assert "逐期调仓（规则 A，最近 1 期）：" in block
        assert LIMITATIONS_NOTE in block


class TestBuildView:
    def test_none_and_unavailable(self):
        none_view = build_schedule_replay_view(None)
        assert none_view["available"] is False
        assert none_view["reason"] == "调仓纪律回放数据不足"
        assert none_view["limitations_note"] == LIMITATIONS_NOTE

        unavailable = build_schedule_replay_view({"available": False, "reason": "开关关闭"})
        assert unavailable["reason"] == "开关关闭"
        assert unavailable["metric_rows"] == []

    def test_available_full(self):
        view = build_schedule_replay_view(_panel())
        assert view["available"] is True
        assert view["title_summary"].startswith("2026-09-01 ~ 2026-10-30（40 个净值日）")
        assert "月度定期 1 次 / 阈值 5pp 触发 0 次" in view["title_summary"]
        assert len(view["metric_rows"]) == 3
        assert view["metric_rows"][0][0] == "买入持有"
        assert view["period_rows"][0][4] == "已计（申赎费）"
        assert view["trigger_lines"] == [
            "规则 A 到点 2 次（首次 2026-09-02、末次 2026-10-02）",
            "规则 B 窗口内未触发（偏离始终小于 5pp）——无调仓期行",
        ]
        assert view["chart"] == {
            "dates": ["09-01", "10-01"],
            "replay": [100.0, 112.34],
            "buyhold": [100.0, 108.12],
        }
        # notes 去重（A 在两规则各出现一次）
        assert view["notes"][:2] == ["A", "B"]
        assert view["notes"][-1].startswith("取数失败品种")

    def test_cost_unknown_and_many_threshold_fires(self):
        threshold_fired = [f"2026-09-{d:02d}" for d in range(1, 8)]
        panel = _panel(
            cost_note="未计成本",
            gap_pct=None,
            fetch_failed=[],
            rules={
                "monthly": _run(
                    fired=[], periods=[_period("2026-09-02", cost_known=False)], notes=[], with_series=False
                ),
                "threshold": _run(fired=threshold_fired, periods=[], notes=[], with_series=False),
            },
        )
        view = build_schedule_replay_view(panel)
        assert view["period_rows"][0][4] == "未计成本"  # cost_known=False → 回显成本态
        assert view["period_rows"][0][3] == "—"
        assert view["trigger_lines"][0] == (
            "规则 B 触发 7 次（2026-09-01、2026-09-02、2026-09-03、2026-09-04、2026-09-05 等共 7 次）"
        )
        assert view["chart"] is None
        assert "行情缺口 —" in view["summary_lines"][0]
        assert view["notes"] == []


class TestWriteSheet:
    def _ws(self):
        wb = Workbook()
        return wb, wb.active

    def test_placeholder_path(self):
        wb, ws = self._ws()
        write_schedule_replay_sheet(ws, {"available": False, "reason": "无可回放持仓（持仓为空）"})
        assert "无可回放持仓（持仓为空）" in _sheet_text(ws)
        assert ws.freeze_panes is not None

    def test_data_path_writes_rows(self):
        wb, ws = self._ws()
        write_schedule_replay_sheet(ws, _panel())
        text = _sheet_text(ws)
        assert "纪律回放 vs 买入持有（指标对照）" in text
        assert "规则 A 月度定期" in text
        assert "规则 A 逐期调仓与成本" in text
        assert "2026-09-02" in text
        assert LIMITATIONS_NOTE in text

    def test_empty_period_rows_writes_fallback_line(self):
        wb, ws = self._ws()
        panel = _panel(
            rules={
                "monthly": _run(fired=[], periods=[], notes=[]),
                "threshold": _run(fired=[], periods=[], notes=[]),
            }
        )
        write_schedule_replay_sheet(ws, panel)
        assert "窗口内无调仓期行" in _sheet_text(ws)
