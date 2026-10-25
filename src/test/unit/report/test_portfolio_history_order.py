"""历史走势并发取数的**汇总顺序确定性** —— 报告内容必须可复现。

`_fetch_all_histories` 用线程池并发取数，但汇总必须按**输入持仓顺序**而不是
`as_completed` 的完成顺序：完成顺序随网络/线程调度抖动，会让两次同数据报告
①「已纳入走势计算」清单顺序不同（内容不可复现）；
② 逐日市值累加的浮点求和顺序漂移（末位变化，极端时影响四舍五入后的展示值）。
"""

from __future__ import annotations

import random
import time
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_HOLDINGS = [
    ("600900", "长江电力", 100.0),
    ("601398", "工商银行", 200.0),
    ("561910", "电池ETF", 300.0),
    ("011506", "建信高端装备", 400.0),
]


def _bars(code: str) -> list[dict]:
    return [{"date": "2026-07-01", "close": float(code[-1]) + 1.0}]


class TestFetchAllHistoriesOrdering:
    def _calc(self):
        from src.python.report.portfolio_history import PortfolioHistoryCalculator

        return PortfolioHistoryCalculator({})

    def test_result_order_follows_input_not_completion(self):
        """随机完成顺序下，成功清单与 series 顺序仍按输入持仓顺序。"""
        calc = self._calc()
        seen_orders: set[tuple[str, ...]] = set()
        for seed in range(6):
            rng = random.Random(seed)

            def _fake(code, name, shares, days):
                time.sleep(rng.random() * 0.01)  # 打乱完成顺序
                return None if code == "561910" else _bars(code)

            with patch.object(calc, "calculate_for_holding", side_effect=_fake):
                series, count, failed, ok = calc._fetch_all_histories(_HOLDINGS, 30)

            seen_orders.add(tuple(ok))
            assert ok == ["长江电力(600900)", "工商银行(601398)", "建信高端装备(011506)"]
            assert failed == ["电池ETF(561910)"]
            assert count == 3
        assert len(seen_orders) == 1, "多次运行的顺序必须一致（不可随调度抖动）"

    def test_series_order_matches_input(self):
        """`all_series` 按输入顺序排列（浮点逐日累加顺序固定）。"""
        calc = self._calc()

        def _fake(code, name, shares, days):
            time.sleep(random.random() * 0.005)
            return _bars(code)

        with patch.object(calc, "calculate_for_holding", side_effect=_fake):
            series, _count, _failed, _ok = calc._fetch_all_histories(_HOLDINGS, 30)

        closes = [s[0]["close"] for s in series]
        assert closes == [1.0, 9.0, 1.0, 7.0], closes  # 代码末位 +1，按输入持仓顺序
