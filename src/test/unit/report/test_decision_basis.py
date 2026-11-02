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
    BACKTEST_DATE,
    BACKTEST_REF,
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
        for key in ("risk_budget", "discipline", "settlement"):
            assert d[key] == {}  # 字段先立：后续轮次逐节填充

    def test_flag_off_returns_disabled_only(self):
        set_feature_enabled(FEATURE_FLAG, False)
        assert is_decision_basis_enabled() is False
        assert build_decision_basis_data() == {"enabled": False}

    def test_zero_parameter_signature(self):
        """零 LLM 依赖的结构断言：装配函数无参数（不接上下文/模型/LLM 客户端）。"""
        assert list(inspect.signature(build_decision_basis_data).parameters) == []

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
        """登记含来源脚本、回测日期、讨论稿指针（可追溯三要素）。"""
        assert BACKTEST_SOURCE == "scripts/eval-decision-quality.py"
        assert BACKTEST_DATE and len(BACKTEST_DATE) == 10
        assert "investment-decision-quality.md" in BACKTEST_REF and "8.1" in BACKTEST_REF

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
