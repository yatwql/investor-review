"""再平衡信号计算模块。

支持：
  - 目标配置 Schema（大类 + 品种级）
  - 权益/固收超大类偏离计算
  - 读取/计算当前大类/品种偏离度
  - 结构化输出再平衡信号

架构约束：
  ⚠️ 禁止导入 report/ 包下的任何模块。
  通过 code_utils.py 获取资产分类函数，保持与报告层的完全解耦。

目标配置 Schema（config.json → rebalance.target_allocation）：
  {
    "大类名称": {"min": 30, "max": 70, "target": 50},
    "品种代码": {"min": 0, "max": 15, "target": 10}
  }
  键为大类名称（如 "equity"）或证券代码（品种级配置）。
  配置为空 {} 时 = 不启用目标配置检查。

资产分类系统：
  大类名称        | 包含品种
  ----------------|--------------------------
  equity          | A 股、港股通、场内 ETF（股票型）
  fund_equity     | 场外股票型/混合型基金
  fixed_income    | 债券、纯债基金、短债
  money_market    | 货币基金、现金管理
  alternative     | 商品 ETF、REITs、可转债
  qdii            | QDII 基金（含隐式海外）
  others          | 未分类品种
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.core.code_utils import (
    is_a_share_code,
    is_bond_fund_by_name,
    is_exchange_fund_code,
    is_hk_stock_code,
    is_index_fund_by_name,
    is_money_fund_by_name,
    is_otc_fund_by_name,
    is_qdii_extended,
    is_convertible_bond_by_name,
    is_etf_by_name_or_code,
)
from src.python.config._core import get_config
from src.python.core.trading_calendar import count_trading_days_elapsed
from src.python.analysis._silence import (
    _SILENCE_FILE,  # noqa: F401  # re-export，conftest 通过 rebalance._SILENCE_FILE 重定向
    _load_silence_state,  # noqa: F401  # re-export，test_rebalance / test_rebalance_edge 引用
    _save_silence_state,  # noqa: F401  # re-export，test_rebalance / test_rebalance_edge 引用
)

from src.python.analysis._silence import (  # noqa: E402, F401 — 兼容既有导入面
    _filter_silenced_signals,
    _update_silence_state,
)
from ._rebalance_deviation import (  # noqa: E402, F401 — 兼容既有导入面
    MIN_NEW_POSITION_TRADING_DAYS,
    _CATEGORY_ORDER,
    _CATEGORY_LABELS,
    _EQUITY_FI_GROUPS,
    _apply_false_positive_protection,
    _compute_confidence,
    _categorize_holdings,
    _calc_category_weights,
    _calc_group_weights,
    _build_category_deviation_signals,
    _build_security_deviation_signals,
    compute_target_deviation,
    _build_equity_fi_signals,
    equity_fixed_income_deviation,
    _compute_single_overflow_signals,
    compute_rebalance_signals,
)

logger = logging.getLogger("invest")

__all__ = [
    "classify_holding",
    "compute_target_deviation",
    "equity_fixed_income_deviation",
    "compute_rebalance_signals",
    "resolve_rebalance_config",
    "build_holding_trading_days",
]


# ── 预设阈值集 ──────────────────────────────────────────────────
# key: profile 名称 → {threshold, deviation_threshold}
_REBALANCE_PROFILES: dict[str, dict[str, float]] = {
    "conservative": {"threshold": 0.10, "deviation_threshold": 0.03},
    "moderate": {"threshold": 0.15, "deviation_threshold": 0.05},
    "aggressive": {"threshold": 0.25, "deviation_threshold": 0.08},
}


def resolve_rebalance_config(rebalance_config: dict[str, Any] | None) -> dict[str, Any]:
    """解析再平衡配置，应用预设阈值集。

    当 profile 为 "conservative" / "moderate" / "aggressive" 时，
    用预设值覆盖 threshold 和 deviation_threshold（除非已在 config 中显式指定）。
    当 profile 为 "custom" 或未匹配时，使用 config 中的独立值。

    Args:
        rebalance_config: 原始 rebalance 配置段（可能为 None）

    Returns:
        解析后的配置字典（含 threshold、deviation_threshold、target_allocation 等）
    """
    if rebalance_config is None:
        config = get_config()
        rebalance_config = config.get("rebalance", {})
    result = dict(rebalance_config)

    profile = result.get("profile", "moderate")
    if profile in _REBALANCE_PROFILES:
        preset = _REBALANCE_PROFILES[profile]
        # 预设值作为默认值，用户显式指定的值优先（已在 config 中）
        result.setdefault("threshold", preset["threshold"])
        result.setdefault("deviation_threshold", preset["deviation_threshold"])
    else:
        # custom 或未知 profile → 使用独立配置值
        result.setdefault("threshold", 0.15)
        result.setdefault("deviation_threshold", 0.05)

    result.setdefault("target_allocation", {})
    result.setdefault("silence_days", 30)
    return result


def build_holding_trading_days(
    transactions: list[Any] | None,
    trading_day: str,
) -> dict[str, int]:
    """按代码统计自首次买入到基准交易日的持仓交易日数。

    数据来源为持仓 Excel 可选「交易流水」页签：取每个代码最早一条买入
    （`action == "buy"`）记录的日期，与基准交易日之间按**交易日**计数。
    不用自然日差——长假会把自然日差显著放大（如春节前后相邻的两个交易日
    相差逾一周），按自然日会把刚建仓的品种误判为已过观察期。

    Args:
        transactions: TradeRecord 列表（可为 None / 空），记录需含 code/date/action。
        trading_day: 基准交易日（YYYY-MM-DD），通常取 get_last_trading_day()。

    Returns:
        {code: 持仓交易日数}。无买入记录或日期非法的代码不出现在结果中——
        消费方按「未知则不做观察期过滤」处理，宁可不抑制也不误抑制。
    """
    if not transactions:
        return {}

    first_buy: dict[str, str] = {}
    for t in transactions:
        if getattr(t, "action", "") != "buy":
            continue
        code = str(getattr(t, "code", "") or "")
        # 流水页签允许 YYYY/MM/DD 形态，归一化为 YYYY-MM-DD（与交易日历口径一致）
        date = str(getattr(t, "date", "") or "").replace("/", "-")
        if not code or not date:
            continue
        if code not in first_buy or date < first_buy[code]:
            first_buy[code] = date

    trading_days: dict[str, int] = {}
    for code, date in first_buy.items():
        elapsed = count_trading_days_elapsed(date, trading_day)
        if elapsed is not None:
            trading_days[code] = elapsed
    return trading_days


# ── 误报防护 ────────────────────────────────────────────────────


# ── 资产分类 —──────────────────────────────────────────────────


def classify_holding(name: str, code: str) -> str:
    """对单个持仓进行资产大类分类。

    Args:
        name: 持仓名称
        code: 证券代码

    Returns:
        大类名称: equity / fund_equity / fixed_income / money_market /
                  alternative / qdii / others
    """
    # 可转债优先于 ETF/LOF 判定（代码以 1 开头，与 ETF 同区间）
    if is_convertible_bond_by_name(name):
        return "alternative"

    # QDII 判定（含隐式海外基金）
    if is_qdii_extended(name):
        return "qdii"

    # 货币基金
    if is_money_fund_by_name(name):
        return "money_market"

    # 债券基金（需在 QDII 之后，因为部分 QDII 债券基金含 "债" 字但不属纯债）
    if is_bond_fund_by_name(name):
        return "fixed_income"

    # 场内 ETF/LOF → 按代码细分（优先于 A 股判断）
    if is_exchange_fund_code(code):
        if is_etf_by_name_or_code(name, code):
            # 债券 ETF → 固收；货币 ETF → 货币；其余 → 权益
            if is_bond_fund_by_name(name):
                return "fixed_income"
            if is_money_fund_by_name(name):
                return "money_market"
            return "equity"
        return "alternative"  # LOF/Reits 等归入 alternative

    # 场外基金（名称匹配 + 00 代码重叠区判断，放在 A 股检查前）
    if is_otc_fund_by_name(name, code) or is_index_fund_by_name(name):
        if is_bond_fund_by_name(name):
            return "fixed_income"
        return "fund_equity"

    # A 股 / 港股通 → 权益
    if is_a_share_code(code) or is_hk_stock_code(code):
        return "equity"

    # 默认归入权益类基金
    return "fund_equity"


# ── 目标配置偏离度计算 ─────────────────────────────────────────


# ── 权益/固收偏离 ────────────────────────────────────────────


# ── 再平衡信号入口（整合单品超限 + 目标偏离 + 权益/固收偏离） ─

