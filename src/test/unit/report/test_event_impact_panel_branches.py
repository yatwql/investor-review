"""事件窗对照面板的分支契约测试。

锁住的契约：
  - 代码写法变体对空码返回空列表
  - 关键词索引跳过非 dict 的穿透资产、跳过无名称的品种，板块未识别时不建行业键
  - 收益缺失（None/非数值）在视图列显示 "—"
  - 事件日期不可解析的新闻不进窗口跨度计算
  - 行情窗口按最早事件日自适应，全不可解析时取窗口下限

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_event_impact_panel_branches.py -v
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.python.core.models import Holding
from src.python.report import event_impact_panel as eip

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _holding(name: str, code: str) -> Holding:
    return Holding(account="证券", name=name, code=code, shares=100, cost_price=10.0)


class TestCodeVariants:
    """代码写法变体。"""

    def test_blank_code_yields_no_variant(self):
        assert eip._code_variants("   ") == []

    def test_a_share_code_yields_prefixed_variant(self):
        assert eip._code_variants("600519") == ["600519", "sh600519"]


class TestKeywordIndex:
    """关键词索引的建键口径。"""

    def test_non_dict_asset_is_skipped(self):
        index = eip._build_keyword_index([_holding("贵州茅台", "600519")], ["not-a-dict"])

        assert "600519" in index
        assert "not-a-dict" not in index

    def test_unnamed_asset_adds_no_key(self):
        index = eip._build_keyword_index([], [{"codes": ["600519"], "name": ""}])

        # 空名称不建键，但代码变体照常登记
        assert "" not in index
        assert "600519" in index

    def test_unrecognized_sector_adds_no_sector_key(self):
        index = eip._build_keyword_index([_holding("测试股份", "600519")], [])

        assert "测试股份" in index
        assert all(level == "品种" for entries in index.values() for _code, level in entries)


class TestFmtPct:
    """收益格式化的缺失口径。"""

    def test_missing_value_shows_dash(self):
        assert eip._fmt_pct(None) == "—"

    def test_non_numeric_value_shows_dash(self):
        assert eip._fmt_pct("N/A") == "—"

    def test_numeric_value_is_signed_percent(self):
        assert eip._fmt_pct(0.0123) == "+1.23%"


class TestHistoryDaysFor:
    """行情窗口跨度按最早事件日自适应。"""

    def test_unparsable_dates_keep_floor(self, monkeypatch):
        monkeypatch.setattr(eip, "parse_event_date", lambda ctime: None)
        assert eip.history_days_for([{"ctime": "whatever"}]) == eip.HISTORY_DAYS_FLOOR

    def test_unparsable_string_after_parse_keeps_floor(self, monkeypatch):
        monkeypatch.setattr(eip, "parse_event_date", lambda ctime: ctime)
        assert eip.history_days_for([{"ctime": "2026/01/05"}], today=date(2026, 3, 1)) == eip.HISTORY_DAYS_FLOOR

    def test_earliest_event_expands_window(self, monkeypatch):
        monkeypatch.setattr(eip, "parse_event_date", lambda ctime: ctime)
        today = date(2026, 6, 1)

        days = eip.history_days_for([{"ctime": "2026-05-01"}, {"ctime": "2025-06-01"}], today=today)

        # 最早事件日距今 365 天 + 前后窗 + 30 天余量，超过下限
        assert days > eip.HISTORY_DAYS_FLOOR
        assert days <= eip.HISTORY_DAYS_CAP


_ALL_DATES = [
    (date(2026, 8, 24) + timedelta(days=i)).isoformat()
    for i in range(70)
    if (date(2026, 8, 24) + timedelta(days=i)).weekday() < 5
]


def _price_bars() -> list[dict]:
    return [{"date": d, "close": 100.0 + i} for i, d in enumerate(_ALL_DATES)]


def _news(**kw) -> dict:
    base = {
        "title": "工行发布三季度业绩",
        "url": "https://example.com/n1",
        "ctime": "2026-09-15 10:30:00",
        "matched_keywords": ["贵州茅台"],
        "llm_analysis": "[中][利好] 业绩超预期",
    }
    base.update(kw)
    return base


def _event(**kw) -> dict:
    base = {
        "event_date": "2026-09-15",
        "anchor_date": "2026-09-15",
        "title": "标题",
        "code": "600519",
        "matched_keyword": "贵州茅台",
        "polarity": "利好",
        "asset_return": 0.01,
        "excess_return": 0.005,
        "direction": "上行",
        "match": "一致",
    }
    base.update(kw)
    return base


class TestRowCapInsideHitLoop:
    """命中码循环内的行数上限。"""

    def test_second_code_beyond_cap_is_counted(self):
        holdings = [_holding("贵州茅台", "600519")]
        penetrated = [{"name": "贵州茅台", "codes": ["000858"]}]

        result = eip.build_event_rows(
            holdings,
            [_news()],
            penetrated,
            fetch_bars=lambda code: _price_bars(),
            fetch_index=lambda code: _price_bars(),
            benchmark_code_for=lambda row: "sh000300",
            max_rows=1,
        )

        assert len(result["events"]) == 1
        assert result["skipped"]["capped"] == 1, "超出上限的命中码须计入 capped（不得静默丢弃）"


class TestViewSummaryAndDegradedLine:
    """视图摘要行与降级行的聚合口径。"""

    def _contract(self, **kw) -> dict:
        base = {
            "available": True,
            "events": [],
            "degraded": [],
            "match_counts": {},
            "benchmark": {},
            "window": {"before": 5, "after": 5},
            "skipped": {},
            "news_total": 1,
            "polarity_known": 1,
        }
        base.update(kw)
        return base

    def test_anchor_shifted_events_get_summary_note(self):
        view = eip.build_event_impact_view(self._contract(events=[_event(anchor_shifted=True)]))

        assert any("已按行情轴末日对齐" in line for line in view["summary_lines"])

    def test_degraded_line_aggregates_reasons_by_count(self):
        view = eip.build_event_impact_view(
            self._contract(
                degraded=[
                    {"reason": "缺基准"},
                    {"reason": "缺基准"},
                    {"reason": "行情不足"},
                ]
            )
        )

        assert view["degraded_line"] == "降级 3 条（该事件不出行）：缺基准×2、行情不足×1"


class TestPanelBenchmarkWiring:
    """默认基准文本取数的接线与失败降级。"""

    def test_default_benchmark_text_getter_resolves_from_holdings(self, monkeypatch):
        monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_benchmark", lambda code: "沪深300指数收益率")

        contract = eip.build_event_impact_panel(
            [_holding("易方达蓝筹精选混合", "005827")],
            [],
            comparison_indices={"sh000300": "沪深300"},
        )

        assert contract["benchmark"]["code"] == "sh000300"
        assert contract["benchmark"]["source"] == "holdings"

    def test_benchmark_resolution_failure_degrades_to_none(self, monkeypatch):
        def _boom(*_a, **_k):
            raise RuntimeError("resolve boom")

        monkeypatch.setattr("src.python.analysis.benchmark_index_resolver.resolve_benchmark_index", _boom)

        contract = eip.build_event_impact_panel([], [])

        assert contract["benchmark"] is None, "映射失败按缺基准逐条降级，不阻断装配"
        assert contract["degraded_count"] == 0


class TestFooterDegradedLine:
    """Excel 尾部区块的降级行与口径标注。"""

    def test_degraded_line_row_written(self, monkeypatch):
        from openpyxl import Workbook

        view = {
            "available": True,
            "summary_lines": [],
            "event_header": list(eip.EVENT_TABLE_HEADER),
            "event_rows": [],
            "degraded_line": "降级 2 条（该事件不出行）：缺基准×2",
            "limitations_note": eip.LIMITATIONS_NOTE,
            "reason": "",
        }
        monkeypatch.setattr(eip, "build_event_impact_view", lambda _contract: view)
        wb = Workbook()
        ws = wb.active
        assert ws is not None

        eip.write_event_impact_footer(ws, {"available": True}, start_row=2)

        flat = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
        assert any("降级 2 条" in text for text in flat)
        assert any(text == eip.LIMITATIONS_NOTE for text in flat)
