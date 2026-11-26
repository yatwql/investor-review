"""tiantian_ranking 残余分支 — 日期采样拒绝面、JS 变量解析失败与评级越界。

锁住的契约：
  - `_sample_date`：``YYYY-MM-DD`` 字符串按 2000 年以上判可信；数值按毫秒时间戳转换，
    转换失败（溢出）返回空串；其它类型返回空串；
  - `_parse_nav_date`：净值序列 JSON 非法 / 非列表 / 空列表 / 末位既非 dict 也非 list
    均返回空串（调用方据此跳过陈旧闸门）；末位为 list 时取首元素作日期；
  - `_days_between`：任一侧日期不可解析返回 None；
  - `_parse_rank_entry`：排名与百分位变量 JSON 非法时只告警，对应项置 ``--``；
  - `_pct_to_rating`：百分位越界（<0 或 >1）返回空评级；
  - `fetch_fund_rankings`：pingzhongdata 取数失败返回 None。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.providers.tiantian_ranking import (
    _days_between,
    _parse_nav_date,
    _parse_rank_entry,
    _pct_to_rating,
    _sample_date,
    fetch_fund_rankings,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


class TestSampleDate:
    """`_sample_date` 的字符串与数值分支。"""

    def test_iso_string_kept_as_is(self):
        """``2024-05-06`` 直接保留（截断到日）。"""
        assert _sample_date("2024-05-06 15:00:00") == "2024-05-06"

    def test_implausible_year_string_rejected(self):
        """年份早于 2000 的字符串判不可信（旧格式里可能是序号）。"""
        assert _sample_date("1999-12-31") == ""

    def test_overflowing_timestamp_returns_empty(self):
        """以毫秒计的数值超出 datetime 范围 → 空串（不抛异常）。"""
        assert _sample_date(1e300) == ""


class TestParseNavDate:
    """`_parse_nav_date` 的载荷异常面。"""

    def test_malformed_series_json_returns_empty(self):
        """净值序列 JSON 非法 → 空串。"""
        assert _parse_nav_date("var Data_netWorthTrend = [oops];") == ""

    def test_empty_series_returns_empty(self):
        """空净值序列 → 空串。"""
        assert _parse_nav_date("var Data_netWorthTrend = [];") == ""

    def test_series_of_lists_uses_first_element(self):
        """旧格式 ``[[x, y], ...]`` 取末位首元素作日期。"""
        assert _parse_nav_date("var Data_netWorthTrend = [[1704067200000, 1.5]];") == "2024-01-01"

    def test_non_list_non_dict_element_returns_empty(self):
        """末位既非 dict 也非 list（标量）→ 空串。"""
        assert _parse_nav_date("var Data_netWorthTrend = [1];") == ""


class TestDaysBetween:
    """`_days_between` 的不可解析输入。"""

    def test_invalid_date_returns_none(self):
        """非法日期（13 月）→ None。"""
        assert _days_between("2024-13-01", "2024-01-01") is None


class TestParseRankEntryDegradation:
    """`_parse_rank_entry` 的 JS 变量解析失败降级。"""

    def test_malformed_rank_json_yields_placeholder(self):
        """排名变量 JSON 非法 → 排名项保持 ``--``。"""
        result = _parse_rank_entry("var Data_rateInSimilarType = [oops];")
        assert result["rank"] == "--"
        assert result["total"] == "--"

    def test_malformed_percentile_json_yields_placeholder(self):
        """百分位变量 JSON 非法 → 百分位项保持 ``--``。"""
        text = (
            'var Data_rateInSimilarType = [{"x": 1704067200000, "y": 12, "sc": 100}];'
            "var Data_rateInSimilarPersent = [oops];"
        )
        result = _parse_rank_entry(text)
        assert result["percentile"] == "--"


class TestPctToRatingBounds:
    """`_pct_to_rating` 的越界拒绝。"""

    @pytest.mark.parametrize("pct", [-0.01, 1.01])
    def test_out_of_range_percentile_returns_empty(self, pct):
        """百分位越界 → 空评级（不套最近档位）。"""
        assert _pct_to_rating(pct) == ""


class TestFetchFundRankingsFailure:
    """`fetch_fund_rankings` 取数失败口径。"""

    def test_missing_payload_returns_none(self):
        """pingzhongdata 取不到 → None。"""
        with patch("src.python.providers.tiantian_ranking._request_pingzhong_data", return_value=None):
            assert fetch_fund_rankings("040046") is None
