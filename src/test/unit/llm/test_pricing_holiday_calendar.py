# -*- coding: utf-8 -*-
"""计价闲时日判定只读已缓存交易日历（回归：假日判定不得触网）。

为什么需要：``pricing._is_holiday`` 曾是「工作日 → ``trading_calendar._is_trading_day``」，
该函数在日历缓存缺失时**会去 akshare 取数**。计价发生在每次 LLM 调用收尾，为此拉一次
远端日历既慢又与本次调用无关；更直接的症状是无日历缓存的机器 / CI 上整批 LLM 缓存
用例被网络守卫拦成硬失败（守卫异常继承 ``BaseException``，计价的 ``except Exception``
降级口吞不掉）。故此处把「只读缓存、不触网」钉成用例：一旦有人改回取数路径即红。
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from src.python.llm import pricing

# `unit_core` 横切标记：日历读取路径属核心基础设施行为，且该缺陷会直接打红 P0
# `dev-verify`（后者的选择面不含 `unit_llm`），故须随 `dev-verify` 跑。
pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.unit_core]

_WEEKDAY = datetime(2026, 10, 9, 10, 0)  # 周五（工作日，可能落在法定节假日）
_MONDAY = datetime(2026, 10, 12, 10, 0)
_SATURDAY = datetime(2026, 10, 10, 10, 0)


def _cached_days(days: list[str]):
    return patch("src.python.core.trading_calendar.cached_trading_days", return_value=days)


class TestHolidayJudgementIsCacheOnly:
    """``_is_holiday`` 只读缓存日历，绝不触发取数。"""

    def test_no_calendar_cache_does_not_fetch(self):
        """无日历缓存：判为「非节假日」，且不调用取数入口（不触网）。"""
        with _cached_days([]):
            with patch("src.python.core.trading_calendar._get_trading_calendar") as fetch:
                assert pricing._is_holiday(_WEEKDAY) is False
        assert fetch.call_count == 0

    def test_cached_calendar_marks_non_trading_weekday_as_holiday(self):
        """日历里有缓存时：工作日不在交易日集合 → 判定为法定节假日。"""
        with _cached_days(["2026-10-09"]):
            assert pricing._is_holiday(_MONDAY) is True
            assert pricing._is_holiday(_WEEKDAY) is False

    def test_weekend_never_consults_calendar(self):
        """周末由 weekend_always_idle 单独处理：不查日历、恒非节假日。"""
        with patch("src.python.core.trading_calendar.cached_trading_days") as days:
            assert pricing._is_holiday(_SATURDAY) is False
        assert days.call_count == 0

    def test_calendar_error_degrades_without_raising(self):
        """日历读取异常时降级为「非节假日」，不让计价报错。"""
        with patch("src.python.core.trading_calendar.cached_trading_days", side_effect=OSError("io")):
            assert pricing._is_holiday(_WEEKDAY) is False
