"""core 域残余分支：默认持久化路径 / 子进程错误行 / 周末午休 / 名称包含 / 决策头非对象。

补齐的都是只在「环境边界」（周末、无缓存目录）或「上游给了非合约数据」时才走到
的分支；每条都断言对外可见结果（返回值或异常），不依赖日志文案。
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from src.python.core import decision_header, holding_status, holdings_editor, market_hours, v8_subprocess
from src.python.core import degradation
from src.python.core.constants import BEIJING_TZ
from src.python.schemas.datasource_fields import FinancialReportFields, QuoteFields
from src.python.schemas.history import DiffSummary, HoldingDiff
from src.test._script_loader import load_module_file

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestDefaultPersistPath:
    def test_state_dir_sits_beside_cache_dir(self, monkeypatch, tmp_path):
        # 会话级隔离 fixture 把真实 `_default_persist_path` 换成了 tmp 版 lambda，
        # 故取同一源文件的**未打补丁实例**来跑真身（覆盖的数据仍记在这个文件上）
        fresh = load_module_file(Path(degradation.__file__), "degradation_unpatched")
        monkeypatch.delitem(sys.modules, "degradation_unpatched", raising=False)
        monkeypatch.setattr(fresh, "get_cache_dir", lambda: str(tmp_path / "cache"))

        assert fresh._default_persist_path() == str(tmp_path / "state" / ".degradation_state.json")


class TestV8ChildErrorLine:
    def test_unparsable_error_line_becomes_unknown_source_failure(self):
        proc = subprocess.CompletedProcess(
            args=["python", "-c", ""],
            returncode=0,
            stdout=f"{v8_subprocess._ERROR_MARKER}这不是 JSON\n",
            stderr="",
        )

        with pytest.raises(v8_subprocess.V8SourceError) as excinfo:
            v8_subprocess._parse_child_output(proc)

        assert excinfo.value.reason == "source_failed"
        assert "unknown" in str(excinfo.value)


class _SaturdayDatetime:
    """把 ``datetime.now(tz)`` 钉在周六正午的替身。"""

    @staticmethod
    def now(_tz=None) -> datetime:
        return datetime(2026, 5, 30, 12, 0, tzinfo=BEIJING_TZ)


class TestMiddayBreakOnWeekend:
    def test_weekend_is_never_midday_break(self, monkeypatch):
        monkeypatch.setattr(market_hours, "datetime", _SaturdayDatetime)

        assert market_hours.is_midday_break() is False


class TestAmbiguousPriceKindGuards:
    def test_exchange_fund_predicate_wins_over_overlap_zone(self, monkeypatch):
        monkeypatch.setattr(holdings_editor, "is_six_digit_code", lambda _c: True)
        monkeypatch.setattr(holdings_editor, "is_otc_code_overlap", lambda _c: True)
        monkeypatch.setattr(holdings_editor, "is_exchange_fund_code", lambda _c: True)

        assert holdings_editor.ambiguous_price_kind("001234", "某ETF") is False


class TestNamesMatchShortNameInside:
    def test_short_market_name_inside_holding_name_matches(self):
        assert holding_status.names_match("贵州茅台酒业集团", "酒业") is True


class TestStructuredHeaderNonObjectPayload:
    def test_non_object_payload_falls_back_to_none(self, monkeypatch):
        monkeypatch.setattr(decision_header, "_extract_header_payload", lambda _text: "[1, 2]")

        assert decision_header.parse_structured_header("决策头：[1, 2]") is None


class TestDatasourceFieldsSerialization:
    def test_quote_fields_to_dict_lists_every_field(self):
        payload = QuoteFields(code="600519", price=1680.0).to_dict()

        assert payload["code"] == "600519"
        assert set(payload) == set(QuoteFields().__dict__)

    def test_financial_report_fields_to_dict_lists_every_field(self):
        payload = FinancialReportFields(doc_id=7, title="年报").to_dict()

        assert payload["doc_id"] == 7
        assert set(payload) == set(FinancialReportFields().__dict__)


class TestDiffSummaryTrim:
    def test_trim_marks_trimmed_and_keeps_portfolio_level_diffs(self):
        summary = DiffSummary(
            total_value_diff=1234.5,
            days_since_last_report=3,
            added=(HoldingDiff(code="600519", name="贵州茅台", action="新增"),),
        )

        trimmed = summary.trim(top_n=0)

        assert trimmed.trimmed is True
        assert trimmed.total_value_diff == 1234.5
        assert trimmed.days_since_last_report == 3
