"""持仓变动事件抽取（holding_change_events）测试 — 快照序列 → 事件表契约。

覆盖（迭代验收）：
  - ≥4 期 fixture 差分事件与手算逐条一致（action 与份额差容差 0，覆盖
    新增/加仓/减仓/清仓/不变）
  - 同期重复报告按日去重（后期数不变、不产生同日环比事件）
  - 事件携带区间 [period_from, period_to]（区间即事件的时间精度）
  - 事件 before/after 字段（供区间贡献分解手算对照）
  - 乱序输入自动按 timestamp 升序（差分方向不被输入顺序颠倒）
  - 消费入口 build_holding_change_events 从快照目录读取（读本地零网络）
  - 快照目录只读：抽取前后快照文件 mtime 不变

测试隔离：conftest `_isolate_sensitive_paths` 把 HISTORY_SNAPSHOT_DIR 重定向到
tmp_path，fixture 快照经 save() 构造，不触碰真实 data/history/。
"""

from __future__ import annotations

import os

import pytest

from src.python.analysis.holding_change_events import (
    build_holding_change_events,
    extract_change_events,
)
from src.python.report.history_snapshot import save
from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


# ── 辅助构造 ──────────────────────────────────────────────


def _h(code: str, shares: float, price: float) -> SnapshotHolding:
    return SnapshotHolding(
        code=code,
        name=f"{code}基金",
        shares=shares,
        cost_price=price,
        market_value=shares * price,
        daily_pnl=0.0,
        total_pnl=0.0,
        cost_total=shares * price,
    )


def _snap(ts: str, holdings: list[SnapshotHolding]) -> SnapshotData:
    return SnapshotData(
        accounts=(AccountSnapshot(account_name="全部", holdings=tuple(holdings)),),
        total_value=sum(h.market_value for h in holdings),
        total_cost=sum(h.cost_total for h in holdings),
        total_pnl=0.0,
        timestamp=ts,
    )


def _save(ts: str, holdings: list[SnapshotHolding]) -> None:
    save(_snap(ts, holdings))


def _four_period_sequence() -> list[SnapshotData]:
    """4 期 fixture：覆盖 新增/加仓/减仓/清仓/不变（手算基准）。

    价格恒定（A=10, B=20, C=50, D=30），份额变化即全部事件来源：
      P1→P2: A 1000→1200（加仓 +200）；B/C 不变
      P2→P3: B 500→缺席（清仓 -500）；D 0→300（新增 +300）
      P3→P4: A 1200→900（减仓 -300）；C 200→缺席（清仓 -200）；D 不变
    """
    return [
        _snap("20260105T090000", [_h("A", 1000, 10), _h("B", 500, 20), _h("C", 200, 50)]),
        _snap("20260106T090000", [_h("A", 1200, 10), _h("B", 500, 20), _h("C", 200, 50)]),
        _snap("20260107T090000", [_h("A", 1200, 10), _h("C", 200, 50), _h("D", 300, 30)]),
        _snap("20260108T090000", [_h("A", 900, 10), _h("D", 300, 30)]),
    ]


# ── 差分事件与手算逐条一致 ─────────────────────────────────


def test_four_period_events_match_hand_computed_rows():
    """4 期差分事件逐条与手算一致（action 与份额差容差 0）。"""
    data = extract_change_events(_four_period_sequence())
    assert data["available"] is True
    assert data["period_count"] == 4
    rows = [(e["period_from"], e["period_to"], e["code"], e["action"], e["shares_diff"]) for e in data["events"]]
    assert rows == [
        ("20260105T090000", "20260106T090000", "A", "加仓", 200.0),
        ("20260106T090000", "20260107T090000", "D", "新增", 300.0),
        ("20260106T090000", "20260107T090000", "B", "清仓", -500.0),
        ("20260107T090000", "20260108T090000", "A", "减仓", -300.0),
        ("20260107T090000", "20260108T090000", "C", "清仓", -200.0),
    ]
    assert data["event_count"] == 5
    assert data["indeterminate_count"] == 0


def test_unchanged_holding_not_emitted_as_event():
    """份额不变（同期价格波动只改市值）→ 不出事件。"""
    seq = [
        _snap("20260105T090000", [_h("A", 1000, 10)]),
        _snap("20260106T090000", [_h("A", 1000, 11)]),
    ]
    data = extract_change_events(seq)
    assert data["available"] is True
    assert data["events"] == []
    assert data["event_count"] == 0


# ── 按日去重（同期重复报告） ──────────────────────────────


def test_same_day_duplicate_snapshots_deduplicated():
    """同一自然日两份快照 → 去重后只保留当天最后，期数不增、无同日环比。"""
    seq = [
        _snap("20260105T090000", [_h("A", 1000, 10)]),
        _snap("20260105T150000", [_h("A", 1500, 10)]),  # 同日重复报告
        _snap("20260106T090000", [_h("A", 1500, 10)]),
    ]
    data = extract_change_events(seq)
    assert data["period_count"] == 2
    assert data["period_timestamps"] == ["20260105T150000", "20260106T090000"]
    # 同日两份被折叠为一天 → 只可能有 1 个区间，且 090000→150000 的加仓不出现
    assert data["event_count"] == 0


# ── 区间与 before/after 字段 ──────────────────────────────


def test_event_interval_bounds_are_adjacent_period_timestamps():
    """事件区间 = 相邻两期时间戳（区间即事件的时间精度）。"""
    data = extract_change_events(_four_period_sequence())
    for e in data["events"]:
        assert e["period_from"] < e["period_to"]
    first = data["events"][0]
    assert first["period_from"] == data["period_timestamps"][0]
    assert first["period_to"] == data["period_timestamps"][1]


def test_event_before_after_fields_support_contribution_decomposition():
    """加仓事件携带份额/市值前后值（供贡献分解手算）。"""
    data = extract_change_events(_four_period_sequence())
    add_a = next(e for e in data["events"] if e["code"] == "A" and e["action"] == "加仓")
    assert add_a["shares_before"] == 1000.0
    assert add_a["shares_after"] == 1200.0
    assert add_a["value_before"] == 10000.0
    assert add_a["value_after"] == 12000.0
    assert add_a["value_diff"] == 2000.0
    exit_b = next(e for e in data["events"] if e["code"] == "B")
    assert exit_b["shares_before"] == 500.0
    assert exit_b["shares_after"] == 0.0
    assert exit_b["value_before"] == 10000.0
    assert exit_b["value_after"] == 0.0


# ── 窗口与计数回显 ────────────────────────────────────────


def test_window_and_counts_echoed_in_contract():
    """窗口起止、原始快照数、期数、事件数随契约回显（供报告复盘窗口标注）。"""
    seq = _four_period_sequence()
    data = extract_change_events(seq)
    assert data["snapshot_count"] == 4
    assert data["window_start"] == "20260105T090000"
    assert data["window_end"] == "20260108T090000"
    assert data["period_timestamps"] == [sd.timestamp for sd in seq]
    assert data["reason"] == ""


def test_shuffled_input_sorted_by_timestamp_before_diffing():
    """乱序输入先按 timestamp 升序排序，差分方向不被输入顺序颠倒。"""
    seq = _four_period_sequence()
    forward = extract_change_events(seq)
    backward = extract_change_events(list(reversed(seq)))
    assert backward == forward


# ── 消费入口与只读 ────────────────────────────────────────


def test_build_wrapper_reads_snapshots_from_directory():
    """build_holding_change_events 从快照目录加载（读本地零网络）。"""
    _save("20260105T090000", [_h("A", 1000, 10)])
    _save("20260106T090000", [_h("A", 800, 10)])
    data = build_holding_change_events()
    assert data["available"] is True
    assert data["period_count"] == 2
    assert data["event_count"] == 1
    assert data["events"][0]["action"] == "减仓"
    assert data["events"][0]["shares_diff"] == -200.0


def test_extraction_never_writes_snapshot_files():
    """抽取过程对快照目录零写入：文件集合与 mtime 抽取前后逐项不变。"""
    from src.python.core.constants import HISTORY_SNAPSHOT_DIR

    _save("20260105T090000", [_h("A", 1000, 10)])
    _save("20260106T090000", [_h("A", 800, 10)])

    def _mtimes(directory: str) -> dict[str, float]:
        if not os.path.isdir(directory):
            return {}
        return {
            f: os.path.getmtime(os.path.join(directory, f)) for f in os.listdir(directory) if f.startswith("snapshot_")
        }

    isolated_before = _mtimes(HISTORY_SNAPSHOT_DIR)
    build_holding_change_events()
    assert _mtimes(HISTORY_SNAPSHOT_DIR) == isolated_before


class TestBaselineSwitchGuard:
    """持仓基线切换守卫：相邻快照标的重合度过低 → 跳过该区间事件推断。

    回归背景：截图/演示运行曾把一份 23 只演示持仓写进真实快照目录，真实报告
    在「持仓变动复盘」章把整批演示标的报成「新增」（并连带真实持仓「清仓」）。
    """

    @staticmethod
    def _snap_of(ts: str, prefix: str, n: int) -> SnapshotData:
        return _snap(ts, [_h(f"{prefix}{i}", 100, 10) for i in range(n)])

    def test_disjoint_portfolios_skip_events(self):
        """12 只 vs 23 只且仅 3 只重合（Jaccard≈0.09）→ 整对跳过，不出事件。"""
        prev = self._snap_of("20261014T090000", "A", 12)
        curr = self._snap_of("20261015T223039", "B", 20)
        curr = _snap(
            "20261015T223039",
            list(curr.accounts[0].holdings) + [_h("A0", 100, 10), _h("A1", 100, 10), _h("A2", 100, 10)],
        )

        out = extract_change_events([prev, curr])

        assert out["available"] is True
        assert out["events"] == [], "基线切换不得产出新增/清仓事件"
        assert out["skipped_pairs"] == 1
        assert "基线变化" in out["baseline_note"]
        assert out["baseline_switches"][0]["jaccard"] < 0.5

    def test_normal_change_not_skipped(self):
        """正常加仓/新增（重合度高）不触发守卫。"""
        base = [_h(f"A{i}", 100, 10) for i in range(12)]
        prev = _snap("20261014T090000", base)
        curr = _snap("20261015T090000", base + [_h("NEW", 100, 10)])

        out = extract_change_events([prev, curr])

        assert out["skipped_pairs"] == 0
        assert out["baseline_note"] == ""
        assert any(e["action"] == "新增" and e["code"] == "NEW" for e in out["events"])

    def test_only_switched_pair_is_skipped(self):
        """三期中只有第一对是基线切换 → 只跳该对，其余照常差分。"""
        prev = self._snap_of("20261014T090000", "A", 12)
        mid_holdings = [_h(f"B{i}", 100, 10) for i in range(9)]
        mid = _snap("20261015T090000", mid_holdings)
        nxt = _snap("20261016T090000", mid_holdings + [_h("ADDED", 50, 10)])

        out = extract_change_events([prev, mid, nxt])

        assert out["skipped_pairs"] == 1
        codes = {(e["action"], e["code"]) for e in out["events"]}
        assert ("新增", "ADDED") in codes, "第二对是正常变动，必须照常出事件"
        assert not any(c.startswith("B") for _a, c in codes), "被跳过的区间不得产出事件"

    def test_empty_holdings_pair_not_skipped(self):
        """两侧都空（无代码）时不判基线切换（无标的可比）。"""
        out = extract_change_events([_snap("20261014T090000", []), _snap("20261015T090000", [])])
        assert out["skipped_pairs"] == 0
