"""历史走势数据质量校验 — 异常检测与收益率诊断。"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("invest")


def _validate_bars(bars: list[dict]) -> list[str]:
    """检查走势数据质量，返回警告列表。

    检查项：
      - 收盘价为 0
      - 未来日期
      - 明显的异常跳变（单日涨跌 > 50%）

    Args:
        bars: 走势数据列表

    Returns:
        警告消息列表，无问题时为空列表
    """
    warnings: list[str] = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    for i, b in enumerate(bars):
        close = b.get("close") or b.get("total_value", 0)
        if close == 0:
            warnings.append(f"{b['date']}: 收盘价为 0（可能停牌或数据异常）")
        if b.get("date", "") > today_str:
            warnings.append(f"{b['date']}: 日期为未来")

        # 检查异常跳变
        if i > 0:
            prev = bars[i - 1].get("close") or bars[i - 1].get("total_value", 0)
            if prev > 0 and close > 0:
                change_pct = abs(close - prev) / prev
                if change_pct > 0.5:
                    warnings.append(f"{b['date']}: 单日变化 {change_pct * 100:.1f}%（可能异常）")

    return warnings


def _detect_terminal_staleness(
    labelled_series: list[tuple[str, list[dict]]],
    merged_dates: list[str],
    terminal_total: float,
    min_lag_trading_days: int = 2,
) -> dict | None:
    """检测走势终点是否由滞后数据构成（各标的最后一条 bar 日期不一致）。

    LOCF 合并会把未刷新的标的沿用上次已知值：QDII/场外基金净值 T-1 滞后属常态
    （落后 1 个交易日），不提示；落后 ≥ ``min_lag_trading_days`` 说明该标的净值链路
    缺数，此时走势终值混用了不同日期的估值，与「最新市值」口径不一致——末端日收益
    与回撤被低估，且走势图终点与报告头市值对不上（实测 2 只基金停在 2 个交易日前，
    终值高出最新市值 3261 元 / 1.2%）。

    Args:
        labelled_series: [(标签, bars), ...]，标签用于提示文案（如「名称(代码)」）
        merged_dates: 合并后的交易日列表（升序），用于换算滞后交易日数
        terminal_total: 走势终点总市值，用于计算滞后标的占比
        min_lag_trading_days: 触发提示的最小滞后交易日数（默认 2）

    Returns:
        {"latest_date", "max_lag_trading_days", "assets": [...], "warning": str}；
        无滞后或滞后未达阈值时返回 None。
    """
    observed: list[tuple[str, str, float]] = []
    for label, series in labelled_series:
        if not series:
            continue
        last_bar = series[-1]
        observed.append((label, str(last_bar.get("date", "")), float(last_bar.get("value") or 0.0)))
    if not observed:
        return None

    latest_date = max(date for _, date, _ in observed)
    date_index = {d: i for i, d in enumerate(merged_dates)}
    last_idx = len(merged_dates) - 1

    stale: list[dict] = []
    for label, last_date, value in observed:
        idx = date_index.get(last_date)
        # 未出现在合并时间线上（被有效区间截断掉）时，按「终点之后的交易日数」计数
        lag = (last_idx - idx) if idx is not None else sum(1 for d in merged_dates if d > last_date)
        if lag < min_lag_trading_days:
            continue
        stale.append(
            {
                "label": label,
                "last_date": last_date,
                "lag_trading_days": lag,
                "value": round(value, 2),
                "weight_pct": round(value / terminal_total * 100, 2) if terminal_total > 0 else 0.0,
            }
        )

    if not stale:
        return None

    stale.sort(key=lambda a: (-a["lag_trading_days"], -a["weight_pct"]))
    max_lag = max(a["lag_trading_days"] for a in stale)
    oldest_date = min(a["last_date"] for a in stale)
    weight_sum = sum(a["weight_pct"] for a in stale)
    warning = (
        f"历史走势终点净值滞后：{'、'.join(a['label'] for a in stale)} 的最新数据日为 {oldest_date}"
        f"（落后 {max_lag} 个交易日，合计占组合 {weight_sum:.1f}%），"
        "走势终值与最新市值口径不同，末端日收益与回撤可能偏低"
    )
    return {
        "latest_date": latest_date,
        "max_lag_trading_days": max_lag,
        "assets": stale,
        "warning": warning,
    }


def _diagnose_return(
    bars: list[dict],
    valid_start_idx: int,
    fund_count_on_date: dict[str, int],
    total_return_pct: float,
    total_series: int,
) -> None:
    """诊断收益率异常：输出起止日市值、覆盖标的数、每日明细快照。"""
    if not bars:
        return

    first_bar = bars[valid_start_idx]
    last_bar = bars[-1]

    # 取起止日 + 中间等间隔抽 3 个样本
    step = max(1, (len(bars) - 1) // 4)
    sample_idxs = [valid_start_idx] + [valid_start_idx + step * i for i in range(1, 4)] + [len(bars) - 1]
    sample_idxs = sorted(set(i for i in sample_idxs if i < len(bars)))

    lines = [
        "[history] ═══ 累计收益率诊断 ═══",
        f"[history]  起算日: {first_bar['date']}  total_value={first_bar['total_value']:.2f}  "
        f"覆盖 {fund_count_on_date.get(first_bar['date'], 0)}/{total_series} 只",
        f"[history]  终止日: {last_bar['date']}  total_value={last_bar['total_value']:.2f}  "
        f"覆盖 {fund_count_on_date.get(last_bar['date'], 0)}/{total_series} 只",
        f"[history]  收益率: {total_return_pct:.2f}%",
        f"[history]  期间: {first_bar['date']} → {last_bar['date']} 共 {len(bars) - valid_start_idx} 个交易日",
    ]

    # 每日明细快照
    lines.append(f"[history]  中轴抽样（{len(sample_idxs)} 点）:")
    for idx in sample_idxs:
        b = bars[idx]
        coverage = fund_count_on_date.get(b["date"], 0)
        lines.append(
            f"[history]    {b['date']}  tv={b['total_value']:.2f}  "
            f"dd={b['drawdown']:.2f}  dd%={b['drawdown_pct']:.2f}%  "
            f"覆盖={coverage}/{total_series}"
        )

    for line in lines:
        logger.info(line)
