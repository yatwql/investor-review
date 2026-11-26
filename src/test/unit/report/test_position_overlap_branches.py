"""report/position_overlap.py 的空集与空标的行残差分支。

锁住的契约：
  - 任一集合为空时 Jaccard / 重叠比例均为 0.0（不除零）；
  - 既无代码又无名称的持仓记录不参与重合度计算。
"""

from __future__ import annotations

import pytest

from src.python.report import position_overlap as po

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_jaccard_zero_when_one_side_is_empty() -> None:
    assert po._jaccard_similarity(set(), {"600519"}) == 0.0


def test_overlap_ratio_zero_when_one_side_is_empty() -> None:
    assert po._overlap_ratio({"600519"}, set()) == 0.0


def test_blank_holding_row_is_skipped_from_overlap() -> None:
    result = po.compute_overlap_matrix(
        {
            "000001": [{"code": "600519", "name": "贵州茅台", "ratio": 5.0}, {"code": " ", "name": ""}],
            "000002": [{"code": "600519", "name": "贵州茅台", "ratio": 3.0}],
        }
    )
    assert result["pairs"][0]["common_count"] == 1
    assert result["pairs"][0]["common_stocks"] == [{"name": "贵州茅台", "code": "600519"}]
