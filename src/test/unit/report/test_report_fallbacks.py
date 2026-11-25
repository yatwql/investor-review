"""报告层的降级分支：数值兜底、回测采样日兜底、信号清单容错、模块结果播报。

断言落在「畸形/缺失输入 → 声明的兜底值或中文提示」上。
"""

from __future__ import annotations

import pytest

from src.python.report import decision_basis, decision_basis_signals
from src.python.report._llm_news import _report_llm_module_results
from src.python.report.fundamental_snapshot_sheet import _yi
from src.python.report.style_factor_sheet import _factor_name

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _Reporter:
    """只收集播报内容的最小 reporter（报告层播报口径断言用）。"""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def info(self, text: str) -> None:
        self.messages.append(("info", text))

    def ok(self, text: str) -> None:
        self.messages.append(("ok", text))

    def warn(self, text: str) -> None:
        self.messages.append(("warn", text))

    def add_error(self, text: str) -> None:
        self.messages.append(("error", text))


class TestNumericFallback:
    """用户手改配置的非数值 → 默认值，不抛错。"""

    def test_non_numeric_text_uses_default(self):
        assert decision_basis._to_float("abc", 1.5) == pytest.approx(1.5)


class TestBacktestRunDateFallback:
    """产物目录不可读（OSError）→ 归档结论采样日兜底。"""

    def test_unreadable_products_dir_falls_back(self, monkeypatch, tmp_path):
        def _boom(_products_dir):
            raise OSError("产物目录不可读")

        monkeypatch.setattr("src.python.core.eval_status.last_eval_date", _boom)

        assert decision_basis_signals.backtest_run_date(tmp_path) == decision_basis_signals.BACKTEST_DATE_FALLBACK


class TestSignalLedgerTolerance:
    """账本记录容错：非字典记录跳过、非整数方向按中性呈现。"""

    def test_non_dict_record_skipped(self, monkeypatch):
        monkeypatch.setattr("src.python.core.signal_ledger.load_signals", lambda: ["坏记录", 42])

        assert decision_basis_signals._latest_signals() == {}

    def test_non_int_direction_rendered_as_neutral(self, monkeypatch):
        signal_type = decision_basis_signals.SIGNAL_TYPES[0]
        monkeypatch.setattr(
            "src.python.core.signal_ledger.load_signals",
            lambda: [{"signal_type": signal_type, "direction": "up", "detail": {}}],
        )

        rows = decision_basis_signals._build_signal_rows()

        assert [row["direction"] for row in rows] == ["neutral"]


class TestSheetValueFallbacks:
    """页签取值兜底：缺失金额写「—」，因子名缺映射时回落原始 key。"""

    def test_missing_amount_written_as_dash(self):
        assert _yi(None) == "—"

    def test_factor_mapping_applied(self):
        assert _factor_name("momentum", {"momentum": "动量"}) == "动量"

    def test_factor_without_mapping_keeps_key(self):
        assert _factor_name("momentum", {"value": "价值"}) == "momentum"


class TestLlmModuleResultReporting:
    """LLM 模块结果播报的四个分支：全空、全跳过、成功。"""

    def test_all_modules_absent_warns_config(self):
        reporter = _Reporter()

        _report_llm_module_results((), (False, False, False, False), reporter)

        assert ("warn", "LLM 均未生成（请检查 LLM 配置）") in reporter.messages

    def test_disabled_modules_reported_as_skipped(self, monkeypatch):
        from src.python.llm import FAIL_REASON_DISABLED

        monkeypatch.setattr(
            "src.python.report.llm_module_info.get_llm_module_failure_reason",
            lambda registry, module_key: FAIL_REASON_DISABLED,
        )
        reporter = _Reporter()

        _report_llm_module_results((None, None, None, None), (False, False, False, False), reporter)

        assert ("info", "所有 LLM 内容已跳过，未调用 LLM") in reporter.messages
        assert len([m for m in reporter.messages if m[0] == "info" and "菜单 S 可切换" in m[1]]) == 4
