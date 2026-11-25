"""report/category.py 的成本分档兜底与分红数据降级分支。

锁住的契约：
  - 只有无市价份额、低成本/高成本档均为 0 时，档位标签才是「未分档」；
  - 分红取数异常时返回空表且 success=False，并在数据源矩阵如实登记为失败；
  - 分红状态登记自身失败只记 debug，不阻断分类页签生成。
"""

from __future__ import annotations

import pytest

from src.python.core.models import Holding
from src.python.report import category as cat

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def test_tier_label_unpriced_only_is_unpriced() -> None:
    buckets = {"low": {"shares": 0.0}, "high": {"shares": 0.0}, "unpriced": {"shares": 300.0}}
    assert cat._tier_label(buckets) == "未分档"


def test_load_dividend_data_degrades_on_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses: list[tuple[bool, str]] = []

    def _boom(_codes: list[str]) -> dict:
        raise RuntimeError("分红源不可达")

    monkeypatch.setattr("src.python.fetcher.akshare.get_dividend_data", _boom)
    monkeypatch.setattr(cat, "_record_dividend_status", lambda ok, msg="": statuses.append((ok, msg)))

    holdings = [Holding(account="证券账户", name="长江电力", code="600900", shares=100, cost_price=10.0)]
    data, success = cat._load_dividend_data(holdings)

    assert (data, success) == ({}, False)
    assert statuses == [(False, "分红数据加载异常")]


def test_record_dividend_status_swallows_tracker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    messages: list[str] = []

    def _boom() -> None:
        raise RuntimeError("tracker 不可用")

    monkeypatch.setattr("src.python.core.degradation.get_tracker", _boom)
    monkeypatch.setattr(cat.logger, "debug", lambda msg, *a, **kw: messages.append(msg))

    cat._record_dividend_status(False, "源不可达")

    assert any("分红状态登记失败" in msg for msg in messages)
