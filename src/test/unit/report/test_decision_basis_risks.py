"""决策依据章的风险类块：约束与纪律明细（``build_discipline_detail``）与风险预算
（``build_risk_budget``）的契约键值、口径文案与降级形态。

块内数字与文案直接进 HTML/Excel 两端，断言按可见字段逐项核对；账本一律指向 tmp_path，全部离线。
"""

from __future__ import annotations


import pytest

from src.python.config.features import reset_feature_flags, set_feature_enabled
from src.python.core import signal_ledger as sl
from src.python.report.decision_basis import (
    build_discipline_detail,
    build_risk_budget,
    build_decision_basis_data,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


@pytest.fixture(autouse=True)
def _reset_features():
    reset_feature_flags()
    yield
    reset_feature_flags()


@pytest.fixture(autouse=True)
def _isolate_decision_ledger(tmp_path, monkeypatch):
    """决策账本隔离：结算摘要默认读账本，测试一律指向 tmp_path。"""
    import src.python.core.decision_ledger as dl

    monkeypatch.setattr(dl, "_DECISION_LEDGER_FILE", str(tmp_path / "decision_ledger.jsonl"))
    return str(tmp_path / "decision_ledger.jsonl")


@pytest.fixture
def ledger_path(tmp_path, monkeypatch):
    """信号账本隔离：读写一律指向 tmp_path，不碰真实 data/state/。"""
    path = str(tmp_path / "signal_ledger.jsonl")
    monkeypatch.setattr(sl, "_SIGNAL_LEDGER_FILE", path)
    return path


class TestConstraintsBlock:
    """集中度约束块：开关关闭时数据契约不出现该键（逐字节回滚），开启时按上限标注。"""

    _HOLDINGS = [{"name": "纳指ETF", "code": "513100", "market_value": 600.0}]

    def test_disabled_by_default_keeps_contract_unchanged(self):
        data = build_decision_basis_data(self._HOLDINGS, 1000.0)
        assert "constraints" not in data
        assert "约束标注" not in data["summary"]

    def test_enabled_annotates_breach_and_summary(self):
        from src.python.config.features import reset_feature_flags

        set_feature_enabled("portfolio_constraints", True)
        try:
            data = build_decision_basis_data(self._HOLDINGS, 1000.0)
        finally:
            reset_feature_flags()
        constraints = data["constraints"]
        assert constraints["enabled"] is True
        assert constraints["breached_count"] == 1
        assert constraints["breached_codes"] == ["513100"]
        assert "约束标注 1 项" in data["summary"]
        # 只标注不阻断：动作与账本侧字段均不受影响（此处断言风险预算独立存在）
        assert data["risk_budget"]["items"][0]["breached"] is True

    def test_rendered_both_channels_when_enabled(self):
        from openpyxl import Workbook

        from src.python.config.features import reset_feature_flags
        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        set_feature_enabled("portfolio_constraints", True)
        try:
            data = build_decision_basis_data(self._HOLDINGS, 1000.0)
            block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
            assert block is not None
            html_text = block.get_text()
            wb = Workbook()
            ws = wb.active
            assert ws is not None
            write_action_sheet(ws, _action_data(), decision_basis_data=data)
            excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        finally:
            reset_feature_flags()
        for text in (html_text, excel_text):
            assert "集中度约束" in text
            assert "单品种权重" in text and "超限" in text
            assert "仅标注，不阻断动作" in text


class TestDisciplineDetail:
    """纪律明细块：触发条 + 距阈值 + 阶段化执行口径（只读复用纪律引擎结果）。"""

    _STOP = {"rule": "止损线 -15%", "name": "纳指ETF", "code": "513100", "value": "-16.0%", "distance_pct": 1.0}
    _TAKE = {"rule": "止盈线 +20%", "name": "长江电力", "code": "600900", "value": "+21.5%", "distance_pct": 1.5}
    _DRAWDOWN = {"rule": "回撤线 -10%", "name": "组合", "code": "", "value": "-18.0%", "distance_pct": 8.0}

    def test_signals_not_wired_marks_unavailable(self):
        detail = build_discipline_detail(None, 1000.0, 1000.0)
        assert detail["available"] is False
        assert detail["reason"] == "未接入纪律信号"
        assert detail["items"] == []

    def test_no_trigger_empty_state(self):
        detail = build_discipline_detail([], 1000.0, 1000.0)
        assert detail["available"] is True
        assert detail["items"] == []
        assert detail["note"] == "当前无纪律触发"

    def test_item_fields_complete(self):
        """每条含规则名/品种/当前值/距阈值/说明，单位取自纪律引擎口径。"""
        detail = build_discipline_detail([self._STOP], 1000.0, 1000.0)
        item = detail["items"][0]
        assert item["rule"] == "止损线 -15%"
        assert item["name"] == "纳指ETF" and item["code"] == "513100"
        assert item["value_label"] == "-16.0%"
        assert item["distance_pct"] == pytest.approx(1.0)
        assert item["distance_label"] == "超线 1.00%"
        assert item["stance_label"]
        assert item["note"]

    @pytest.mark.parametrize(
        ("total_mv", "peak_mv", "regime"),
        [(900.0, 1000.0, "down"), (1000.0, 1000.0, "normal"), (None, None, "unknown")],
    )
    def test_regime_detection(self, total_mv, peak_mv, regime):
        detail = build_discipline_detail([self._STOP], total_mv, peak_mv)
        assert detail["regime"] == regime
        assert detail["regime_label"] in {"下跌段", "常态段", "未评估"}

    def test_down_regime_stop_advises_confirmation(self):
        """下跌段止损：提示先确认趋势，而不是机械执行。"""
        detail = build_discipline_detail([self._STOP], 900.0, 1000.0)
        item = detail["items"][0]
        assert item["stance_label"] == "宜确认后执行"
        assert "下跌段" in item["note"] and "确认趋势" in item["note"]

    def test_normal_regime_follows_threshold(self):
        detail = build_discipline_detail([self._STOP], 1000.0, 1000.0)
        assert detail["items"][0]["stance_label"] == "按阈值执行"
        assert "常态段" in detail["items"][0]["note"]

    def test_drawdown_notes_double_reduction_with_stop(self):
        """止损与回撤同向触发时，回撤条说明避免双重减仓（行为仍由纪律引擎决定）。"""
        detail = build_discipline_detail([self._STOP, self._DRAWDOWN], 900.0, 1000.0)
        drawdown_item = detail["items"][1]
        assert "双重减仓" in drawdown_item["note"]

    def test_take_profit_in_down_regime_confirm(self):
        detail = build_discipline_detail([self._TAKE], 900.0, 1000.0)
        assert "已达止盈线" in detail["items"][0]["note"]

    def test_readonly_does_not_touch_signals(self):
        """验收②：只读透传，不修改纪律触发条（触发行为仍是纪律引擎唯一职责）。"""
        signals = [dict(self._STOP), dict(self._DRAWDOWN)]
        snapshot = [dict(sig) for sig in signals]
        build_discipline_detail(signals, 900.0, 1000.0)
        assert signals == snapshot

    def test_summary_reports_trigger_count_and_regime(self, ledger_path):
        data = build_decision_basis_data(
            [{"name": "纳指ETF", "code": "513100", "market_value": 900.0}],
            900.0,
            1000.0,
            discipline_signals=[dict(self._STOP)],
        )
        assert "纪律触发 1 条" in data["summary"]
        assert "下跌段" in data["summary"]


class TestRiskBudget:
    """风险预算块：上限 vs 现状三行（单品种 / 行业 / 回撤），单位百分数数值。"""

    @pytest.mark.parametrize(("market_value", "breached"), [(600.0, True), (100.0, False)])
    def test_single_weight_breach(self, market_value, breached):
        """单品种权重取 `rebalance.threshold`（默认 15%），超限即 breached。"""
        rb = build_risk_budget([{"name": "纳指ETF", "code": "513100", "market_value": market_value}], 1000.0)
        item = rb["items"][0]
        assert item["item"] == "单品种权重"
        assert item["max_pct"] == pytest.approx(15.0)
        assert item["current_pct"] == pytest.approx(market_value / 10.0)
        assert item["breached"] is breached
        assert item["status_label"] == ("超限" if breached else "正常")
        assert rb["breached_count"] == (1 if breached else 0)

    def test_industry_unconfigured_not_zero(self):
        """无行业上限配置键 → 显式「未配置上限」，不得显示 0。"""
        rb = build_risk_budget([{"name": "X", "code": "1", "market_value": 100.0}], 1000.0)
        item = rb["items"][1]
        assert item["item"] == "行业权重"
        assert item["max_pct"] is None and item["current_pct"] is None
        assert item["max_label"] == "未配置上限"
        assert item["status_label"] == "未配置"
        assert item["breached"] is False

    def test_drawdown_breach_uses_discipline_threshold(self):
        """回撤上限取 `discipline.drawdown_pct`（默认 −10%），现状相对历史峰值。"""
        rb = build_risk_budget([{"name": "X", "code": "1", "market_value": 800.0}], 800.0, portfolio_peak_mv=1000.0)
        item = rb["items"][2]
        assert item["item"] == "组合回撤"
        assert item["max_pct"] == pytest.approx(-10.0)
        assert item["current_pct"] == pytest.approx(-20.0)
        assert item["breached"] is True
        assert item["status_label"] == "超限"

    def test_drawdown_without_peak_is_unevaluated(self):
        rb = build_risk_budget([{"name": "X", "code": "1", "market_value": 800.0}], 800.0)
        item = rb["items"][2]
        assert item["current_label"] == "未评估"
        assert item["status_label"] == "未评估"
        assert item["breached"] is False
        assert item["max_pct"] == pytest.approx(-10.0)

    def test_drawdown_never_negative_when_new_high(self):
        """市值创新高时回撤归零，不出现负回撤。"""
        rb = build_risk_budget([{"name": "X", "code": "1", "market_value": 1200.0}], 1200.0, portfolio_peak_mv=1000.0)
        assert rb["items"][2]["current_pct"] == pytest.approx(0.0)
        assert rb["items"][2]["breached"] is False

    def test_unavailable_without_holdings(self):
        assert build_risk_budget(None, 0)["available"] is False
        assert build_risk_budget([], 1000.0)["reason"] == "缺少持仓市值"

    def test_summary_reports_breached_count(self, ledger_path):
        data = build_decision_basis_data([{"name": "X", "code": "1", "market_value": 600.0}], 1000.0)
        assert "风险预算超限 1 项" in data["summary"]
