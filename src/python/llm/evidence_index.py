"""LLM 复盘的证据索引 —— 把该模块提示词里已装配的输入块，翻成可回引的稳定 id。

为什么由提示词输入块生成（而不是复用事实校验的语料）：模型只能引用它**真正看到**的
内容；索引与本模块提示词同源，才能保证「主张引用的证据」在读者侧可回指。

id 规则：`ev:<kind>:<稳定键|8 位内容哈希>`，前缀固定、长度受控，不与缓存键
（`llm_*` / `price_*`）混淆。只给一行摘要（不给全文），控制提示词增量。
"""

from __future__ import annotations

from typing import Any


def _fmt_rate(value: Any) -> str:
    """收益率展示：小数入、百分比出；非数值返回空串（不猜）。"""
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return ""


def build_evidence_index(
    *,
    holdings_details: list[dict[str, Any]] | None = None,
    penetrated_assets: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, str]:
    """装配证据索引：`{evidence_id: 一行摘要}`（按来源块顺序，稳定可复现）。

    Args:
        holdings_details: 持仓明细（消费 `code` / `name` / `profit_rate` / `price`）。
        penetrated_assets: 穿透 TOP10（消费 `name` / `codes`）。
        metrics: 量化指标（beta / sharpe / annualized_volatility / max_drawdown 等）。


    Returns:
        证据 id → 摘要；无输入时返回空 dict（调用方据此不注入索引段）。
    """
    index: dict[str, str] = {}

    for item in holdings_details or []:
        code = str(item.get("code") or "").strip()
        if not code:
            continue
        name = str(item.get("name") or code)
        rate = _fmt_rate(item.get("profit_rate"))
        index.setdefault(f"ev:hold:{code}", f"{name}（{code}）持仓{'收益率 ' + rate if rate else ''}".strip())
        price = item.get("price")
        if price is not None:
            index.setdefault(f"ev:quote:{code}", f"{name}（{code}）最新价 {price}")

    for asset in penetrated_assets or []:
        name = str(asset.get("name") or "").strip()
        codes = [str(c).strip() for c in (asset.get("codes") or []) if str(c).strip()]
        if not name or not codes:
            continue
        index.setdefault(f"ev:pen:{codes[0]}", f"穿透资产 {name}（{'/'.join(codes[:3])}）")

    for key, value in (metrics or {}).items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        index.setdefault(f"ev:metric:{key}", f"组合指标 {key} = {value}")

    return index
