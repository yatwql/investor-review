"""环比比对基线（``load_comparison_baseline``）单元测试。

覆盖：
  - 同一交易日多次快照 → 基线跳过同交易日，取更早交易日中最新一份
  - 跨多个交易日 → 取最近的更早交易日那份（不是最旧那份）
  - 仅同一交易日快照 / 空目录 → None（调用方按首次运行口径隐藏环比）
  - ``current_ts`` 不可解析 → 回退 ``load_latest``（退化旧口径，不阻塞环比）
  - 命名空间域隔离 → 基线只读本域

需求 ``R-SNP-01``（生成报告自动创建持仓快照用于环比对比）、``R-OUT-15``
（本期要点对比基准：基线为上一有报告交易日的最新一份报告）。

测试隔离：conftest `_isolate_sensitive_paths` 已将 HISTORY_SNAPSHOT_DIR
重定向到 tmp_path；交易日历走 `offline_external_sources` 离线桩
（回空集 → 排除周六日回退），不发起真实网络请求。
"""

from __future__ import annotations

import pytest

from src.python.report.history_snapshot import load_comparison_baseline, save
from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


def _save(ts: str, mv: float = 1000.0, namespace: str | None = None) -> None:
    """落一份指定时间戳的快照（文件名与内部时间戳同源）。"""
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


class TestLoadComparisonBaseline:
    """跨交易日基线选择主口径。"""

    def test_same_trading_day_snapshots_skipped(self):
        """同日多份快照全部跳过，基线取前一交易日最新一份。"""
        _save("20260701T100000")
        _save("20260701T150000")
        _save("20260702T100000")

        baseline = load_comparison_baseline("20260702T110000")

        assert baseline is not None
        assert baseline.timestamp == "20260701T150000"

    def test_picks_nearest_earlier_day_not_oldest(self):
        """多于两个交易日时取最近的更早交易日那份，而非最旧那份。"""
        _save("20260630T150000")
        _save("20260701T160000")
        _save("20260702T100000")

        baseline = load_comparison_baseline("20260702T110000")

        assert baseline is not None
        assert baseline.timestamp == "20260701T160000"

    def test_none_when_only_same_trading_day(self):
        """仅同一交易日的快照（同日重复运行）→ None，无意义比对不发生。"""
        _save("20260701T100000")
        _save("20260701T150000")

        assert load_comparison_baseline("20260701T160000") is None

    def test_none_on_empty_directory(self):
        """空目录 → None（无快照可比，不触发交易日历取数）。"""
        assert load_comparison_baseline("20260702T100000") is None

    def test_unparseable_current_falls_back_to_latest(self):
        """current_ts 不可解析 → 回退 load_latest（退化旧口径，不阻塞环比）。"""
        _save("20260701T100000")
        _save("20260702T100000")

        baseline = load_comparison_baseline("not-a-timestamp")

        assert baseline is not None
        assert baseline.timestamp == "20260702T100000"

    def test_namespace_domain_scoped(self):
        """基线只读本域：主目录空 + web 域有更早交易日快照 → web 基线可得、主目录 None。"""
        _save("20260701T150000", namespace="web")

        assert load_comparison_baseline("20260702T100000", "web") is not None
        assert load_comparison_baseline("20260702T100000") is None

    def test_baseline_value_reflected_in_diff(self):
        """基线快照参与 HistoryDiff：总市值环比 = 本次 - 基线（跳过同日中间快照）。"""
        from src.python.fetcher.history_diff import HistoryDiff

        _save("20260630T150000", mv=1000.0)
        _save("20260701T150000", mv=9999.0)  # 同交易日更早一份：不得成为基线
        current = SnapshotData(
            accounts=(AccountSnapshot(account_name="全部", holdings=()),),
            total_value=1200.0,
            total_cost=10.0,
            total_pnl=0.0,
            timestamp="20260701T190000",
        )

        baseline = load_comparison_baseline(current.timestamp)
        diff = HistoryDiff.compute(current, baseline)

        assert baseline is not None and baseline.timestamp == "20260630T150000"
        assert diff.is_first_check is False
        assert diff.total_value_diff == pytest.approx(200.0)
