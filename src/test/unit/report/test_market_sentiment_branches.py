"""report/market_sentiment.py 连板梯队成员计数的不可解析载荷分支。

锁住的契约：``item[0].boards`` 不是 dict 时成员数按 0 计（对外呈现为「无梯队数据」而非异常）。
"""

from __future__ import annotations

import pytest

from src.python.report import market_sentiment as ms

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_ladder_member_count_zero_when_boards_not_mapping() -> None:
    assert ms._ladder_member_count({"item": [{"boards": "不可解析"}]}) == 0
