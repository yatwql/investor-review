"""组合相对基准风险调整超额度量 — 纯计算层（数据契约数据源）。

职责：基于组合历史走势契约（history_data，含归一化基准序列），计算
「组合跑没跑赢基准」的风险调整超额度量：

- 滚动 1Y（250 交易日）超额曲线（组合累计收益 − 基准累计收益）
- 年化信息比率 IR 与跟踪误差 TE（全窗口日超额序列）
- 近 12 / 24 月跑赢基准胜率（完整自然月粒度，组合月收益 > 基准月收益记胜）

设计要点：
- 纯标准库、无数据获取、无 report/llm 依赖（analysis 层隔离约束）；
  基准序列由调用方传入（走势章既有 benchmarks 归一化序列，与组合 bars
  按索引一一对应——normalize_benchmarks LOCF 对齐契约）。
- 样本不足按 §1.4.5 数据降级治理逐指标降级：IR/TE 需 ≥60 对齐交易日，
  胜率需 ≥12 / ≥24 个完整自然月（排除数据首末不完整月），不足置 None
  并在 reason 中说明，不阻断其余指标。
- 契约结构见 technical.md 附录 H「风险调整超额契约（risk_adjusted_excess_data）」。

用法：
  >>> from src.python.analysis.benchmark_excess import build_risk_adjusted_excess
  >>> contract = build_risk_adjusted_excess(history_data)
  >>> contract["available"]
  True
"""

from __future__ import annotations

import math
from typing import Any

# ── 口径常量 ─────────────────────────────────────────────

_TRADING_DAYS_PER_YEAR = 252
"""A 股年化交易日数（IR / TE / 年化超额）。"""

ROLLING_WINDOW_DAYS = 250
"""滚动超额曲线窗口（交易日 ≈ 1 年）。"""

_MIN_SAMPLE_IR = 60
"""IR / TE 最少对齐交易日样本，不足则该指标置 None。"""

_MIN_COMPLETE_MONTHS_12M = 12
"""近 12 月胜率所需最少完整自然月数。"""

_MIN_COMPLETE_MONTHS_24M = 24
"""近 24 月胜率所需最少完整自然月数。"""

_EPS = 1e-15
"""除零/方差退化保护。"""

__all__ = [
    "ROLLING_WINDOW_DAYS",
    "build_risk_adjusted_excess",
]


# ── 契约构建 ─────────────────────────────────────────────


def build_risk_adjusted_excess(history_data: dict[str, Any] | None) -> dict[str, Any]:
    """构建风险调整超额契约（`risk_adjusted_excess_data`）。

    Args:
        history_data: 组合历史走势契约 dict（bars / daily_returns / benchmarks）。
            为 None、status=unavailable、bars 空或未配置基准时返回
            available=False 占位（含中文降级原因）。

    Returns:
        契约 dict：
        {
            "available": bool,
            "reason": str | None,        # available=False 的降级原因
            "window": {"start", "end", "days"} | None,
            "benchmarks": [              # 每个基准一行（available=True 时）
                {"code", "name",
                 "ir_annual": float | None,        # 年化信息比率
                 "te_annual": float | None,        # 年化跟踪误差
                 "excess_annual_pct": float | None,  # 年化超额收益（%）
                 "win_rate_12m": float | None,     # 近 12 完整月跑赢胜率（%）
                 "win_rate_24m": float | None,     # 近 24 完整月跑赢胜率（%）
                 "complete_months": int},          # 数据内完整自然月数
            ],
            "rolling": {                 # 主基准（第一个）滚动 1Y 超额
                "available": bool,
                "reason": str | None,
                "window_days": int,
                "primary_name": str,
                "points": [{"date", "excess_pct"}, ...],
            },
            "notes": [str, ...],         # 口径句（展示层引用，单源）
        }
    """
    if not history_data or history_data.get("status") == "unavailable":
        return _unavailable("历史走势数据不可用")
    bars = history_data.get("bars") or []
    if not bars:
        return _unavailable("历史走势数据不可用")
    benchmarks = history_data.get("benchmarks") or []
    if not benchmarks:
        return _unavailable("未配置业绩基准（history.benchmark_indices）")

    daily_returns = history_data.get("daily_returns") or []
    bm_rows: list[dict[str, Any]] = []
    primary_pairs: list[tuple[str, float, float]] = []

    for idx, bm in enumerate(benchmarks):
        pairs = _align_excess_pairs(bars, daily_returns, bm)
        if idx == 0:
            primary_pairs = pairs
        row = {
            "code": bm.get("code", ""),
            "name": bm.get("name", bm.get("code", "基准")),
            "ir_annual": _information_ratio(pairs),
            "te_annual": _tracking_error(pairs),
            "excess_annual_pct": _annualized_excess_pct(pairs),
            "win_rate_12m": None,
            "win_rate_24m": None,
            "complete_months": 0,
        }
        wr12, wr24, n_months = _win_rates(pairs)
        row["win_rate_12m"] = wr12
        row["win_rate_24m"] = wr24
        row["complete_months"] = n_months
        bm_rows.append(row)

    rolling = _rolling_excess(primary_pairs, bm_rows[0]["name"] if bm_rows else "")

    return {
        "available": True,
        "reason": None,
        "window": {
            "start": str(bars[0].get("date") or ""),
            "end": str(bars[-1].get("date") or ""),
            "days": len(bars),
        },
        "benchmarks": bm_rows,
        "rolling": rolling,
        "notes": [
            "口径：超额 = 组合日收益 − 基准日收益（归一化序列按交易日对齐）；"
            f"IR = 日超额均值 / 日超额标准差 × √{_TRADING_DAYS_PER_YEAR}（年化）；"
            f"跟踪误差 = 日超额标准差 × √{_TRADING_DAYS_PER_YEAR}（年化）",
            "跑赢胜率按完整自然月粒度（排除数据首末不完整月）：组合月收益 > 基准月收益记胜；"
            "12/24 月胜率分别需 ≥12 / ≥24 个完整月，不足则该格标「数据不足」",
            f"滚动超额 = 近 {ROLLING_WINDOW_DAYS} 个交易日组合与基准累计收益之差（百分点），逐交易日滚动",
        ],
    }


def _unavailable(reason: str) -> dict[str, Any]:
    """数据不可用占位（§1.4.5 降级空口径）。"""
    return {
        "available": False,
        "reason": reason,
        "window": None,
        "benchmarks": [],
        "rolling": {
            "available": False,
            "reason": reason,
            "window_days": ROLLING_WINDOW_DAYS,
            "primary_name": "",
            "points": [],
        },
        "notes": [],
    }


# ── 对齐与指标 ───────────────────────────────────────────


def _align_excess_pairs(
    bars: list[dict[str, Any]],
    daily_returns: list[float],
    bm: dict[str, Any],
) -> list[tuple[str, float, float]]:
    """对齐组合日收益与基准日收益，产出 (date, 组合日收益, 基准日收益) 三元组。

    对齐口径：基准归一化序列与组合 bars 按索引一一对应（normalize_benchmarks
    契约）；组合日收益序列序号 j 对应 bars[j+1]。基准短缺/值非正的点跳过。
    """
    pairs: list[tuple[str, float, float]] = []
    bm_bars = bm.get("bars") or []
    n = min(len(bars), len(bm_bars), len(daily_returns) + 1)
    for j in range(len(daily_returns)):
        if j + 1 >= n:
            break
        prev_v = float(bm_bars[j].get("value") or 0.0)
        curr_v = float(bm_bars[j + 1].get("value") or 0.0)
        if prev_v <= 0 or curr_v <= 0:
            continue
        port_r = float(daily_returns[j])
        bm_r = (curr_v - prev_v) / prev_v
        date = str(bars[j + 1].get("date") or "")
        pairs.append((date, port_r, bm_r))
    return pairs


def _excess_series(pairs: list[tuple[str, float, float]]) -> list[float]:
    """日超额序列（组合日收益 − 基准日收益）。"""
    return [p - b for _, p, b in pairs]


def _information_ratio(pairs: list[tuple[str, float, float]]) -> float | None:
    """年化信息比率 IR = mean(excess) / std(excess) × √252；样本不足/退化 → None。"""
    excess = _excess_series(pairs)
    if len(excess) < _MIN_SAMPLE_IR:
        return None
    mean = sum(excess) / len(excess)
    var = sum((x - mean) ** 2 for x in excess) / (len(excess) - 1)
    if var < _EPS:
        return None
    ir = mean / math.sqrt(var) * math.sqrt(_TRADING_DAYS_PER_YEAR)
    return _finite(ir)


def _tracking_error(pairs: list[tuple[str, float, float]]) -> float | None:
    """年化跟踪误差 TE = std(excess) × √252；样本不足/退化 → None。"""
    excess = _excess_series(pairs)
    if len(excess) < _MIN_SAMPLE_IR:
        return None
    mean = sum(excess) / len(excess)
    var = sum((x - mean) ** 2 for x in excess) / (len(excess) - 1)
    if var < _EPS:
        return None
    te = math.sqrt(var) * math.sqrt(_TRADING_DAYS_PER_YEAR)
    return _finite(te)


def _annualized_excess_pct(pairs: list[tuple[str, float, float]]) -> float | None:
    """全窗口年化超额收益（几何，%）；样本不足 → None。"""
    if len(pairs) < _MIN_SAMPLE_IR:
        return None
    p_total = 1.0
    b_total = 1.0
    for _, p, b in pairs:
        p_total *= 1.0 + p
        b_total *= 1.0 + b
    p_ann = p_total ** (_TRADING_DAYS_PER_YEAR / len(pairs)) - 1.0
    b_ann = b_total ** (_TRADING_DAYS_PER_YEAR / len(pairs)) - 1.0
    return _finite((p_ann - b_ann) * 100.0)


def _monthly_win_rates(
    pairs: list[tuple[str, float, float]],
) -> tuple[dict[tuple[int, int], float], dict[tuple[int, int], float]]:
    """按自然月分组，分别复利组合与基准月收益 → { (年, 月): 月超额 }。"""
    port_m: dict[tuple[int, int], float] = {}
    bm_m: dict[tuple[int, int], float] = {}
    for date, p, b in pairs:
        try:
            yyyymm = (int(date[0:4]), int(date[5:7]))
        except (ValueError, IndexError, TypeError):
            continue
        port_m[yyyymm] = port_m.get(yyyymm, 1.0) * (1.0 + p)
        bm_m[yyyymm] = bm_m.get(yyyymm, 1.0) * (1.0 + b)
    port_ret = {k: v - 1.0 for k, v in port_m.items()}
    bm_ret = {k: v - 1.0 for k, v in bm_m.items()}
    keys = sorted(set(port_ret) & set(bm_ret))
    excess = {k: port_ret[k] - bm_ret[k] for k in keys}
    return excess, bm_ret


def _win_rates(pairs: list[tuple[str, float, float]]) -> tuple[float | None, float | None, int]:
    """近 12 / 24 完整月跑赢胜率（%）。

    完整自然月 = 排除数据首末月份（可能不完整）。不足 12 / 24 个完整月时
    对应胜率置 None（展示层标「数据不足」）。
    """
    excess_by_month, _ = _monthly_win_rates(pairs)
    complete = sorted(excess_by_month)[1:-1] if len(excess_by_month) > 2 else []
    n = len(complete)

    def _rate(months: int) -> float | None:
        if n < months:
            return None
        window = complete[-months:]
        wins = sum(1 for k in window if excess_by_month[k] > 0)
        return round(wins / len(window) * 100, 1)

    return _rate(_MIN_COMPLETE_MONTHS_12M), _rate(_MIN_COMPLETE_MONTHS_24M), n


def _rolling_excess(
    pairs: list[tuple[str, float, float]],
    primary_name: str,
) -> dict[str, Any]:
    """主基准滚动 1Y 超额曲线（逐交易日）。样本 < 窗口长度 → unavailable。"""
    if len(pairs) < ROLLING_WINDOW_DAYS:
        return {
            "available": False,
            "reason": f"数据不足（需 ≥{ROLLING_WINDOW_DAYS} 个交易日，现有 {len(pairs)} 个）",
            "window_days": ROLLING_WINDOW_DAYS,
            "primary_name": primary_name,
            "points": [],
        }
    points: list[dict[str, Any]] = []
    # 预计算前缀累计，滚动窗口累计 = 前缀商，O(n) 而非 O(n·w)
    port_cum = [1.0]
    bm_cum = [1.0]
    for _, p, b in pairs:
        port_cum.append(port_cum[-1] * (1.0 + p))
        bm_cum.append(bm_cum[-1] * (1.0 + b))
    for i in range(ROLLING_WINDOW_DAYS, len(pairs) + 1):
        port_window = port_cum[i] / port_cum[i - ROLLING_WINDOW_DAYS] - 1.0
        bm_window = bm_cum[i] / bm_cum[i - ROLLING_WINDOW_DAYS] - 1.0
        value = _finite((port_window - bm_window) * 100.0)
        if value is None:
            continue
        points.append({"date": pairs[i - 1][0], "excess_pct": round(value, 2)})
    if not points:
        return {
            "available": False,
            "reason": "滚动窗口计算结果为空",
            "window_days": ROLLING_WINDOW_DAYS,
            "primary_name": primary_name,
            "points": [],
        }
    return {
        "available": True,
        "reason": None,
        "window_days": ROLLING_WINDOW_DAYS,
        "primary_name": primary_name,
        "points": points,
    }


def _finite(value: float | None) -> float | None:
    """NaN/Inf → None（数值清理）。"""
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value
