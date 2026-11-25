"""report/_fund_rating.py 的超额收益阈值兜底与评分追加分支。

锁住的契约：
  - 配置里的阈值不可转 int 时回退内置默认值（80 / 40）；
  - 评级说明命中「超额收益」评分时追加「（超额收益评分N）」并即刻返回；
  - 评分落在双向阈值之间时评级维持同类排名结果不变。
"""

from __future__ import annotations

import pytest

from src.python.report import _fund_rating as fr

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_excess_thresholds_fall_back_on_unparsable_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.python.config.get_config",
        lambda: {"performance_evaluation": {"excess_threshold_up": "高配"}},
    )
    assert fr._get_excess_thresholds() == (
        fr._DEFAULT_EXCESS_THRESHOLD_UP,
        fr._DEFAULT_EXCESS_THRESHOLD_DOWN,
    )


def test_rating_comment_appends_excess_score() -> None:
    comment = fr._calc_rating_comment("良好", {"categories": ["选股", "超额收益"], "data": [70, 85]}, "沪深300")
    assert comment.endswith("（超额收益评分85）")
    assert "基准：沪深300" not in comment


def test_adjust_rating_keeps_peer_rating_for_middle_score() -> None:
    adjusted = fr._adjust_rating_with_benchmark("稳定", {"categories": ["超额收益"], "data": [60]})
    assert adjusted == "稳定"


def test_adjust_rating_keeps_peer_rating_for_non_numeric_score() -> None:
    adjusted = fr._adjust_rating_with_benchmark("良好", {"categories": ["超额收益"], "data": ["高"]})
    assert adjusted == "良好"
