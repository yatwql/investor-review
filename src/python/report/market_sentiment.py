"""市场情绪与资金热点 —— 报告层装配（开关 ``market_sentiment``，默认关）。

链路：同花顺官方（龙虎榜 + 连板梯队，经 ``fetcher/market_sentiment.py`` 网关取数，
不直连 provider）→ ``analysis/market_sentiment.py`` 纯装配（只保留命中持仓/穿透
标的的事件行）→ 数据契约 ``market_sentiment_data``。

降级与闸门：
  - 功能开关关闭 → 返回 ``None``（章节隐藏，零网络开销）
  - 缺凭据 / 两源皆不可用 / 无标的命中 → ``available=False`` 的降级契约（写占位，不阻断主链路）
  - 取数带 1 小时缓存 + 链路熔断/过期缓存降级（``sentiment_lhb`` / ``sentiment_ladder``，
    随菜单刷新与 TTL 管理，实现细节在取数网关与 Provider Chain）
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.analysis.market_sentiment import build_market_sentiment, tracked_targets
from src.python.fetcher.market_sentiment import (
    credential_missing as _credential_missing,
    fetch_dragon_tiger as _fetch_dragon_tiger,
    fetch_limit_up_ladder as _fetch_limit_up_ladder,
)

logger = logging.getLogger("invest")


def build_market_sentiment_data(
    holdings: list,
    penetrated_assets: list | None,
    config: dict | None = None,
) -> dict[str, Any] | None:
    """装配市场情绪契约（开关关闭返回 ``None``）。"""
    from src.python.config import is_enable_market_sentiment

    if not is_enable_market_sentiment():
        return None
    if _credential_missing() is not None:
        return {
            "available": False,
            "reason": "未配置同花顺 API key（详见数据源可用性矩阵）",
            "trade_date": "",
            "summary": {},
            "rows": [],
            "failures": [],
            "entry_count": 0,
        }

    dragon_tiger = _fetch_dragon_tiger()
    ladder = _fetch_limit_up_ladder()
    if dragon_tiger or ladder:
        # provider 级归属已由 fetch_with_fallback 在链路内登记；
        # 这里只补类别级取用标记（数据源说明表「本次使用」）
        from src.python.report.data_status import mark_data_used

        mark_data_used("sentiment")

    targets = tracked_targets(holdings, penetrated_assets)
    contract = build_market_sentiment(dragon_tiger, ladder, targets)
    # 命中 0 条有三种截然不同的成因：源无条目 / 跟踪标的为空 / 当日确无交集。
    # 只写「命中 0 条」时事后无法区分（本次实测 0 命中，源侧 72+30 条、跟踪 12 只），
    # 故把两侧规模一并落日志。
    logger.info(
        "[market_sentiment] 命中 %d 条（龙虎榜 %d 只 / 连板梯队 %d 只 ∩ 跟踪标的 %d 只），交易日 %s",
        contract["entry_count"],
        _dragon_tiger_stock_count(dragon_tiger),
        _ladder_member_count(ladder),
        len(targets),
        contract["trade_date"] or "未知",
    )
    return contract


def _dragon_tiger_stock_count(dragon_tiger: dict[str, Any] | None) -> int:
    """龙虎榜条目数（文档契约：``stock_items`` 逐只）。"""
    return sum(1 for item in (dragon_tiger or {}).get("stock_items") or [] if isinstance(item, dict))


def _ladder_member_count(ladder: dict[str, Any] | None) -> int:
    """连板梯队最新一日的成员数（``item[0].boards`` 各板位成员合计）。"""
    items = [i for i in ((ladder or {}).get("item") or []) if isinstance(i, dict)]
    if not items:
        return 0
    boards = items[0].get("boards") or {}
    if not isinstance(boards, dict):
        return 0
    return sum(len(members) for members in boards.values() if isinstance(members, list))


__all__ = ["build_market_sentiment_data"]
