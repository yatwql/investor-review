"""report/benchmark.py 归一化的载荷过滤与短样本分支。

锁住的契约：
  - 缺 ``date`` 的指数 bar 被丢弃，不参与对齐；
  - 指数数据整段早于组合起算日时该指数跳过（返回空结果）；
  - 对齐后仅 1 个数据点时年化波动率按 0.0 计（不做单点标准差）。
"""

from __future__ import annotations

import pytest

from src.python.report.benchmark import normalize_benchmarks

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_bar_without_date_is_dropped() -> None:
    result = normalize_benchmarks(
        [{"date": "2024-01-02"}, {"date": "2024-01-03"}],
        {
            "HS300": {
                "name": "沪深300",
                "bars": [
                    {"close": 99.0},
                    {"date": "2024-01-02", "close": 100.0},
                    {"date": "2024-01-03", "close": 101.0},
                    {"date": "2024-01-04", "close": 102.0},
                ],
            }
        },
    )
    assert [bar["value"] for bar in result[0]["bars"]] == [100.0, 101.0]
    assert result[0]["data_start"] == "2024-01-02"


def test_benchmark_ending_before_portfolio_start_is_skipped() -> None:
    result = normalize_benchmarks(
        [{"date": "2024-02-01"}, {"date": "2024-02-02"}],
        {"HS300": {"name": "沪深300", "bars": [{"date": "2024-01-02", "close": 100.0}]}},
    )
    assert result == []


def test_single_aligned_point_has_zero_annualized_volatility() -> None:
    result = normalize_benchmarks(
        [{"date": "2024-01-03"}],
        {"HS300": {"name": "沪深300", "bars": [{"date": "2024-01-03", "close": 101.0}]}},
    )
    assert result[0]["annualized_volatility"] == 0.0
    assert result[0]["total_return_pct"] == 0.0
