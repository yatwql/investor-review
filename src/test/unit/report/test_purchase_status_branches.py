"""report/purchase_status.py 的时效越界、限额小数与未知状态展示分支。

锁住的契约：
  - 超过 7 个交易日的抓取时间一律 ``expired``（过时数据不展示）；
  - 非整数日限额保留两位小数，下一开放日不可解析时原样展示；
  - 未列入四态（开放/限大额/暂停/场内）的真实状态以「⚪ 状态」呈现，不吞掉。
"""

from __future__ import annotations

import pytest

from src.python.report import purchase_status as ps

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_stale_level_expired_beyond_window() -> None:
    assert ps.stale_level("2019-01-02", "2024-06-03") == "expired"


def test_fmt_limit_keeps_two_decimals_for_fractional_limit() -> None:
    assert ps._fmt_limit(1500.5) == "1,500.50"


def test_fmt_next_open_returns_raw_text_when_unparsable() -> None:
    assert ps._fmt_next_open("待定") == "待定"


def test_unknown_status_is_shown_with_neutral_marker() -> None:
    data = {"available": True, "fetched_at": "2024-06-03", "rows": {"000001": {"purchase_status": "限制申购"}}}
    assert ps.format_purchase_status_cell(data, "000001", level="fresh") == "⚪ 限制申购"
