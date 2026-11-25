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

from datetime import date

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
