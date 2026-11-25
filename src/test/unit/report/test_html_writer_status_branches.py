"""report/html_writer_status.py 的评级标签映射与历史走势状态分支。

锁住的契约：
  - ``perf_data`` 中同时具备 code 与 rating_tag 的条目才进入 adjusted_ratings；
  - 历史走势 status=unavailable 记 ``history_source`` 不可用、degraded 记 ``history_degraded``；
  - warnings 按关键词映射到 zero_value / correction / nav_stale 三个键，未命中关键词的告警丢弃。
"""

from __future__ import annotations

import pytest

from src.python.report import html_writer_status as hws
from src.python.report.html_writer_status import _build_data_status_sections, _build_history_data_status

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_adjusted_ratings_keep_only_rows_with_code_and_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, dict[str, str]] = {}

    def _capture(adjusted_ratings: dict[str, str], total_funds: int) -> dict:
        seen["ratings"] = dict(adjusted_ratings)
        return {}

    monkeypatch.setattr(hws, "build_perf_data_status", _capture)
    perf_data = [
        {"code": "000001", "rating_tag": "优秀"},
        {"code": "000002"},
        {"rating_tag": "良好"},
    ]
    _build_data_status_sections({}, {}, None, True, True, perf_data, [], True)
    assert seen["ratings"] == {"000001": "优秀"}


def test_history_unavailable_status_registered() -> None:
    status = _build_history_data_status({"status": "unavailable"})
    assert status["history_source"]["available"] is False


def test_history_degraded_and_warning_keys_registered() -> None:
    status = _build_history_data_status(
        {
            "status": "degraded",
            "warnings": ["某日收盘价为 0", "发现净值修正", "净值滞后 3 日", "其它无关告警"],
        }
    )
    assert status["history_degraded"]["available"] is True
    assert {"history_zero_value", "history_correction", "history_nav_stale"} <= set(status)
    assert "history_other" not in status
