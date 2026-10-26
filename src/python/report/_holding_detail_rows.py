"""持仓明细行的单一装配点 — 编排路径与行动建议路径共用。

两处消费方要的是同一批持仓字段，只是字段集不同：

  - **编排路径**（`_orchestrator_data.prepare_report_data`）取全量，额外含行情三字段
    `change_pct` / `nav_date` / `source_api`（`with_market_fields=True`）；
  - **行动建议路径**（basic/both 的 `_action_holdings_details`）只取 10 字段子集。

过去两条路径各写一份字面量，`profit_rate` 的百分号换算与 `channel` 的渠道判定重复
实现——字段增删漏改一处，就会出现「同一持仓在行动建议与编排数据里字段不同」的
静默不一致。此处收敛为唯一构造点：共有 10 字段集中组装，行情三字段按需追加，尾部
统一附加 `holding_days`。

字段口径（对外契约，改动前先确认两侧消费方）：
  - `profit_rate`：百分比（小数 ×100，如 1.8712 → 187.12；`DetailRow.profit_rate`
    本身是小数），供 prompt 格式化与 fact_checker 校验；None 保持 None；
  - `channel`：场内/场外渠道，判定单源在 `core/holding_status.classify_channel`，
    供调仓建议可行化层按渠道取整份额与计费；
  - `account`：账户名原值（收益归因大类分解的场外渠道判定需原始关键词）；
  - `change_pct`：当日涨跌幅（%），昨收缺失或为 0 时取 0.0（不产生除零）。
"""

from __future__ import annotations

#: 两条路径共有的 10 个字段（行情三字段之外的全部）
COMMON_DETAIL_FIELDS: tuple[str, ...] = (
    "name",
    "code",
    "market_value",
    "cost",
    "profit",
    "profit_rate",
    "shares",
    "price",
    "channel",
    "account",
)

#: 仅编排路径携带的行情三字段
MARKET_DETAIL_FIELDS: tuple[str, ...] = ("change_pct", "nav_date", "source_api")


def _change_pct(price: float, yesterday_close: float) -> float:
    """当日涨跌幅（%）：昨收缺失/为 0 时返回 0.0，避免除零。"""
    if yesterday_close and abs(yesterday_close) > 1e-10:
        return (price - yesterday_close) / yesterday_close * 100
    return 0.0


def build_holding_detail_rows(
    details: list,
    *,
    with_market_fields: bool,
    transactions: list | None = None,
) -> list[dict]:
    """持仓明细（DetailRow 列表）→ 明细行字典列表。

    Args:
        details: `market_value.DetailRow` 列表。
        with_market_fields: True 时追加 `change_pct` / `nav_date` / `source_api`
            （编排路径）；False 时只出 10 字段子集（行动建议路径）。
        transactions: 交易流水记录（可为 None）；提供时附加 `holding_days`
            （再平衡误报防护的「新买入品种观察期」判据）。

    Returns:
        明细行字典列表，顺序与 `details` 一致；字段顺序：共有 10 字段按
        `COMMON_DETAIL_FIELDS` 的分组顺序（行情三字段插在 `profit_rate` 之后），
        与历史逐字面量实现的键序一致。
    """
    from src.python.core.holding_status import classify_channel

    rows: list[dict] = []
    for d in details:
        account = getattr(d, "account", "")
        row: dict = {
            "name": d.name,
            "code": d.code,
            "market_value": d.market_value,
            "cost": d.cost,
            "profit": d.profit,
            "profit_rate": (d.profit_rate * 100) if d.profit_rate is not None else None,
        }
        if with_market_fields:
            row["change_pct"] = _change_pct(d.price, d.yesterday_close)
            row["nav_date"] = d.nav_date
            row["source_api"] = d.source_api
        row["shares"] = d.shares
        row["price"] = d.price
        # 渠道上下文：判定单源在 holding_status.classify_channel（两路径同源）
        row["channel"] = classify_channel(account)
        # 账户名原值：收益归因大类分解的场外渠道判定需渠道关键词
        row["account"] = account
        rows.append(row)

    attach_holding_trading_days(rows, transactions)
    return rows


def attach_holding_trading_days(rows: list[dict], transactions: list | None) -> None:
    """为持仓明细行就地附加 holding_days（首次买入至今的交易日数）。

    再平衡误报防护的第 (2) 类「新买入品种观察期」依赖该字段。无交易流水或
    品种无买入记录时不写入该键——防护按「未知」跳过观察期过滤，宁可不抑制
    也不误抑制。

    Args:
        rows: 明细行字典列表（`build_holding_detail_rows` 产物）。
        transactions: 交易流水记录（可为 None / 空）。
    """
    if not transactions:
        return
    from src.python.analysis.rebalance import build_holding_trading_days
    from src.python.report.market_value import get_last_trading_day

    trading_days = build_holding_trading_days(transactions, get_last_trading_day())
    for row in rows:
        days = trading_days.get(row.get("code", ""))
        if days is not None:
            row["holding_days"] = days
