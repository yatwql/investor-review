"""环比比对基线（``load_comparison_baseline``）边缘场景测试。

必须使用 @pytest.mark.edge 标记，存放于 *_edge.py 文件。

覆盖：
  - 周末多次运行 → 周六/周日快照同属上周五交易日，一并跳过
  - 盘前（<9:30）运行 → 本次归属前一交易日，跳过同属该交易日的快照
  - 节假日日历感知 → 非交易日快照的交易日归属按日历回溯（monkeypatch 日历）
  - 损坏快照文件 → 自动跳过，基线顺延到次新有效快照
  - 内部时间戳不可解析的快照 → 不参与基线候选

测试隔离：conftest `_isolate_sensitive_paths` 重定向 HISTORY_SNAPSHOT_DIR；
交易日历走 `offline_external_sources` 离线桩（回空集 → 排除周六日回退），
节假日用例另行 monkeypatch `_get_trading_calendar` 注入精确日历。
"""

from __future__ import annotations

import os

import pytest

import src.python.core.constants as core_constants
from src.python.report.history_snapshot import load_comparison_baseline, save
from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_report,
    pytest.mark.edge,
    pytest.mark.usefixtures("offline_external_sources"),
]


def _save(ts: str, mv: float = 1000.0, namespace: str | None = None) -> None:
    holding = SnapshotHolding(
        code="110011",
        name="基金A",
        shares=10.0,
        cost_price=1.0,
        market_value=mv,
        total_pnl=0.0,
        cost_total=10.0,
    )
    sd = SnapshotData(
        accounts=(AccountSnapshot(account_name="全部", holdings=(holding,)),),
        total_value=mv,
        total_cost=10.0,
        total_pnl=0.0,
        timestamp=ts,
    )
    save(sd, namespace)


class TestTradingDayAttributionEdge:
    """交易日归属边界：周末与盘前。"""

    def test_weekend_runs_skip_to_previous_trading_day(self):
        """周六/周日运行的快照同属上周五交易日 → 一并跳过，基线落到上周四。"""
        _save("20261008T150000")  # 周四
        _save("20261009T210000")  # 周五盘后（交易日=周五）
        _save("20261010T100000")  # 周六（交易日=周五）
        _save("20261011T150000")  # 周日（交易日=周五）

        baseline = load_comparison_baseline("20261011T160000")

        assert baseline is not None
        assert baseline.timestamp == "20261008T150000"

    def test_pre_market_run_belongs_to_previous_trading_day(self):
        """周一盘前（<9:30）运行归属上周五 → 跳过周五盘后快照，基线落到上周四。"""
        _save("20261008T210000")  # 周四盘后
        _save("20261009T210000")  # 周五盘后（交易日=周五，与本次相同）

        baseline = load_comparison_baseline("20261012T080000")

        assert baseline is not None
        assert baseline.timestamp == "20261008T210000"

    def test_holiday_calendar_walks_back_attribution(self, monkeypatch):
        """节假日按日历回溯：假日当天运行与假日前最后一个交易日的快照同交易日 → 跳过。"""
        # 假设 06-25/06-29/06-30 为休市日（仅 06-24、06-26、07-01、07-02 在日历内）
        trading_days = {"2026-06-24", "2026-06-26", "2026-07-01", "2026-07-02"}
        monkeypatch.setattr(
            "src.python.core.trading_calendar._get_trading_calendar",
            lambda: trading_days,
        )
        _save("20260624T150000")
        _save("20260626T150000")  # 交易日 06-26

        # 当次运行落在假日 06-30 → 归属 06-26 → 与 06-26 快照同交易日，跳过
        baseline = load_comparison_baseline("20260630T100000")

        assert baseline is not None
        assert baseline.timestamp == "20260624T150000"


class TestCandidateFaultTolerance:
    """候选快照容错：损坏文件与不可解析时间戳。"""

    def test_corrupt_file_falls_through_to_next(self):
        """更近候选内容损坏 → 跳过，基线顺延到次新有效快照。"""
        _save("20260630T150000")
        os.makedirs(core_constants.HISTORY_SNAPSHOT_DIR, exist_ok=True)
        corrupt_path = os.path.join(core_constants.HISTORY_SNAPSHOT_DIR, "snapshot_20260701T150000.json")
        with open(corrupt_path, "w", encoding="utf-8") as f:
            f.write("{ not valid json ")

        baseline = load_comparison_baseline("20260702T100000")

        assert baseline is not None
        assert baseline.timestamp == "20260630T150000"

    def test_unparseable_internal_timestamp_not_eligible(self):
        """内部时间戳不可解析的快照不参与基线候选（解析失败即无法判交易日）。"""
        _save("20260630T150000")
        _save("garbage-ts")

        baseline = load_comparison_baseline("20260702T100000")

        assert baseline is not None
        assert baseline.timestamp == "20260630T150000"
