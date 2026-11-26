"""bond_yield 残余分支 — akshare 缺失/熔断/版本探测与收益率解析的脏数据口径。

锁住的契约：
  - `_bond_yield_frame`：找不到可用 akshare API 名 → None（不算数据源故障）；
  - `get_risk_free_rate` / `get_risk_free_rate_history`：akshare 已熔断时跳过实时取数，
    历史侧用过期缓存兜底（返回 None 或过期行）；
  - `_fetch_from_akshare`：pandas 缺失 / akshare 未安装 → None；
  - `_fetch_history_from_akshare`：akshare 未安装 → []；解析期异常 → []（记告警）；
    收益率换算后不在 (0, 1) 的点（脏数据/单位错位）逐点跳过。
"""

from __future__ import annotations

import sys

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src.python.fetcher.bond_yield import (
    _bond_yield_frame,
    _fetch_from_akshare,
    _fetch_history_from_akshare,
    get_risk_free_rate,
    get_risk_free_rate_history,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


class TestBondYieldFrame:
    """`_bond_yield_frame` 的 API 探测缺失面。"""

    def test_missing_api_name_returns_none(self, monkeypatch):
        """版本探测找不到可用 API 名 → None（不抛异常、不记熔断）。"""
        monkeypatch.setitem(sys.modules, "akshare", MagicMock())
        with patch("src.python.fetcher.bond_yield._resolve_bond_yield_api", return_value=None):
            assert _bond_yield_frame() is None


class TestRiskFreeRateCircuitBroken:
    """akshare 熔断时实时取数被跳过。"""

    def test_rate_returns_none_when_akshare_broken(self):
        """熔断中且无缓存/配置 → None，且不调起 akshare 取数。"""
        registry = MagicMock()
        registry.is_circuit_broken.return_value = True
        with (
            patch("src.python.core.provider_registry.get_registry", return_value=registry),
            patch("src.python.fetcher.bond_yield._fetch_from_akshare") as fetch,
        ):
            assert get_risk_free_rate(cache_ok=False) is None

        fetch.assert_not_called()

    def test_history_uses_stale_cache_when_akshare_broken(self):
        """熔断中 → 返回过期缓存兜底（rf 日变动仅数 bp，7 天陈旧可容忍）。"""
        registry = MagicMock()
        registry.is_circuit_broken.return_value = True
        stale = [{"date": "2024-01-02", "rate": 0.0174}]
        with (
            patch("src.python.core.provider_registry.get_registry", return_value=registry),
            patch("src.python.fetcher.bond_yield._stale_history_fallback", return_value=stale),
        ):
            assert get_risk_free_rate_history(cache_ok=False) == stale


class TestAkshareAvailability:
    """pandas / akshare 缺席时的降级口径。"""

    def test_missing_pandas_returns_none(self, monkeypatch):
        """pandas 不可导入 → None（无法解析返回值，不抛 ImportError）。"""
        monkeypatch.setitem(sys.modules, "pandas", None)
        assert _fetch_from_akshare() is None

    def test_missing_akshare_returns_none(self):
        """akshare 未安装（find_spec 为 None）→ None。"""
        with patch("src.python.fetcher.bond_yield.find_spec", return_value=None):
            assert _fetch_from_akshare() is None

    def test_history_missing_akshare_returns_empty(self):
        """akshare 未安装 → 历史序列空列表。"""
        with patch("src.python.fetcher.bond_yield.find_spec", return_value=None):
            assert _fetch_history_from_akshare() == []


class TestHistoryParsingDegradation:
    """历史收益率逐点解析的脏数据与异常口径。"""

    def test_out_of_range_point_skipped(self):
        """换算后不在 (0,1) 的点（如 100%）逐点跳过，其余点保留。"""
        frame = pd.DataFrame(
            {
                "日期": ["2024-01-02", "2024-01-03", "2024-01-04"],
                "中国10年期国债收益率": [1.74, 100.0, None],
            }
        )
        with patch("src.python.fetcher.bond_yield._bond_yield_frame", return_value=frame):
            rows = _fetch_history_from_akshare()

        assert [row["date"] for row in rows] == ["2024-01-02"]
        assert rows[0]["rate"] == pytest.approx(0.0174)

    def test_parse_exception_returns_empty(self):
        """解析期异常（iterrows 抛错）→ 空列表，不外抛。"""
        frame = MagicMock()
        frame.empty = False
        frame.columns = ["日期", "中国10年期国债收益率"]
        frame.iterrows.side_effect = RuntimeError("broken frame")
        with patch("src.python.fetcher.bond_yield._bond_yield_frame", return_value=frame):
            assert _fetch_history_from_akshare() == []
