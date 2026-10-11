"""危机区间标注模块测试 — 静态日期表 + 区间重叠 + 区间回撤/恢复耗时。

覆盖场景：
  - build_crisis_annotation 数据不可用占位（None / status=unavailable / bars 空）
  - 窗口与 2018/2020 区间重叠 → in_range + 区间最大回撤 + 最深日 + 恢复耗时
  - 窗口同时跨越 2018 + 2020 → 两个区间均正确标注并统计
  - 窗口不重叠 → 全部 in_range=False（显式"无历史区间"依据）
  - 最深日临近窗口末尾未恢复 → recovered=False / recovery_days=None
  - data_end 覆盖与缺失回退到 bars 末日期；恢复扫描不受窗口截断限制
  - 重叠窗口内无 bar / 非法日期 / 非正值净值 的防御分支

设计约束：纯标准库、无网络请求（危机日期为静态历史事实表）。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.python.analysis.crisis_annotation import (
    CRISIS_INTERVALS,
    _overlap_interval,
    _parse_window,
    build_crisis_annotation,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]
pytestmark.append(pytest.mark.usefixtures("offline_external_sources"))


def _bars(pairs: list[tuple[str, float]]) -> list[dict]:
    """从 (date, total_value) 列表生成 bars（升序）。"""
    return [{"date": d, "total_value": float(v)} for d, v in pairs]


def _history(bars: list[dict], data_start: str, data_end: str | None = None) -> dict:
    """构造带窗口的 history_data mock。"""
    h: dict = {"status": "ok", "bars": bars, "data_start": data_start}
    if data_end is not None:
        h["data_end"] = data_end
    return h


# 2018 贸易摩擦重叠窗口：区间内 100 → 80 → 70（最深日）→ 100（恢复）→ 110
_2018_BARS = _bars(
    [
        ("2018-06-15", 100.0),  # 区间起点（2018-06-19）之前，不参与区间统计
        ("2018-06-20", 100.0),
        ("2018-07-05", 80.0),
        ("2018-08-01", 70.0),  # 最深日，回撤 30%
        ("2018-09-01", 100.0),  # 恢复至峰值
        ("2018-12-31", 110.0),
    ]
)

# 2020 疫情重叠窗口：区间内 100 → 80 → 60（最深日）→ 100（恢复）→ 120
_2020_BARS = _bars(
    [
        ("2020-02-10", 100.0),
        ("2020-02-25", 80.0),
        ("2020-03-05", 60.0),  # 最深日，回撤 40%
        ("2020-03-20", 100.0),  # 恢复至峰值
        ("2020-06-01", 120.0),
    ]
)


def _interval(contract: dict, name: str) -> dict:
    """按名称取出危机区间条目。"""
    return next(it for it in contract["intervals"] if it["name"] == name)


class TestBuildCrisisAnnotation:
    """build_crisis_annotation 数据可用性与区间标注。"""

    def test_none_returns_unavailable(self):
        """history_data=None → available=False 占位，4 个区间全 in_range=False。"""
        c = build_crisis_annotation(None)
        assert c["available"] is False
        assert len(c["intervals"]) == len(CRISIS_INTERVALS)
        assert all(it["in_range"] is False for it in c["intervals"])
        assert all(it["interval_drawdown_pct"] is None for it in c["intervals"])

    def test_status_unavailable_returns_unavailable(self):
        """status=unavailable → available=False 占位。"""
        c = build_crisis_annotation({"status": "unavailable", "bars": []})
        assert c["available"] is False

    def test_empty_bars_returns_unavailable(self):
        """bars 为空 → available=False 占位。"""
        c = build_crisis_annotation({"status": "ok", "bars": []})
        assert c["available"] is False

    def test_available_with_no_overlap_window(self):
        """窗口（2026）与全部危机区间不重叠 → available=True，全部 in_range=False。"""
        bars = _bars([("2026-01-05", 100.0), ("2026-06-01", 120.0)])
        c = build_crisis_annotation(_history(bars, "2026-01-01", "2026-12-31"))
        assert c["available"] is True
        assert all(it["in_range"] is False for it in c["intervals"])
        assert all(it["interval_drawdown_pct"] is None for it in c["intervals"])

    def test_2018_interval_annotated_with_stats(self):
        """窗口与 2018 贸易摩擦重叠 → 区间回撤 30.0%、最深日、恢复 31 天、已恢复。"""
        c = build_crisis_annotation(_history(_2018_BARS, "2018-06-15", "2018-12-31"))
        it = _interval(c, "2018 贸易摩擦")
        assert it["in_range"] is True
        assert it["interval_drawdown_pct"] == 30.0
        assert it["trough_date"] == "2018-08-01"
        assert it["recovery_days"] == 22  # 恢复耗时按交易日计（自然日 31 天中扣除周末）
        assert it["recovered"] is True
        # 其余区间不重叠
        assert _interval(c, "2020 疫情冲击")["in_range"] is False
        assert _interval(c, "2015 股灾")["in_range"] is False

    def test_2020_interval_annotated_with_stats(self):
        """窗口与 2020 疫情重叠 → 区间回撤 40.0%、最深日、恢复 15 天、已恢复。"""
        c = build_crisis_annotation(_history(_2020_BARS, "2020-02-01", "2020-12-31"))
        it = _interval(c, "2020 疫情冲击")
        assert it["in_range"] is True
        assert it["interval_drawdown_pct"] == 40.0
        assert it["trough_date"] == "2020-03-05"
        assert it["recovery_days"] == 11  # 按交易日计
        assert it["recovered"] is True

    def test_window_spans_2018_and_2020_both_annotated(self):
        """窗口同时跨越 2018 + 2020 → 两个区间均 in_range 且统计正确（行为断言）。"""
        bars = _2018_BARS + _bars([("2019-06-03", 100.0)]) + _2020_BARS
        c = build_crisis_annotation(_history(bars, "2018-06-15", "2020-12-31"))
        it18 = _interval(c, "2018 贸易摩擦")
        it20 = _interval(c, "2020 疫情冲击")
        assert it18["in_range"] is True
        assert it18["interval_drawdown_pct"] == 30.0
        assert it20["in_range"] is True
        assert it20["interval_drawdown_pct"] == 40.0
        assert _interval(c, "2015 股灾")["in_range"] is False
        assert _interval(c, "2022 市场调整")["in_range"] is False

    def test_still_in_drawdown_at_window_end(self):
        """最深日后净值未回到峰值 → recovered=False / recovery_days=None。"""
        bars = _bars(
            [
                ("2018-06-20", 100.0),
                ("2018-07-05", 80.0),
                ("2018-08-01", 70.0),  # 最深日
                ("2018-12-31", 70.0),  # 窗口末尾仍在低谷
            ]
        )
        c = build_crisis_annotation(_history(bars, "2018-06-15", "2018-12-31"))
        it = _interval(c, "2018 贸易摩擦")
        assert it["in_range"] is True
        assert it["interval_drawdown_pct"] == 30.0
        assert it["trough_date"] == "2018-08-01"
        assert it["recovery_days"] is None
        assert it["recovered"] is False

    def test_data_end_override_and_recovery_scan_beyond_window(self):
        """data_end 提前截断报告窗口 → 区间统计以窗口内 bar 为准，恢复扫描仍全量。"""
        # 窗口只到 2018-08-05，但恢复（2018-09-01）在窗口外仍被扫描到
        c = build_crisis_annotation(_history(_2018_BARS, "2018-06-15", "2018-08-05"))
        it = _interval(c, "2018 贸易摩擦")
        assert it["in_range"] is True
        assert it["trough_date"] == "2018-08-01"
        assert it["recovery_days"] == 22  # 恢复耗时按交易日计（自然日 31 中扣除周末）
        assert it["recovered"] is True

    def test_data_end_missing_falls_back_to_last_bar(self):
        """history_data 无 data_end → 窗口末端回退到 bars[-1].date。"""
        c = build_crisis_annotation(_history(_2018_BARS, "2018-06-15"))
        it = _interval(c, "2018 贸易摩擦")
        assert it["in_range"] is True
        assert it["interval_drawdown_pct"] == 30.0

    def test_overlap_window_without_bars_keeps_stats_none(self):
        """重叠窗口内无 bar → in_range=True 但区间统计置空。"""
        bars = _bars(
            [
                ("2015-06-10", 100.0),
                ("2015-06-20", 90.0),  # 跳过 [2015-06-12, 2015-06-15] 窗口
            ]
        )
        c = build_crisis_annotation(_history(bars, "2015-06-12", "2015-06-15"))
        it = _interval(c, "2015 股灾")
        assert it["in_range"] is True
        assert it["interval_drawdown_pct"] is None
        assert it["recovered"] is None

    def test_nonpositive_value_skipped_in_interval_stats(self):
        """区间内出现非正值净值（0）→ 跳过，不破坏最大回撤计算。"""
        bars = _bars(
            [
                ("2018-06-20", 100.0),
                ("2018-07-05", 0.0),  # 非正值，跳过
                ("2018-08-01", 70.0),  # 最深日，回撤仍 30%
                ("2018-09-01", 100.0),
            ]
        )
        c = build_crisis_annotation(_history(bars, "2018-06-15", "2018-12-31"))
        it = _interval(c, "2018 贸易摩擦")
        assert it["interval_drawdown_pct"] == 30.0
        assert it["trough_date"] == "2018-08-01"

    def test_bad_window_dates_produce_no_overlap(self):
        """data_start/data_end 非法 → 全部区间不重叠（防御分支）。"""
        bars = _bars([("2020-02-10", 100.0)])
        c = build_crisis_annotation({"status": "ok", "bars": bars, "data_start": "bad-date", "data_end": "2020-12-31"})
        assert c["available"] is True
        assert all(it["in_range"] is False for it in c["intervals"])


class TestCrisisIntervalHelpers:
    """CRISIS_INTERVALS 静态表 + 内部解析/重叠辅助。"""

    def test_static_table_shapes_and_known_anchors(self):
        """静态表结构完整（字段/日期/起止有序/名称唯一），含最早与最新锚点条目。

        断言结构关系而非条数或全清单——静态表后续增补危机区间时本用例不需改写。
        """
        names = [it["name"] for it in CRISIS_INTERVALS]
        assert len(names) == len(set(names))  # 名称唯一
        # 最早（2015 股灾）与最新锚点（近窗口关税冲击）必须在表内
        assert {"2015 股灾", "2025 关税冲击"} <= set(names)
        # 每项具备完整字段，日期合法且起止有序
        for it in CRISIS_INTERVALS:
            assert {"name", "start", "end", "desc"} <= set(it)
            assert date.fromisoformat(it["start"]) <= date.fromisoformat(it["end"])

    def test_parse_window_valid(self):
        """合法日期 → (start, end) date 对。"""
        assert _parse_window("2018-01-01", "2018-12-31") == (
            date(2018, 1, 1),
            date(2018, 12, 31),
        )

    def test_parse_window_bad_format_returns_none(self):
        """非法日期 → None。"""
        assert _parse_window("bad", "2018-12-31") is None
        assert _parse_window(None, None) is None

    def test_overlap_clips_to_window(self):
        """区间与窗口部分重叠 → 返回裁剪后的重叠日期。"""
        raw = {"name": "2018 贸易摩擦", "start": "2018-06-19", "end": "2019-01-04"}
        window = (date(2018, 1, 1), date(2018, 12, 31))
        assert _overlap_interval(raw, window) == (date(2018, 6, 19), date(2018, 12, 31))

    def test_overlap_no_intersection_returns_none(self):
        """区间完全在窗口外 → None。"""
        raw = {"name": "2015 股灾", "start": "2015-06-12", "end": "2015-09-30"}
        window = (date(2018, 1, 1), date(2018, 12, 31))
        assert _overlap_interval(raw, window) is None

    def test_overlap_none_window_returns_none(self):
        """window=None → None。"""
        raw = {"name": "2018 贸易摩擦", "start": "2018-06-19", "end": "2019-01-04"}
        assert _overlap_interval(raw, None) is None


class TestCrisisReplay:
    """回放态（功能开关 crisis_replay）双层契约 — 关态兼容 / 组合层 / 指数层 / 降级。"""

    @staticmethod
    def _index_series() -> dict:
        """合成覆盖全部静态危机区间的主基准日线（每区间 起 100 / 深 85 / 收 95）。"""
        bars: list[dict] = []
        for iv in CRISIS_INTERVALS:
            mid = (date.fromisoformat(iv["start"]) + timedelta(days=10)).isoformat()
            bars.append({"date": iv["start"], "close": 100.0})
            bars.append({"date": mid, "close": 85.0})
            bars.append({"date": iv["end"], "close": 95.0})
        bars.sort(key=lambda b: b["date"])
        return {"name": "沪深300", "bars": bars}

    def test_off_state_contract_has_no_replay_fields(self):
        """关态（默认）：顶层无 replay 键、区间项无任何回放字段（历史契约逐字节兼容）。"""
        contract = build_crisis_annotation(_history(_2018_BARS, "2018-01-01", "2018-12-31"))
        assert "replay" not in contract
        assert "index_reason" not in contract
        for it in contract["intervals"]:
            assert "portfolio_return_pct" not in it
            assert "index_return_pct" not in it
            assert "index_drawdown_pct" not in it
            assert "index_available" not in it

    def test_replay_marks_all_intervals_with_index_layer(self):
        """回放态 + 指数序列 → 顶层 replay、全部区间含指数层字段；窗口外区间指数也算出。"""
        contract = build_crisis_annotation(
            _history(_2018_BARS, "2018-01-01", "2018-12-31"),
            replay=True,
            index_series=self._index_series(),
        )
        assert contract["replay"] is True
        assert "index_reason" not in contract
        for it in contract["intervals"]:
            assert it["index_available"] is True
            assert it["index_return_pct"] is not None
            assert it["index_drawdown_pct"] is not None
        # 窗口外的 2015 区间：组合层不可算、指数层有值（双层设计的互补关系）
        it2015 = _interval(contract, "2015 股灾")
        assert it2015["in_range"] is False
        assert it2015["portfolio_return_pct"] is None

    def test_replay_portfolio_layer_within_window(self):
        """回放态窗口内区间（2018）→ 组合区间收益算出，回撤/恢复字段沿用关态语义。"""
        contract = build_crisis_annotation(
            _history(_2018_BARS, "2018-01-01", "2018-12-31"),
            replay=True,
            index_series=self._index_series(),
        )
        it = _interval(contract, "2018 贸易摩擦")
        assert it["in_range"] is True
        # 重叠段首尾：2018-06-20 100 → 2018-12-31 110 → +10%
        assert it["portfolio_return_pct"] == pytest.approx(10.0)
        assert it["interval_drawdown_pct"] == pytest.approx(30.0)

    def test_replay_index_math(self):
        """指数层收益/回撤：100 → 85 → 95 → 收益 -5%、最大回撤 15%。"""
        contract = build_crisis_annotation(
            _history(_2018_BARS, "2018-01-01", "2018-12-31"),
            replay=True,
            index_series=self._index_series(),
        )
        it = _interval(contract, "2015 股灾")
        assert it["index_return_pct"] == pytest.approx(-5.0)
        assert it["index_drawdown_pct"] == pytest.approx(15.0)

    def test_replay_without_index_series_records_reason(self):
        """指数序列缺失（未配置基准）→ index_reason 记录 + 全区间指数层不可用；组合层不受影响。"""
        contract = build_crisis_annotation(
            _history(_2018_BARS, "2018-01-01", "2018-12-31"),
            replay=True,
            index_series=None,
        )
        assert contract["replay"] is True
        assert "基准" in str(contract["index_reason"])
        assert all(not it["index_available"] for it in contract["intervals"])
        it = _interval(contract, "2018 贸易摩擦")
        assert it["portfolio_return_pct"] is not None  # 组合层独立于指数层

    def test_replay_index_coverage_insufficient(self):
        """指数日线区间内有效点不足 → 对应区间 index_available=False（不编造数值）。"""
        contract = build_crisis_annotation(
            _history(_2018_BARS, "2018-01-01", "2018-12-31"),
            replay=True,
            index_series={"bars": [{"date": "2015-06-12", "close": 100.0}]},
        )
        assert all(not it["index_available"] for it in contract["intervals"])

    def test_replay_unavailable_history_falls_back_to_off_contract(self):
        """history 不可用 → 关态占位（回放态亦退回占位，呈现层按关态渲染）。"""
        contract = build_crisis_annotation(None, replay=True, index_series=self._index_series())
        assert contract["available"] is False
        assert "replay" not in contract

    def test_recent_interval_in_extended_window(self):
        """长窗 bars 覆盖近窗口关税冲击（2025-04）→ 该区间 in_range + 组合收益算出。"""
        bars = _bars(
            [
                ("2025-03-01", 100.0),
                ("2025-04-07", 100.0),
                ("2025-04-15", 90.0),
                ("2025-04-30", 97.0),
                ("2025-05-01", 98.0),
            ]
        )
        contract = build_crisis_annotation(
            _history(bars, "2025-03-01", "2025-05-01"),
            replay=True,
            index_series=self._index_series(),
        )
        it = _interval(contract, "2025 关税冲击")
        assert it["in_range"] is True
        assert it["portfolio_return_pct"] == pytest.approx(-3.0)  # 100 → 97
