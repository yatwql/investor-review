"""场外基金「按交易日取官方净值」查询（持仓录入专用，复用既有净值链）。

录入场外买入/卖出时，用户给的是**交易日**而不是价格，实际成本价来自该日官方单位净值。
本模块把「交易日 → 净值」的取数与降级口径收敛在一处：

  - 取数走既有历史净值链 ``history_fund_otc``（多 provider + 周级缓存），不新增网络源；
  - 当日无净值（非交易日 / 净值未发布）时取**该日之前最近一个净值日**，并在返回值里
    标明实际净值日期，由交互层如实上屏；
  - 全链路取不到 → 返回 ``None``（调用方按「该笔标失败，允许手填或放弃」处理，不得
    静默用 0 价或估算价）。
"""

from __future__ import annotations

import logging
import re
from datetime import date

from src.python.fetcher.chain_incremental import fetch_with_incremental_fallback

logger = logging.getLogger("invest")

_DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")
# 请求窗口下限：覆盖「交易日在前一天/上一交易日」的常规情形
_MIN_WINDOW_DAYS = 30
# 请求窗口上限：十年足够覆盖任何合理录入；防止异常日期把缓存窗口拉爆
_MAX_WINDOW_DAYS = 3650


def normalize_trade_date(raw: str) -> str:
    """交易日归一为 ``YYYY-MM-DD``（接受 ``YYYY/MM/DD``）。

    Args:
        raw: 用户输入的日期文本。

    Returns:
        归一后的日期字符串。

    Raises:
        ValueError: 形态非法或不是有效日历日。
    """
    match = _DATE_RE.match((raw or "").strip())
    if not match:
        raise ValueError(f"日期格式应为 YYYY-MM-DD: {raw}")
    year, month, day = (int(part) for part in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError as e:
        raise ValueError(f"不是有效日期: {raw}") from e


def resolve_nav_on_trade_date(code: str, trade_date: str) -> dict | None:
    """取场外基金在交易日（或其之前最近净值日）的官方单位净值。

    Args:
        code: 6 位基金代码。
        trade_date: 交易日（``YYYY-MM-DD``，可含 ``/``）。

    Returns:
        ``{"nav": float, "nav_date": str, "exact_date": bool}``；取不到返回 ``None``。
        ``exact_date`` 为 False 表示当日无净值、用的是之前最近净值日的净值。
    """
    try:
        target = normalize_trade_date(trade_date)
    except ValueError:
        logger.warning("[净值查询] 交易日非法: %s", trade_date)
        return None
    window = min(max((date.today() - date.fromisoformat(target)).days + 15, _MIN_WINDOW_DAYS), _MAX_WINDOW_DAYS)
    try:
        bars = fetch_with_incremental_fallback("history_fund_otc", code.strip(), window)
    except Exception:  # 取数链路异常不得打断录入会话
        logger.warning("[净值查询] 历史净值取数异常: %s", code, exc_info=True)
        return None
    if not bars:
        logger.warning("[净值查询] 无历史净值数据: %s", code)
        return None

    candidates = sorted((bar for bar in bars if str(bar.get("date") or "")), key=lambda bar: bar["date"])
    exact = next((bar for bar in candidates if candle_date(bar) == target), None)
    chosen = exact or _latest_before(candidates, target)
    if chosen is None:
        return None
    nav = float(chosen.get("nav") or 0.0)
    if nav <= 0:
        return None
    return {"nav": nav, "nav_date": candle_date(chosen), "exact_date": exact is not None}


def resolve_purchase_shares(code: str, trade_date: str, amount: float) -> dict | None:
    """按申购金额换算场外买入份额（份额只在当日净值已公布后才成立）。

    场外申购的份额要等该交易日（T 日）净值公布后才能确定：T 日当天只能给金额。
    净值尚未公布或无可用净值时返回 ``None``——调用方据此拒绝「现在按份额记账」，
    而不是用估算净值先把持仓写进去。

    Args:
        code: 6 位基金代码。
        trade_date: 申购交易日。
        amount: 申购金额（元）。

    Returns:
        ``{"shares", "nav", "nav_date", "exact_date"}``；无法换算返回 ``None``。
    """
    if amount <= 0:
        return None
    nav_result = resolve_nav_on_trade_date(code, trade_date)
    if nav_result is None:
        return None
    return {**nav_result, "shares": amount / nav_result["nav"]}


def candle_date(bar: dict) -> str:
    """净值/K 线记录 → ``YYYY-MM-DD``（容忍带时间的日期串）。"""
    return str(bar.get("date") or "")[:10]


def _latest_before(candidates: list[dict], target: str) -> dict | None:
    """取日期严格早于 target 的最近一条（升序列表从尾部回溯）。"""
    for bar in reversed(candidates):
        if candle_date(bar) < target:
            return bar
    return None
