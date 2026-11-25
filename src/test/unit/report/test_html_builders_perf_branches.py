"""基金业绩条目构建的分支覆盖：预取排名 vs 单只取数、有/无明细行的盈亏列、收益率解析。

`_build_single_perf_item` 的四个输入组合（排名来源 × 明细行有无）决定返回字典的
盈亏字符串、收益率字符串与原始值，是 HTML 业绩表的唯一数据源；两个纯解析函数
（`_parse_return_raw` / `_format_return_pct`）的非法值降级同样在此锁定。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.python.core.models import Holding
from src.python.report import html_builders
from src.python.report.html_builders import (
    _build_single_perf_item,
    _format_return_pct,
    _parse_return_raw,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class _Progress:
    """ProgressReporter 的最小事实现（只接 info 调用）。"""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, text: str) -> None:
        self.messages.append(text)


def _fund() -> Holding:
    return Holding(account="测试账户", name="易方达蓝筹精选混合", code="005827", shares=1000, cost_price=2.5)


def _rankings() -> dict:
    return {
        "rankings": {
            "近3月": {"return": 3.1},
            "近6月": {"return": "--"},
            "近1年": {"return": -8.4},
            "同类排名": {"rank": 155, "total": 362},
        },
        "rating": "优秀",
    }


class TestBuildSinglePerfItem:
    def test_prefetched_rankings_with_detail_row(self, monkeypatch):
        """预取命中时不调单只取数接口；有明细行 → 盈亏带正号、收益率 ×100 显示。"""
        called: list[str] = []

        def _no_fetch(code):
            called.append(code)
            return None

        monkeypatch.setattr(html_builders, "fetch_fund_rankings", _no_fetch)
        monkeypatch.setattr(html_builders, "fetch_fund_benchmark", lambda code: "沪深300")
        detail = SimpleNamespace(code="005827", profit=1234.5, profit_rate=0.1234)

        item = _build_single_perf_item(
            1,
            _fund(),
            {"005827": detail},
            _Progress(),
            3,
            prefetched_rankings={"005827": _rankings()},
        )

        assert called == []  # 预取已覆盖，不再逐只取数
        assert item["profit"] == "+1,234.50"
        assert item["profit_rate"] == "+12.34%"
        assert item["profit_raw"] == 1234.5
        assert item["syl_3m"] == "+3.10%"
        assert item["syl_3m_raw"] == 3.1
        assert item["syl_6m"] == "--"  # 上游 "--" 不参与着色
        assert item["syl_1y_raw"] == -8.4
        assert item["rating"] == "优秀 持续跑赢基准，超额收益显著"
        assert item["rank"] == "155/362"
        assert item["benchmark"] == "沪深300"

    def test_missing_detail_row_falls_back_to_placeholders(self, monkeypatch):
        """无明细行（新股/未核算）→ 盈亏与盈亏率写 '--'，原始值归零。"""
        monkeypatch.setattr(html_builders, "fetch_fund_rankings", lambda code: _rankings())
        monkeypatch.setattr(html_builders, "fetch_fund_benchmark", lambda code: "--")
        progress = _Progress()

        item = _build_single_perf_item(2, _fund(), {}, progress, 5)

        assert item["profit"] == "--"
        assert item["profit_rate"] == "--"
        assert item["profit_raw"] == 0.0
        assert item["profit_rate_raw"] == 0.0
        assert item["rating"] == "优秀 持续跑赢基准，超额收益显著"
        # 进度行带「序号/总数」与基金名
        assert progress.messages == ["基金业绩 [2/5]: 易方达蓝筹精选混合"]

    def test_fetch_failure_degrades_all_return_columns(self, monkeypatch):
        monkeypatch.setattr(html_builders, "fetch_fund_rankings", lambda code: None)
        monkeypatch.setattr(html_builders, "fetch_fund_benchmark", lambda code: "--")

        item = _build_single_perf_item(1, _fund(), {}, _Progress(), 1)

        assert item["syl_3m"] == "--"
        assert item["syl_6m"] == "--"
        assert item["syl_1y"] == "--"
        assert item["syl_3m_raw"] is None
        assert item["rating"] == "--"
        assert item["rating_tag"] == ""
        assert item["rank"] == "--"


class TestReturnParsers:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [(None, None), ("--", None), ("5.23", 5.23), (5, 5.0), ("abc", None), ([1], None)],
    )
    def test_parse_return_raw(self, value, expected):
        assert _parse_return_raw(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(None, "--"), ("--", "--"), ("5.23", "+5.23%"), (-2.1, "-2.10%"), ("abc", "--"), ({"a": 1}, "--")],
    )
    def test_format_return_pct(self, value, expected):
        assert _format_return_pct(value) == expected
