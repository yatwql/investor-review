"""天天基金历史净值解析（`providers/tiantian_nav`）：JS 变量提取与时间戳口径。

覆盖点：
  - 变量缺失 / 非法 JSON / 非数组载荷 → 空列表（不得抛异常打断净值链路）
  - `{"data": [...]}` 包装格式与裸数组格式
  - `x` 的三种取值形态：YYYYMMDD、YYYY-MM-DD、13 位毫秒时间戳（须按北京时间解，
    用 UTC 解会整体前移一天）
  - 单位净值与累计净值按日期合并、去重、升序，双双为 0 的日期丢弃
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.python.core.constants import BEIJING_TZ
from src.python.providers import tiantian_nav

pytestmark = [pytest.mark.unit, pytest.mark.unit_providers]


def _js(var_name: str, payload: object) -> str:
    return f"var {var_name} = {json.dumps(payload)};"


class TestParseNavTrend:
    def test_missing_variable_returns_empty(self):
        assert tiantian_nav._parse_nav_trend("var Data_other = [];", "Data_netWorthTrend") == []

    def test_invalid_json_returns_empty(self):
        text = "var Data_netWorthTrend = [{'x': 1}];"
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == []

    def test_wrapped_data_key_is_unwrapped(self):
        text = _js("Data_netWorthTrend", {"data": [{"x": 20260701, "y": 1.5}]})
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == [{"date": "2026-07-01", "nav": 1.5}]

    def test_wrapped_invalid_json_falls_back_to_empty(self):
        text = 'var Data_netWorthTrend = {"data": [oops};'
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == []

    def test_non_list_payload_returns_empty(self):
        text = _js("Data_netWorthTrend", {"foo": 1})
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == []

    def test_dash_date_passthrough(self):
        text = _js("Data_netWorthTrend", [{"x": "2026-07-01", "y": 2.25}])
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == [{"date": "2026-07-01", "nav": 2.25}]

    def test_millisecond_timestamp_decoded_in_beijing_tz(self):
        ts = int(datetime(2026, 7, 1, 0, 0, tzinfo=BEIJING_TZ).timestamp() * 1000)
        text = _js("Data_netWorthTrend", [{"x": ts, "y": 1.11}])
        bars = tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend")

        assert bars == [{"date": "2026-07-01", "nav": 1.11}], "毫秒时间戳必须按北京时间解，否则整体前移一天"

    def test_skips_non_dict_zero_and_short_entries(self):
        text = _js(
            "Data_netWorthTrend",
            [
                "not-a-dict",
                {"x": 0, "y": 1.0},
                {"x": 20260701, "y": 0},
                {"x": "12345", "y": 1.0},
                {"x": 20260702, "y": 1.2},
            ],
        )
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == [{"date": "2026-07-02", "nav": 1.2}]

    def test_result_sorted_by_date(self):
        text = _js("Data_netWorthTrend", [{"x": 20260703, "y": 3.0}, {"x": 20260701, "y": 1.0}])
        assert [bar["date"] for bar in tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend")] == [
            "2026-07-01",
            "2026-07-03",
        ]


class TestFetchFundNavHistory:
    def test_request_failure_returns_empty(self, monkeypatch):
        monkeypatch.setattr(tiantian_nav, "_request_pingzhong_data", lambda code: None)
        assert tiantian_nav.fetch_fund_nav_history("110020") == []

    def test_merges_net_and_acc_nav_sorted(self, monkeypatch):
        text = ";".join(
            [
                _js("Data_netWorthTrend", [{"x": 20260702, "y": 1.2}, {"x": 20260701, "y": 1.1}]),
                _js("Data_ACWorthTrend", [{"x": 20260702, "y": 3.2}]),
            ]
        )
        monkeypatch.setattr(tiantian_nav, "_request_pingzhong_data", lambda code: text)

        assert tiantian_nav.fetch_fund_nav_history("110020") == [
            {"date": "2026-07-01", "nav": 1.1, "acc_nav": 0.0},
            {"date": "2026-07-02", "nav": 1.2, "acc_nav": 3.2},
        ]

    def test_acc_only_date_keeps_zero_net_nav(self, monkeypatch):
        text = _js("Data_ACWorthTrend", [{"x": 20260701, "y": 2.0}])
        monkeypatch.setattr(tiantian_nav, "_request_pingzhong_data", lambda code: text)

        assert tiantian_nav.fetch_fund_nav_history("110020") == [{"date": "2026-07-01", "nav": 0.0, "acc_nav": 2.0}]

    def test_both_values_non_positive_dropped(self, monkeypatch):
        text = _js("Data_netWorthTrend", [{"x": 20260701, "y": 0}])
        monkeypatch.setattr(tiantian_nav, "_request_pingzhong_data", lambda code: text)

        assert tiantian_nav.fetch_fund_nav_history("110020") == []

    def test_no_nav_variables_returns_empty(self, monkeypatch):
        monkeypatch.setattr(tiantian_nav, "_request_pingzhong_data", lambda code: "var somethingElse = 1;")
        assert tiantian_nav.fetch_fund_nav_history("110020") == []


class TestNavMergeAndPayloadFallbacks:
    """合并期兜底：双重零净值日期丢弃、包装体 data 非数组、超范围时间戳跳过。"""

    def test_date_with_zero_net_and_acc_nav_is_dropped(self, monkeypatch):
        """两侧净值都为 0 的日期（解析层漏网）→ 不产出记录，避免 0 净值污染曲线。"""
        monkeypatch.setattr(tiantian_nav, "_request_pingzhong_data", lambda code: "占位文本")

        def _fake_trend(_text: str, _var: str) -> list[dict]:
            return [{"date": "2026-07-01", "nav": 0.0}]

        monkeypatch.setattr(tiantian_nav, "_parse_nav_trend", _fake_trend)

        assert tiantian_nav.fetch_fund_nav_history("110020") == []

    def test_wrapped_data_not_a_list_returns_empty(self):
        """包装体里 data 不是数组 → 空列表（不得迭代成脏 bar）。"""
        text = _js("Data_netWorthTrend", {"data": {"foo": 1}})
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == []

    def test_out_of_range_millisecond_timestamp_skipped(self):
        """毫秒时间戳超出可表示年份 → 跳过该条，其余条照常解析。"""
        text = _js(
            "Data_netWorthTrend",
            [{"x": 99999999999999999, "y": 1.0}, {"x": 20260701, "y": 1.5}],
        )
        assert tiantian_nav._parse_nav_trend(text, "Data_netWorthTrend") == [{"date": "2026-07-01", "nav": 1.5}]
