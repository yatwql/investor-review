"""判断依据章内块（形态 A）数据契约、信号清单与双端同源测试。

覆盖：数据契约（信号清单字段齐全 / 区分度三态如实标注 / 回测结论模块常量登记）、
开关关闭仅返回 enabled=False（回滚通道）、零参数签名（零 LLM 依赖结构断言）、
可信度仲裁四枚举规则（含 reason）、enable_llm 两态输出逐字节一致、
渠道范围（HTML/Excel 呈现，CLI/TUI 不引用）、双端同源（同一份
decision_basis_data 在 HTML/Excel 渲染出的标题与 summary 一致，防一处写死）。
全部离线，不触网。
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.python.config.features import reset_feature_flags, set_feature_enabled
from src.python.core import signal_ledger as sl
from src.python.report import decision_basis as db
from src.python.report.decision_basis import (
    BACKTEST_CONCLUSIONS,
    BACKTEST_DATE_FALLBACK,
    BACKTEST_REF,
    build_discipline_detail,
    build_settlement_summary,
    build_risk_budget,
    BACKTEST_SOURCE,
    BLOCK_TITLE,
    DISCRIMINATION_FAILED,
    DISCRIMINATION_INSUFFICIENT,
    DISCRIMINATION_NOT_BACKTESTED,
    DISCRIMINATION_PASSED,
    FEATURE_FLAG,
    arbitrate_confidence,
    build_decision_basis_data,
    in_direction_axis,
    is_decision_basis_enabled,
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


def _append(signal_type: str, *, report_date: str = "2026-11-01", **kwargs) -> None:
    sl.append_signal(
        signal_type=signal_type,
        report_date=report_date,
        rating=kwargs.pop("rating", "低估"),
        **kwargs,
    )


def _signal_row(**overrides) -> dict:
    """仲裁用最小信号行（in_axis/basis/direction 三键参与规则判定）。"""
    row = {"in_axis": True, "basis": "stat_model", "direction": "bullish", "discrimination": DISCRIMINATION_PASSED}
    row.update(overrides)
    return row


class TestContractShape:
    """数据契约：信号清单 + 可信度，账本空 → 规范空态。"""

    def test_empty_ledger_contract(self, ledger_path):
        d = build_decision_basis_data()
        assert d["enabled"] is True  # 缺省开（纯事实块）
        assert d["available"] is True  # 账本可读即可用，空账本走空态而非不可用
        assert d["title"] == BLOCK_TITLE == "判断依据"
        assert d["signals"] == []
        assert d["confidence"]["level"] == "unknown"
        assert d["confidence"]["reason"] == "no_signal"
        assert BLOCK_TITLE in d["summary"]
        assert d["risk_budget"]["available"] is False  # 无持仓入参 → 风险预算块空态
        assert d["risk_budget"]["reason"] == "缺少持仓市值"
        assert d["discipline"]["available"] is False  # 未传纪律触发条 → 纪律明细块空态
        assert d["discipline"]["reason"] == "未接入纪律信号"
        assert d["settlement"]["available"] is True
        assert d["settlement"]["batches"] == []  # 空账本 → 「暂无结算样本」
        assert d["settlement"]["horizons"] == [5, 20, 60]

    def test_flag_off_returns_disabled_only(self):
        set_feature_enabled(FEATURE_FLAG, False)
        assert is_decision_basis_enabled() is False
        assert build_decision_basis_data() == {"enabled": False}

    def test_no_llm_parameter_signature(self):
        """零 LLM 依赖的结构断言：装配入参只有确定性数据（无上下文/模型/客户端）。"""
        params = inspect.signature(build_decision_basis_data).parameters
        assert set(params) == {
            "holdings_details",
            "total_mv",
            "portfolio_peak_mv",
            "discipline_signals",
            "settlement_decisions",
        }
        assert all(p.default is None for p in params.values())  # 全部可缺省：零参数即可调用

    def test_signal_rows_field_completeness(self, ledger_path):
        """验收①正向：账本有记录时，信号行三组必填字段齐（可空但须显式给出）。"""
        _append(sl.SIGNAL_MARKET_TEMPERATURE, subject="sh000300", detail={"sample_count": 90})
        _append(
            sl.SIGNAL_VALUATION,
            subject="SH600001",
            detail={"pe": None, "pb": None, "sample_count": 365},
        )
        d = build_decision_basis_data()
        names = {s["name"] for s in d["signals"]}
        assert {"市场温度", "估值分位"} <= names
        for s in d["signals"]:
            for key in ("basis", "n_obs", "ic", "monotonic", "discrimination"):
                assert key in s, f"{s['name']} 缺字段 {key}"  # 键必须显式给出（值可为 None）

    def test_valuation_price_proxy_basis(self, ledger_path):
        """估值分位 detail.pe/pb 均为 null ⇒ price_proxy（与账本事实一致）。"""
        _append(sl.SIGNAL_VALUATION, subject="SH600001", detail={"pe": None, "pb": None, "sample_count": 365})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "估值分位")
        assert row["basis"] == "price_proxy"
        assert row["basis_label"] == "价格代理"

    def test_valuation_real_basis_when_pe_present(self, ledger_path):
        """detail.pe 可得 ⇒ valuation_real（口径透明由 basis 表达）。"""
        _append(sl.SIGNAL_VALUATION, subject="SH600001", detail={"pe": 12.3, "pb": None, "sample_count": 365})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "估值分位")
        assert row["basis"] == "valuation_real"


class TestDirectionAxis:
    """验收①负向：basis/n_obs/ic/monotonic 缺任一即不进方向轴。"""

    @pytest.mark.parametrize(
        "overrides",
        [
            {"basis": None},
            {"basis": "unknown"},
            {"n_obs": None},
            {"ic": None},
            {"monotonic": None},
            {"discrimination": DISCRIMINATION_NOT_BACKTESTED},
            {"discrimination": DISCRIMINATION_INSUFFICIENT},
            {"discrimination": DISCRIMINATION_FAILED},
        ],
        ids=[
            "basis-null",
            "basis-unknown",
            "n-obs-null",
            "ic-null",
            "monotonic-null",
            "not-tested",
            "insufficient",
            "failed",
        ],
    )
    def test_missing_field_blocks_axis(self, overrides):
        assert (
            in_direction_axis(
                **{
                    **{
                        "basis": "stat_model",
                        "n_obs": 100,
                        "ic": 0.1,
                        "monotonic": True,
                        "discrimination": DISCRIMINATION_PASSED,
                    },
                    **overrides,
                }
            )
            is False
        )

    def test_complete_fields_enter_axis(self):
        assert (
            in_direction_axis(
                basis="stat_model", n_obs=100, ic=0.1, monotonic=True, discrimination=DISCRIMINATION_PASSED
            )
            is True
        )


class TestDiscriminationStates:
    """验收②：「未回测」「样本不足」如实标注，不填先验值。"""

    def test_not_backtested_note_and_nulls(self, ledger_path):
        _append(sl.SIGNAL_MARKET_TEMPERATURE, subject="sh000300", detail={"sample_count": 90})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "市场温度")
        assert row["discrimination"] == DISCRIMINATION_NOT_BACKTESTED
        assert row["discrimination_label"].startswith("未回测")
        assert row["ic"] is None and row["monotonic"] is None  # 不填先验
        assert "仅参考" in row["discrimination_label"]  # 无效信号显式标注

    def test_insufficient_sample_note(self, ledger_path):
        _append(sl.SIGNAL_FACTOR_CATALOG, subject="portfolio", detail={"computed": 23})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "因子目录")
        assert row["discrimination"] == DISCRIMINATION_INSUFFICIENT
        assert "样本不足" in row["note"] and "n=19" in row["note"]
        assert row["ic"] is None and row["monotonic"] is None
        assert row["in_axis"] is False

    def test_backtest_failed_note(self, ledger_path):
        _append(sl.SIGNAL_VALUATION, subject="SH600001", detail={"pe": None, "pb": None, "sample_count": 365})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "估值分位")
        assert row["discrimination"] == DISCRIMINATION_FAILED
        assert "回测未通过" in row["discrimination_label"]
        assert row["ic"] is not None and row["monotonic"] is not None  # 已回测 → 实测值
        assert row["in_axis"] is False


class TestBacktestRegistry:
    """验收⑥：首批回测结论以模块常量登记，不新增配置键、不写运行时账本。"""

    def test_registry_provenance_fields(self):
        """登记含来源脚本、回测采样日兜底、讨论稿指针（可追溯三要素）。"""
        assert BACKTEST_SOURCE == "scripts/eval-decision-quality.py"
        assert BACKTEST_DATE_FALLBACK and len(BACKTEST_DATE_FALLBACK) == 10
        assert "investment-decision-quality.md" in BACKTEST_REF and "8.1" in BACKTEST_REF

    def test_backtest_run_date_follows_products(self, tmp_path):
        """回测采样日随产物刷新：取最新一份产物的日期，不写死常量。"""
        import os
        from datetime import datetime

        older = tmp_path / "horizon.json"
        older.write_text("{}", encoding="utf-8")
        os.utime(older, (1_700_000_000, 1_700_000_000))
        expected = "2026-03-05"
        stamp = datetime.strptime(expected, "%Y-%m-%d").timestamp()
        newer = tmp_path / "factor-ic.json"
        newer.write_text("{}", encoding="utf-8")
        os.utime(newer, (stamp, stamp))

        assert db.backtest_run_date(tmp_path) == expected

    def test_backtest_run_date_falls_back_without_products(self, tmp_path):
        """产物缺失（新克隆/被清理）→ 回落到归档结论采样日，不抛异常。"""
        assert db.backtest_run_date(tmp_path) == BACKTEST_DATE_FALLBACK

    def test_valuation_entry(self, ledger_path):
        """估值分位：已回测未通过（n=117、ic≈0.0399、monotonic=false）。"""
        _append(sl.SIGNAL_VALUATION, subject="SH600001", detail={"pe": None, "pb": None, "sample_count": 365})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "估值分位")
        entry = BACKTEST_CONCLUSIONS[sl.SIGNAL_VALUATION]
        assert entry["discrimination"] == DISCRIMINATION_FAILED
        assert row["n_backtest"] == entry["n_backtest"] == 117
        assert row["ic"] == pytest.approx(entry["ic"], abs=1e-4)
        assert row["ic"] == pytest.approx(0.04, abs=5e-3)  # ic≈0.04（估值两口径区分度回测代理口径实测 0.0399）
        assert row["monotonic"] is False

    def test_factor_catalog_entry(self, ledger_path):
        """因子目录：样本不足态（ic/monotonic 为 null + note 标注）。"""
        _append(sl.SIGNAL_FACTOR_CATALOG, subject="portfolio", detail={"computed": 23})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "因子目录")
        entry = BACKTEST_CONCLUSIONS[sl.SIGNAL_FACTOR_CATALOG]
        assert row["discrimination"] == entry["discrimination"] == DISCRIMINATION_INSUFFICIENT
        assert row["ic"] is None and row["monotonic"] is None  # 样本不足态不填先验

    def test_unregistered_type_defaults_to_not_backtested(self, ledger_path):
        """未登记结论的类型一律「未回测」——宁可空着不填先验。"""
        _append(sl.SIGNAL_TAIL_RISK, subject="portfolio", detail={"sample_size": 60})
        row = next(s for s in build_decision_basis_data()["signals"] if s["name"] == "尾部风险")
        assert row["discrimination"] == DISCRIMINATION_NOT_BACKTESTED
        assert row["n_backtest"] is None


class TestConfidenceArbitration:
    """验收③：可信度仲裁四枚举（含 reason）——按序短路，首版不产出 high。"""

    def test_empty_signals(self):
        c = arbitrate_confidence([])
        assert (c["level"], c["reason"]) == ("unknown", "no_signal")

    def test_no_valid_signal(self):
        c = arbitrate_confidence([_signal_row(in_axis=False)])
        assert (c["level"], c["reason"]) == ("unknown", "no_valid_signal")
        assert "有效信号 0/1" in c["detail"]  # 空态不得显示可信度高

    def test_all_proxy(self):
        rows = [_signal_row(basis="price_proxy", direction=d) for d in ("bullish", "bullish", "bullish")]
        c = arbitrate_confidence(rows)
        assert (c["level"], c["reason"]) == ("low", "all_proxy")

    def test_split_direction(self):
        rows = [_signal_row(direction="bullish"), _signal_row(direction="bearish"), _signal_row(direction="bullish")]
        c = arbitrate_confidence(rows)
        assert (c["level"], c["reason"]) == ("low", "split_direction")

    def test_insufficient_signals(self):
        rows = [_signal_row(direction="bullish"), _signal_row(direction="bullish")]
        c = arbitrate_confidence(rows)
        assert (c["level"], c["reason"]) == ("low", "insufficient_signals")

    def test_direction_aligned_medium(self):
        rows = [_signal_row(direction="bullish") for _ in range(3)]
        c = arbitrate_confidence(rows)
        assert (c["level"], c["reason"]) == ("medium", "direction_aligned")

    def test_never_high(self):
        """首版不产出 high（防高置信幻觉）——规则路径全覆盖断言。"""
        max_case = arbitrate_confidence([_signal_row(direction="bullish") for _ in range(5)])
        assert max_case["level"] == "medium"
        assert db._LEVEL_LABELS["high"] == "高"  # 展示映射存在，仅规则不产出


class TestZeroLlmDependency:
    """验收④：零 LLM 依赖——enable_llm 两态输出逐字节一致。"""

    def test_enable_llm_two_states_identical(self, ledger_path):
        _append(sl.SIGNAL_MARKET_TEMPERATURE, subject="sh000300", detail={"sample_count": 90})
        with patch("src.python.config.is_enable_llm", return_value=True):
            on = json.dumps(build_decision_basis_data(), sort_keys=True, ensure_ascii=False)
        with patch("src.python.config.is_enable_llm", return_value=False):
            off = json.dumps(build_decision_basis_data(), sort_keys=True, ensure_ascii=False)
        assert on == off


class TestChannelScope:
    """验收⑤：三渠道——HTML/Excel 呈现，CLI/TUI 不出现。"""

    def test_cli_tui_do_not_reference_block(self):
        root = Path(__file__).resolve().parents[3] / "python"
        offenders = []
        for sub in ("cli", "tui"):
            for f in (root / sub).rglob("*.py"):
                if "decision_basis" in f.read_text(encoding="utf-8"):
                    offenders.append(str(f.relative_to(root)))
        assert offenders == [], f"CLI/TUI 不应引用判断依据块: {offenders}"


def _decision(settlements: dict[int, dict], **overrides) -> dict:
    """构造 fold_ledger 形态的决策行（仅结算摘要消费的字段）。"""
    base = {"decision_id": overrides.pop("decision_id", "d1"), "settlements": settlements}
    base.update(overrides)
    return base


class TestSettlementSummary:
    """结算摘要块：最近 5 批 × 5/20/60 视界（未到期显式标注、涨跌域着色）。"""

    def test_empty_ledger(self):
        summary = build_settlement_summary([])
        assert summary["available"] is True
        assert summary["batches"] == []
        assert summary["note"] == "暂无结算样本"
        assert summary["horizons"] == [5, 20, 60]

    def test_pending_horizon_labeled_not_zero(self):
        """验收①：仅 5 日结算时，20/60 日显示「未到期」而不是 0。"""
        summary = build_settlement_summary(
            [_decision({5: {"settle_date": "2026-10-27", "raw_return": -0.02, "bench_return": -0.015}})]
        )
        cells = summary["batches"][0]["cells"]
        assert cells[0]["state"] == "settled"
        assert cells[0]["value_label"] == "-2.00%"
        assert cells[1]["state"] == "pending" and cells[1]["value_label"] == "未到期"
        assert cells[1]["mean_return_pct"] is None
        assert cells[2]["value_label"] == "未到期"

    def test_batch_limit_five(self):
        """验收②：批次上限 5，超出部分不在本块（指向历史决策复盘块）。"""
        decisions = [
            _decision({5: {"settle_date": f"2026-10-{day:02d}", "raw_return": 0.01}}, decision_id=f"d{day}")
            for day in range(1, 8)
        ]
        summary = build_settlement_summary(decisions)
        assert len(summary["batches"]) == 5
        assert [b["date"] for b in summary["batches"]] == [
            "2026-10-07",
            "2026-10-06",
            "2026-10-05",
            "2026-10-04",
            "2026-10-03",
        ]
        assert "历史决策复盘" in summary["note"]

    def test_return_and_excess_aggregation(self):
        summary = build_settlement_summary(
            [
                _decision(
                    {5: {"settle_date": "2026-10-27", "raw_return": -0.02, "bench_return": -0.01}}, decision_id="a"
                ),
                _decision(
                    {5: {"settle_date": "2026-10-27", "raw_return": 0.01, "bench_return": 0.02}}, decision_id="b"
                ),
            ]
        )
        cell = summary["batches"][0]["cells"][0]
        assert summary["batches"][0]["n"] == 2
        assert cell["mean_return_pct"] == pytest.approx(-0.5)
        assert cell["mean_excess_pct"] == pytest.approx(-1.0)
        assert cell["value_label"] == "-0.50%"
        assert cell["excess_label"] == "-1.00%"

    @pytest.mark.parametrize(("raw_return", "color_var"), [(0.02, "--profit"), (-0.02, "--loss"), (0.0, "")])
    def test_gain_loss_color_domain(self, raw_return, color_var):
        """验收④：正负着色走涨跌域变量（红涨绿跌），零值不着色。"""
        summary = build_settlement_summary([_decision({5: {"settle_date": "2026-10-27", "raw_return": raw_return}})])
        assert summary["batches"][0]["cells"][0]["color_var"] == color_var

    def test_excess_missing_falls_back_to_return(self):
        summary = build_settlement_summary([_decision({5: {"settle_date": "2026-10-27", "raw_return": 0.02}})])
        cell = summary["batches"][0]["cells"][0]
        assert cell["excess_label"] == "—"
        assert cell["color_var"] == "--profit"

    def test_summary_reports_batch_count(self, ledger_path):
        data = build_decision_basis_data(
            settlement_decisions=[_decision({5: {"settle_date": "2026-10-27", "raw_return": 0.01}})]
        )
        assert "结算 1 批" in data["summary"]


class TestConstraintsBlock:
    """集中度约束块：开关关闭时数据契约不出现该键（逐字节回滚），开启时按上限标注。"""

    _HOLDINGS = [{"name": "纳指ETF", "code": "513100", "market_value": 600.0}]

    def test_disabled_by_default_keeps_contract_unchanged(self):
        data = build_decision_basis_data(self._HOLDINGS, 1000.0)
        assert "constraints" not in data
        assert "约束标注" not in data["summary"]

    def test_enabled_annotates_breach_and_summary(self):
        from src.python.config.features import reset_feature_flags, set_feature_enabled

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

        from src.python.config.features import reset_feature_flags, set_feature_enabled
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


class TestBothEndsSameSource:
    """双端同源：同一份契约在 HTML/Excel 渲染出的标题与 summary 一致。"""

    def test_title_and_summary_in_both_channels(self, ledger_path):
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        _append(sl.SIGNAL_MARKET_TEMPERATURE, subject="sh000300", detail={"sample_count": 90})
        data = build_decision_basis_data()
        # HTML 端：#decision-basis 块内含标题与 summary
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        # Excel 端：顶部子块含同一标题与 summary
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert data["title"] in text
            assert data["summary"] in text
            assert "信号清单" in text
            assert "信号可信度" in text
            assert "市场温度" in text  # 账本记录双端同现

    def test_risk_budget_rendered_both_channels(self, ledger_path):
        """风险预算三行字段双端同现，且与再平衡块文案互引不重复动作。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data([{"name": "纳指ETF", "code": "513100", "market_value": 600.0}], 1000.0)
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert "风险预算" in text
            assert "单品种权重" in text and "行业权重" in text and "组合回撤" in text
            assert "未配置上限" in text  # 行业无配置键 → 显式标注，不按 0 显示
            assert "超限" in text
            assert "再平衡信号" in text  # 分工互引：超限动作不在本块

    def test_discipline_detail_rendered_both_channels(self, ledger_path):
        """纪律明细双端同现，且与交易纪律块文案互引不重复动作。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data(
            [{"name": "纳指ETF", "code": "513100", "market_value": 900.0}],
            900.0,
            1000.0,
            discipline_signals=[
                {"rule": "止损线 -15%", "name": "纳指ETF", "code": "513100", "value": "-16.0%", "distance_pct": 1.0}
            ],
        )
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert "纪律明细" in text
            assert "止损线 -15%" in text
            assert "超线 1.00%" in text
            assert "下跌段" in text
            assert "交易纪律" in text  # 分工互引：动作不在本块

    def test_settlement_summary_rendered_both_channels(self, ledger_path):
        """结算摘要双端同现：批次/条数/未到期/超额，且指向历史决策复盘块。"""
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data(
            settlement_decisions=[
                _decision({5: {"settle_date": "2026-10-27", "raw_return": -0.02, "bench_return": -0.015}})
            ]
        )
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None
        html_text = block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        for text in (html_text, excel_text):
            assert "结算摘要" in text
            assert "2026-10-27" in text
            assert "-2.00%" in text and "-0.50%" in text
            assert "未到期" in text
            assert "历史决策复盘" in text

    def test_confidence_rendered_both_channels(self, ledger_path):
        from openpyxl import Workbook

        from src.python.report.action_sheet import write_action_sheet
        from src.test.unit.report.test_action_html import _action_data, _render

        data = build_decision_basis_data()  # 空账本 → unknown/no_signal
        block = _render(_action_data(), decision_basis_data=data).find(id="decision-basis")
        assert block is not None and "暂不可判" in block.get_text()
        wb = Workbook()
        ws = wb.active
        assert ws is not None
        write_action_sheet(ws, _action_data(), decision_basis_data=data)
        excel_text = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        assert "暂不可判" in excel_text
