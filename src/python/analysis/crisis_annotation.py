"""危机区间标注与双层回放 — 纯计算层（数据契约数据源）。

职责：基于组合净值时间线（history_data.bars），对预设历史危机区间
（2015 股灾 / 2018 贸易摩擦 / 2020 疫情 / 2022 调整 / 2025 关税冲击）做
区间标注，并在回放态（replay=True）下扩展「组合 vs 指数」双层表现：

- 区间是否落在报告数据窗口内（in_range）
- 区间内最大回撤（interval_drawdown_pct，正数百分比）
- 区间最深日（trough_date）与恢复耗时（recovery_days）
- 回放态（双层）：
  - 组合层 —— 区间收益（portfolio_return_pct，in_range 时才可算）
  - 指数层 —— 主基准在危机区间的收益与最大回撤（index_return_pct /
    index_drawdown_pct），基于编排层预取的指数长窗日线，对**全部**区间
    计算——历史危机大多超出组合侧可得窗口（数据源单次 ≤365 交易日），
    指数层保证历史危机仍有市场基准参照；组合侧不可得时如实标窗口外

设计要点：
- 危机日期为**静态历史事实表**（不随持仓变化）；关态仅在既有 bars 数据
  窗口内做重叠裁剪，无任何新增网络请求；回放态的长窗 bars 与指数序列
  由编排层预取传入，本模块保持纯计算（无 I/O）。
- 关态（replay 缺省 False）契约仅含 available/intervals 两键——不写任何回放字段。
- 纯标准库，无数据获取、无 report/llm 依赖（analysis 层隔离约束）。
- 契约结构见 technical.md 附录 H「危机区间标注契约（crisis_annotation_data）」。

用法：
  >>> from src.python.analysis.crisis_annotation import build_crisis_annotation
  >>> contract = build_crisis_annotation(history_data)
  >>> contract["intervals"][0]["name"]
  '2015 股灾'
"""

from __future__ import annotations

from src.python.core.trading_calendar import elapsed_trading_days_with_natural_fallback
from datetime import date
from typing import Any

# ── 静态危机区间表（历史事实，不随持仓变化） ─────────────────
# 每项：{name, start, end, desc}，日期为 ISO 格式（YYYY-MM-DD）。
CRISIS_INTERVALS: list[dict[str, str]] = [
    {
        "name": "2015 股灾",
        "start": "2015-06-12",
        "end": "2015-09-30",
        "desc": "杠杆牛破裂，上证指数自 5178 点快速回落，连续千股跌停",
    },
    {
        "name": "2018 贸易摩擦",
        "start": "2018-06-19",
        "end": "2019-01-04",
        "desc": "中美贸易摩擦升级，市场风险偏好收缩，上证指数跌破 2500 点",
    },
    {
        "name": "2020 疫情冲击",
        "start": "2020-02-03",
        "end": "2020-03-23",
        "desc": "新冠疫情全球扩散引发流动性危机，全球市场同步重挫",
    },
    {
        "name": "2022 市场调整",
        "start": "2022-01-04",
        "end": "2022-04-27",
        "desc": "美联储激进加息叠加俄乌冲突，成长股大幅回调",
    },
    {
        "name": "2025 关税冲击",
        "start": "2025-04-07",
        "end": "2025-04-30",
        "desc": "美国对等关税落地引发全球风险资产剧烈震荡，A 股节后开盘单日重挫后逐步企稳",
    },
]


def build_crisis_annotation(
    history_data: dict | None,
    replay: bool = False,
    index_series: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建危机区间标注契约（`crisis_annotation_data`）。

    Args:
        history_data: 组合历史走势契约 dict（含 bars / data_start / data_end）。
            为 None、status=unavailable 或 bars 为空时返回 available=False 占位
            （回放态亦退回占位——呈现层按 6 列关态渲染）。
        replay: 回放态开关（crisis_replay）。True 时契约顶层写 ``replay`` 键，
            每区间扩展组合层收益与指数层收益/回撤字段；False（默认）时不写
            任何回放字段。
        index_series: 编排层预取的主基准指数长窗日线
            ``{"bars": [{"date", "close"}, ...]}`` 或 None（未配置基准）。
            仅 replay=True 时被消费；缺失/空时指数层逐区间标不可用。

    Returns:
        契约 dict：
        {
            "available": bool,   # 数据可用（history_data 有可用 bars）
            "replay": True,      # 仅回放态写入（关态无此键）
            "index_reason": str, # 仅回放态：指数层不可用原因（有则写）
            "intervals": [
                {
                    "name": str,               # 危机名称
                    "start": str,              # 区间起点（ISO 日期）
                    "end": str,                # 区间终点（ISO 日期）
                    "desc": str,               # 危机背景说明
                    "in_range": bool,          # 是否与报告数据窗口重叠
                    "interval_drawdown_pct": float | None,  # 区间最大回撤（正数 %）
                    "trough_date": str | None, # 区间内最深日
                    "recovery_days": int | None,  # 最深日→恢复耗时（天），未恢复为 None
                    "recovered": bool | None,  # 数据窗口内是否已恢复
                    # ── 以下仅回放态（replay=True）写入 ──
                    "portfolio_return_pct": float | None,  # 组合区间收益（%，in_range 才可算）
                    "index_return_pct": float | None,      # 指数区间收益（%）
                    "index_drawdown_pct": float | None,    # 指数区间最大回撤（%，正数）
                    "index_available": bool,               # 指数层是否算出
                },
                ...
            ],
        }
    """
    if not history_data or history_data.get("status") == "unavailable":
        return _unavailable()
    bars = history_data.get("bars") or []
    if not bars:
        return _unavailable()

    data_start = history_data.get("data_start") or bars[0].get("date", "")
    data_end = history_data.get("data_end") or bars[-1].get("date", "")
    window = _parse_window(data_start, data_end)

    index_bars = None
    if replay:
        index_bars = (index_series or {}).get("bars") or None

    intervals: list[dict[str, Any]] = []
    for raw in CRISIS_INTERVALS:
        entry: dict[str, Any] = {
            "name": raw["name"],
            "start": raw["start"],
            "end": raw["end"],
            "desc": raw.get("desc", ""),
            "in_range": False,
            "interval_drawdown_pct": None,
            "trough_date": None,
            "recovery_days": None,
            "recovered": None,
        }
        overlap = _overlap_interval(raw, window)
        if overlap is not None:
            stats = _compute_interval_stats(bars, overlap, replay=replay)
            entry.update(stats)
            entry["in_range"] = True
        elif replay:
            entry["portfolio_return_pct"] = None
        if replay:
            entry.update(_compute_index_stats(index_bars, raw))
        intervals.append(entry)

    contract: dict[str, Any] = {"available": True, "intervals": intervals}
    if replay:
        contract["replay"] = True
        if not index_bars:
            contract["index_reason"] = "未配置业绩基准（history.benchmark_indices）"
    return contract


# ── 内部实现 ─────────────────────────────────────────────


def _unavailable() -> dict[str, Any]:
    """数据不可用占位（status=unavailable / 无 bars）。"""
    return {
        "available": False,
        "intervals": [
            {
                "name": raw["name"],
                "start": raw["start"],
                "end": raw["end"],
                "desc": raw.get("desc", ""),
                "in_range": False,
                "interval_drawdown_pct": None,
                "trough_date": None,
                "recovery_days": None,
                "recovered": None,
            }
            for raw in CRISIS_INTERVALS
        ],
    }


def _parse_window(data_start: str, data_end: str) -> tuple[date, date] | None:
    """解析报告数据窗口为 (start, end) date 对；格式异常返回 None。"""
    try:
        return date.fromisoformat(data_start), date.fromisoformat(data_end)
    except (TypeError, ValueError):
        return None


def _overlap_interval(
    raw: dict[str, str],
    window: tuple[date, date] | None,
) -> tuple[date, date] | None:
    """计算危机区间与报告数据窗口的重叠区间。

    Returns:
        (overlap_start, overlap_end) 或 None（区间不重叠 / 日期格式异常）。
    """
    if window is None:
        return None
    w_start, w_end = window
    try:
        i_start = date.fromisoformat(raw["start"])
        i_end = date.fromisoformat(raw["end"])
    except (TypeError, ValueError):
        return None
    overlap_start = max(i_start, w_start)
    overlap_end = min(i_end, w_end)
    if overlap_start > overlap_end:
        return None
    return overlap_start, overlap_end


def _compute_interval_stats(
    bars: list[dict],
    overlap: tuple[date, date],
    replay: bool = False,
) -> dict[str, Any]:
    """在重叠区间内计算区间回撤 + 恢复耗时（回放态追加区间收益）。

    Args:
        bars: [{"date": "YYYY-MM-DD", "total_value": float, ...}, ...] 升序。
        overlap: (start, end) 重叠区间 date 对。
        replay: 回放态时追加 ``portfolio_return_pct``（重叠段首尾净值收益）。

    Returns:
        {interval_drawdown_pct, trough_date, recovery_days, recovered}
        —— 回放态多一个 portfolio_return_pct。
    """
    o_start, o_end = overlap
    window_bars: list[dict] = []
    for bar in bars:
        d_str = str(bar.get("date") or "")
        try:
            d = date.fromisoformat(d_str)
        except (TypeError, ValueError):
            continue
        if o_start <= d <= o_end:
            window_bars.append(bar)

    # 无重叠内 bar → 区间统计置空
    if not window_bars:
        empty: dict[str, Any] = {
            "interval_drawdown_pct": None,
            "trough_date": None,
            "recovery_days": None,
            "recovered": None,
        }
        if replay:
            empty["portfolio_return_pct"] = None
        return empty

    # 1) 区间最大回撤：窗口内 running peak 的最大 (peak - value)/peak
    running_peak = 0.0
    peak_at_trough = 0.0
    max_dd = 0.0
    trough_date: str | None = None
    for bar in window_bars:
        tv = float(bar.get("total_value") or 0.0)
        d = str(bar.get("date") or "")
        if tv <= 0:
            continue
        if tv > running_peak:
            running_peak = tv
        if running_peak > 0:
            dd = (running_peak - tv) / running_peak
            if dd > max_dd:
                max_dd = dd
                trough_date = d
                peak_at_trough = running_peak

    # 2) 恢复耗时：从最深日向后扫描，首个 total_value >= 峰值 的日期
    recovery_date: str | None = None
    if trough_date is not None and peak_at_trough > 0:
        scanning = False
        for bar in bars:
            d_str = str(bar.get("date") or "")
            if d_str == trough_date:
                scanning = True
                continue
            if scanning:
                tv = float(bar.get("total_value") or 0.0)
                if tv >= peak_at_trough:
                    recovery_date = d_str
                    break

    result: dict[str, Any] = {
        "interval_drawdown_pct": round(max_dd * 100, 2),
        "trough_date": trough_date,
        "recovery_days": None,
        "recovered": False,
    }
    if replay:
        result["portfolio_return_pct"] = _window_return_pct(window_bars)
    if recovery_date is None:
        return result

    recovery_days = elapsed_trading_days_with_natural_fallback(str(trough_date), str(recovery_date)) or None
    result["recovery_days"] = recovery_days
    result["recovered"] = True
    return result


def _window_return_pct(window_bars: list[dict]) -> float | None:
    """重叠段首尾有效净值的区间收益（%）；有效点不足 2 个 → None。"""
    values = [float(b.get("total_value") or 0.0) for b in window_bars if float(b.get("total_value") or 0.0) > 0]
    if len(values) < 2 or values[0] == 0:
        return None
    return round((values[-1] / values[0] - 1.0) * 100, 2)


def _compute_index_stats(
    index_bars: list[dict] | None,
    raw: dict[str, str],
) -> dict[str, Any]:
    """主基准指数在危机区间的收益与最大回撤（回放态指数层）。

    Args:
        index_bars: 指数长窗日线 [{"date", "close"}, ...] 升序，可长于组合窗口。
        raw: 静态危机区间条目（start / end）。

    Returns:
        {portfolio_return_pct（仅占位调用方已置）不在此; index_return_pct,
        index_drawdown_pct, index_available}。区间内有效点 < 2 → 不可用。
    """
    out: dict[str, Any] = {
        "index_return_pct": None,
        "index_drawdown_pct": None,
        "index_available": False,
    }
    if not index_bars:
        return out
    try:
        i_start = date.fromisoformat(raw["start"])
        i_end = date.fromisoformat(raw["end"])
    except (TypeError, ValueError):
        return out
    closes: list[float] = []
    for bar in index_bars:
        try:
            d = date.fromisoformat(str(bar.get("date") or ""))
        except (TypeError, ValueError):
            continue
        if i_start <= d <= i_end:
            c = float(bar.get("close") or 0.0)
            if c > 0:
                closes.append(c)
    if len(closes) < 2:
        return out
    running_peak = closes[0]
    max_dd = 0.0
    for c in closes:
        if c > running_peak:
            running_peak = c
        if running_peak > 0:
            dd = (running_peak - c) / running_peak
            if dd > max_dd:
                max_dd = dd
    out["index_return_pct"] = round((closes[-1] / closes[0] - 1.0) * 100, 2)
    out["index_drawdown_pct"] = round(max_dd * 100, 2)
    out["index_available"] = True
    return out
