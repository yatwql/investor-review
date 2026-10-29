"""Web 持仓录入：表单变更 → 预览 → 确认写回。

与 TUI 渠道共用同一套单源：

- 编解码/成本口径/写回契约 → :mod:`src.python.core.holdings_editor`
- 交易日 → 官方净值、金额 → 份额 → :mod:`src.python.fetcher.nav_lookup`

Web 侧**不持有服务端草稿**：浏览器保存变更清单（intent 列表），服务端每次
preview/save 都用它重放一份内存副本——避免引入进程级会话状态，也不会出现
「多标签页共用一份草稿互相覆盖」。写前 mtime 闸门 + ``.bak`` 与 TUI 一致。

变更清单元素（浏览器 → 服务端）::

    {"account": "股票账户", "code": "600919", "name": "江苏银行",
     "side": "buy", "shares": 100, "amount": None,
     "price": 10.2, "trade_date": "2026-10-29", "asset_kind": "exchange"}
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from src.python.core.holdings_editor import (
    PRICE_KIND_EXCHANGE,
    PRICE_KIND_OTC,
    SIDE_BUY,
    SIDE_SELL,
    HoldingsBook,
    TradeIntent,
    ambiguous_price_kind,
    load_book,
    price_kind,
)
from src.python.core.reader import HOLDINGS_HEADER

logger = logging.getLogger("invest")

#: 单次提交的变更上限（防止异常请求把页面/内存打爆）
MAX_INTENTS = 50


class HoldingsEditError(ValueError):
    """持仓录入参数/状态错误。

    ``code`` 供 handler 映射错误信封：默认 ``BAD_PARAM``（400），
    写前发现文件已被他人改动时为 ``HOLDINGS_STALE``（409）。
    """

    def __init__(self, message: str, *, code: str = "BAD_PARAM") -> None:
        super().__init__(message)
        self.code = code


# ── 文件与总览 ────────────────────────────────────────────


def _holdings_path() -> str:
    """当前正式持仓文件路径（不存在即报错，不在 Web 侧兜底选文件）。"""
    from src.python.config import resolve_holdings_path

    path = resolve_holdings_path()
    if not os.path.isfile(path):
        raise HoldingsEditError(f"持仓文件不存在：{os.path.basename(path)}（请先在配置里指定持仓目录与文件名）")
    return path


def build_overview() -> dict:
    """持仓总览（账户 → 行）+ 文件 mtime，供表单选择账户/已有标的。"""
    path = _holdings_path()
    book = load_book(path)
    return {
        "file": os.path.basename(path),
        "mtime": os.path.getmtime(path),
        "header": list(HOLDINGS_HEADER),
        "accounts": _accounts_payload(book),
        "rows_total": book.total_rows(),
    }


def _accounts_payload(book: HoldingsBook) -> list[dict]:
    """账户清单（含行明细与未保存标记，供前端渲染与选择）。"""
    return [
        {
            "account": account,
            "dirty": account in book.dirty_accounts(),
            "rows": [
                {
                    "name": row.name,
                    "code": row.code,
                    "shares": float(row.shares),
                    "cost": float(row.cost_price),
                    "dirty": book.is_dirty(account, row.code),
                }
                for row in rows
            ],
        }
        for account, rows in book.accounts.items()
    ]


# ── 变更清单解析 ──────────────────────────────────────────


def _parse_intents(payload: dict) -> list[TradeIntent]:
    """浏览器变更清单 → TradeIntent 列表（逐条校验，价格/份额按品种补全）。

    Raises:
        HoldingsEditError: 条目结构非法、数量超限或取不到官方净值。
    """
    raw_intents = payload.get("intents")
    if not isinstance(raw_intents, list) or not raw_intents:
        raise HoldingsEditError("变更清单为空：先添加至少一笔买入或卖出")
    if len(raw_intents) > MAX_INTENTS:
        raise HoldingsEditError(f"单次最多提交 {MAX_INTENTS} 笔变更")

    intents: list[TradeIntent] = []
    for index, raw in enumerate(raw_intents, 1):
        if not isinstance(raw, dict):
            raise HoldingsEditError(f"第 {index} 笔格式不合法")
        intents.append(_parse_intent(raw, index))
    return intents


def _parse_intent(raw: dict, index: int) -> TradeIntent:
    """单笔：字段校验 + 品种形态判定 + 价格/份额补全。"""
    account = str(raw.get("account") or "").strip()
    code = str(raw.get("code") or "").strip()
    name = str(raw.get("name") or "").strip()
    side = str(raw.get("side") or "").strip()
    if not account:
        raise HoldingsEditError(f"第 {index} 笔缺少账户")
    if not code:
        raise HoldingsEditError(f"第 {index} 笔缺少证券代码")
    if side not in (SIDE_BUY, SIDE_SELL):
        raise HoldingsEditError(f"第 {index} 笔方向非法（应为 buy / sell）")

    kind = _resolve_kind(raw, code, name, index)
    trade_date = _resolve_trade_date(raw, kind, index)
    shares, price = _resolve_amount_and_price(raw, code, kind, trade_date, side, index)
    return TradeIntent(
        account=account,
        name=name or code,
        code=code,
        side=side,
        shares=shares,
        price=price,
        trade_date=trade_date,
    )


def _resolve_kind(raw: dict, code: str, name: str, index: int) -> str:
    """品种价格形态：歧义区（00 重叠）要求前端显式给出 asset_kind。"""
    declared = str(raw.get("asset_kind") or "").strip()
    if declared in (PRICE_KIND_EXCHANGE, PRICE_KIND_OTC):
        return declared
    if not ambiguous_price_kind(code, name):
        return price_kind(code, name)
    raise HoldingsEditError(f"第 {index} 笔（{name or code}）需选择品种属性：场内证券 或 场外基金")


def _resolve_trade_date(raw: dict, kind: str, index: int) -> str:
    """交易日：场外必填；场内缺省当天。"""
    from src.python.fetcher.nav_lookup import normalize_trade_date

    text = str(raw.get("trade_date") or "").strip()
    if not text:
        if kind == PRICE_KIND_OTC:
            raise HoldingsEditError(f"第 {index} 笔场外产品必须填写交易日")
        return date.today().isoformat()
    try:
        return normalize_trade_date(text)
    except ValueError as e:
        raise HoldingsEditError(f"第 {index} 笔{e}") from e


def _resolve_amount_and_price(
    raw: dict, code: str, kind: str, trade_date: str, side: str, index: int
) -> tuple[float, float]:
    """按「按份额 / 按金额」与品种，补全份额与每份价格。"""
    price_raw = raw.get("price")
    amount_raw = raw.get("amount")
    shares_raw = raw.get("shares")

    if amount_raw not in (None, "") and kind == PRICE_KIND_OTC and side == SIDE_BUY:
        return _resolve_by_amount(code, trade_date, amount_raw, index)

    shares = _positive(shares_raw, f"第 {index} 笔份额")
    if price_raw not in (None, ""):
        return shares, _positive(price_raw, f"第 {index} 笔价格")
    return shares, _official_price(code, kind, trade_date, index)


def _resolve_by_amount(code: str, trade_date: str, amount_raw: Any, index: int) -> tuple[float, float]:
    """场外按金额：份额 = 金额 / 该交易日官方净值（净值未公布即本笔不成立）。"""
    from src.python.fetcher.nav_lookup import resolve_purchase_shares

    amount = _positive(amount_raw, f"第 {index} 笔申购金额")
    result = resolve_purchase_shares(code, trade_date, amount)
    if result is None:
        raise HoldingsEditError(
            f"第 {index} 笔：{trade_date} 的官方净值尚未公布（或为非交易日），无法把金额换算成份额，请改用按份额"
        )
    return float(result["shares"]), float(result["nav"])


def _official_price(code: str, kind: str, trade_date: str, index: int) -> float:
    """未填价格时的官方价：场内取当前行情，场外取交易日净值。"""
    if kind == PRICE_KIND_EXCHANGE:
        from src.python.fetcher.price import fetch_market_data

        data = fetch_market_data(code) or {}
        try:
            price = float(data.get("price") or 0.0)
        except (TypeError, ValueError):
            price = 0.0
        if price <= 0:
            raise HoldingsEditError(f"第 {index} 笔未取到当前行情，请手填成交价")
        return price

    from src.python.fetcher.nav_lookup import resolve_nav_on_trade_date

    result = resolve_nav_on_trade_date(code, trade_date)
    if result is None:
        raise HoldingsEditError(f"第 {index} 笔取不到 {trade_date} 的官方净值，请手填价格或改日期")
    return float(result["nav"])


def _positive(value: Any, label: str) -> float:
    """正数解析（份额 / 金额 / 价格共用）。"""
    try:
        number = float(value)
    except (TypeError, ValueError) as e:
        raise HoldingsEditError(f"{label}应为数字") from e
    if number <= 0:
        raise HoldingsEditError(f"{label}必须大于 0")
    return number


# ── 预览与写回 ────────────────────────────────────────────


def preview(payload: dict) -> dict:
    """把变更清单重放到内存副本，返回写回后的持仓与差异摘要（**不写文件**）。"""
    path = _holdings_path()
    before, after = _replay(path, payload)
    return {
        "file": os.path.basename(path),
        "mtime": os.path.getmtime(path),
        "accounts": _accounts_payload(after),
        "diff": _diff_summary(before, after),
        "rows_total": after.total_rows(),
    }


def save(payload: dict) -> dict:
    """确认写回：mtime 闸门 → 备份 → 重放 → 原子写盘（回读校验在编辑层内）。"""
    from src.python.web.holdings_update import backup_holdings_file

    path = _holdings_path()
    base_mtime = payload.get("base_mtime")
    if base_mtime is not None:
        try:
            stale = abs(os.path.getmtime(path) - float(base_mtime)) > 1e-6
        except (TypeError, ValueError) as e:
            raise HoldingsEditError("base_mtime 格式非法") from e
        if stale:
            raise HoldingsEditError(
                "持仓文件已被其他程序修改，请刷新后重试（避免覆盖他人的改动）",
                code="HOLDINGS_STALE",
            )

    book = load_book(path)
    intents = _parse_intents(payload)
    for intent in intents:
        book.apply(intent)

    backup = backup_holdings_file(path)
    append_flows = bool(payload.get("append_flows"))
    book.save(append_flows=append_flows)
    logger.info("[web-holdings] 已保存 %d 笔变更（记流水=%s）→ %s", len(intents), append_flows, path)
    return {
        "saved": len(intents),
        "append_flows": append_flows,
        "backup": os.path.basename(backup) if backup else "",
        "file": os.path.basename(path),
        "rows_total": book.total_rows(),
    }


def _replay(path: str, payload: dict) -> tuple[HoldingsBook, HoldingsBook]:
    """返回（写回前基线, 重放变更后的副本）——两个独立实例，供差异对比。"""
    before = load_book(path)
    after = load_book(path)
    for intent in _parse_intents(payload):
        after.apply(intent)
    return before, after


def _diff_summary(before: HoldingsBook, after: HoldingsBook) -> dict:
    """按 (账户, 代码) 对比前后，给出 新增 / 更新 / 移除 三档计数。"""

    def keyed(book: HoldingsBook) -> dict[tuple[str, str], tuple[float, float]]:
        return {
            (account, row.code): (float(row.shares), float(row.cost_price))
            for account, rows in book.accounts.items()
            for row in rows
        }

    old, new = keyed(before), keyed(after)
    updated = [
        key
        for key in set(old) & set(new)
        if abs(old[key][0] - new[key][0]) > 1e-9 or abs(old[key][1] - new[key][1]) > 1e-9
    ]
    return {
        "added": len(set(new) - set(old)),
        "updated": len(updated),
        "removed": len(set(old) - set(new)),
    }
