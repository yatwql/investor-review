"""冻结输入样本：把一次真实持仓快照转成评测可复用的固定输入。

目的：A/B 比较必须**同一份输入**，否则输出长度差异无法归因到预算。样本从
``data/history/snapshots/*.json`` 构建（离线、零网络），字段映射见 ``_holding_row``。

局限（写进产物自述）：快照不含 pipeline_data / history 序列，故
``metrics``/``pipeline_data`` 默认留空——评测比的是**同输入跨变体**的差异，绝对
长度会略短于真实报告，不影响档位之间的相对比较。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REQUIRED_KEYS = ("holdings_details", "total_mv", "total_cost", "total_profit", "holdings_count")


def _holding_row(item: dict[str, Any]) -> dict[str, Any]:
    """快照持仓行 → 提示词持仓明细行（字段对齐 ``prompts_data_blocks._fmt_holding_line``）。"""
    cost_total = float(item.get("cost_total") or 0.0)
    profit = float(item.get("total_pnl") or 0.0)
    rate = (profit / cost_total * 100) if cost_total else None
    return {
        "code": str(item.get("code") or ""),
        "name": str(item.get("name") or ""),
        "shares": float(item.get("shares") or 0.0),
        "cost": cost_total,
        "market_value": float(item.get("market_value") or 0.0),
        "profit": profit,
        "profit_rate": rate,
        "nav_date": "",
        "source_api": "",
    }


def _category_of(code: str) -> str:
    """按代码类型粗分类（仅用于提示词的【分布】段，不影响数值）。

    判定一律走 ``core/code_utils``（代码类型判定中心化约束：调用方不得内联
    前缀/长度判断，否则同一品种在不同模块会被分成两类）。
    """
    from src.python.core.code_utils import is_a_share_code, is_exchange_fund_code

    if not code:
        return "未知"
    if is_a_share_code(code):
        return "A股"
    if is_exchange_fund_code(code):
        return "场内基金"
    return "场外基金"


def build_sample_from_snapshot(snapshot_path: Path) -> dict[str, Any]:
    """从持仓快照构建冻结样本。

    Args:
        snapshot_path: ``data/history/snapshots/snapshot_*.json`` 路径。

    Returns:
        样本字典（可直接 JSON 序列化）：``holdings_details`` / ``categories`` /
        ``total_mv`` / ``total_cost`` / ``total_profit`` / ``total_today_profit`` /
        ``holdings_count`` / ``penetrated_assets`` / ``metrics`` / ``pipeline_data`` /
        ``competitive_context`` / ``sample_meta``。
    """
    try:
        snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # 文件不可读/非 JSON：评测前明确报错，不静默用空样本
        raise ValueError(f"快照读取失败：{snapshot_path}（{exc}）") from exc
    accounts = snap.get("accounts") or []
    rows: list[dict[str, Any]] = []
    for account in accounts:
        for item in account.get("holdings") or []:
            row = _holding_row(item)
            if row["code"]:
                rows.append(row)
    if not rows:
        raise ValueError(f"快照中没有可用持仓：{snapshot_path}")

    categories: dict[str, int] = {}
    for row in rows:
        key = _category_of(row["code"])
        categories[key] = categories.get(key, 0) + 1

    total_mv = sum(row["market_value"] for row in rows)
    total_cost = sum(row["cost"] for row in rows)
    sample = {
        "holdings_details": rows,
        "categories": categories,
        "total_mv": total_mv,
        "total_cost": total_cost,
        "total_profit": sum(row["profit"] for row in rows),
        "total_today_profit": 0.0,
        "holdings_count": len(rows),
        "penetrated_assets": [],
        "metrics": {},
        "pipeline_data": {},
        "competitive_context": "",
        "sample_meta": {
            "source": str(snapshot_path.name),
            "snapshot_timestamp": snap.get("timestamp"),
            "note": "pipeline_data/metrics 未冻结：跨变体同输入，比相对差异而非绝对长度",
        },
    }
    return sample


def save_sample(sample: dict[str, Any], output: Path) -> Path:
    """把样本写成 JSON（父目录自动创建）。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def load_sample(path: Path) -> dict[str, Any]:
    """读取并校验样本；缺关键键即抛 ValueError（评测前暴露样本不完整）。"""
    try:
        sample = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"样本读取失败：{path}（{exc}）") from exc
    missing = [key for key in _REQUIRED_KEYS if key not in sample]
    if missing:
        raise ValueError(f"样本缺少必需键：{missing}（{path}）")
    if not sample["holdings_details"]:
        raise ValueError(f"样本持仓明细为空：{path}")
    logger.debug("样本已加载：%s（%d 只持仓）", path, len(sample["holdings_details"]))
    return sample
