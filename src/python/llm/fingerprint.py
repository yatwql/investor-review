"""LLM 缓存指纹模块 — 指纹计算与缓存 TTL 管理。"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from src.python.llm.fact_checker._constants import FACT_CHECK_RULES_VERSION
from src.python.llm.rate_caliber import PROMPT_SCHEMA_VERSION

logger = logging.getLogger("invest")

__all__ = [
    "compute_fingerprint",
    "extract_stable_holdings",
    "extract_stable_penetration",
    "build_llm_fingerprint",
    "get_cache_ttl_llm",
]


def compute_fingerprint(*args: Any) -> str:
    """计算输入数据的确定性哈希值（前 12 位），用作缓存键后缀。

    当市场行情、持仓数据变化时指纹随之改变，
    自动跳过旧缓存，无需等待 TTL 过期。
    """
    raw = json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def extract_stable_holdings(holdings_details: list[dict] | None) -> list[dict]:
    """从持仓明细中提取稳定的（无行情波动）字段。"""
    if not holdings_details:
        return []
    return [{"name": d.get("name", ""), "code": d.get("code", ""), "cost": d.get("cost", 0)} for d in holdings_details]


def extract_stable_penetration(penetrated_assets: list[dict] | None, full: bool = False) -> list[dict]:
    """从穿透资产中提取稳定的（无行情波动）字段。

    Args:
        penetrated_assets: 穿透 TOP10 资产列表
        full: 若为 True 则包含 mv/ratio/sector（用于穿透深度分析的额外区分）

    Returns:
        稳定字段的字典列表
    """
    result: list[dict] = []
    if penetrated_assets:
        for a in penetrated_assets:
            entry = {"name": a.get("name", ""), "codes": a.get("codes", [])}
            if full:
                entry["mv"] = a.get("mv", 0)
                entry["sector"] = a.get("sector", "")
                # 数据契约字段为 ratio_pct（report/penetration.py top10 产出），严格读取；
                # 缺失即 0（契约漂移由提示词构建侧告警，避免两处各自兼容）
                ratio_val = a.get("ratio_pct")
                entry["ratio"] = float(ratio_val) if isinstance(ratio_val, (int, float)) else 0.0
            result.append(entry)
    return result


RISK_SIGNAL_KEYS = ("max_drawdown_pct", "annualized_volatility", "total_return_pct", "status")
"""进指纹的风险信号键（唯一声明点；审计组件与正式指纹共用，避免口径漂移）。"""


def risk_signals_of(history_data: dict | None) -> dict:
    """从 history_data 提取进指纹的风险信号子集（不含 bars 等易变载荷）。"""
    if not history_data or not isinstance(history_data, dict):
        return {}
    return {key: history_data[key] for key in RISK_SIGNAL_KEYS if key in history_data}


def build_llm_fingerprint(
    total_mv: float = 0,
    total_cost: float = 0,
    total_profit: float = 0,
    total_today_profit: float = 0,
    holdings_details: list[dict] | None = None,
    penetrated_assets: list[dict] | None = None,
    categories: dict | None = None,
    full_penetration: bool = False,
    history_data: dict | None = None,
) -> str:
    """构建 LLM 模块的缓存指纹，统一剔除行情波动字段。

    替代 _expert_review_fingerprint / _health_check_fingerprint / _penetration_deep_fingerprint。

    使用 _extract_stable_holdings 剔除行情波动；
    穿透资产默认仅取 (name, codes)，full_penetration=True 时额外包含
    mv/sector/ratio（穿透深度分析需要穿透数据更新触发缓存失效）。

    history_data 参数提取 key 风险信号摘要加入指纹，
    使风险指标变化时自动失效 LLM 缓存。

    Args:
        total_mv: 总市值
        total_cost: 总成本
        total_profit: 总盈亏
        total_today_profit: 本日盈亏
        holdings_details: 持仓明细（仅提取 name/code/cost）
        penetrated_assets: 穿透资产列表
        categories: 分类汇总
        full_penetration: 为 True 时穿透资产包含 mv/sector/ratio（用于穿透深度分析）
        history_data: 组合历史走势数据，仅提取 key 风险信号摘要

    Returns:
        指纹哈希值（前 12 位）
    """
    _details = extract_stable_holdings(holdings_details)
    _pen = extract_stable_penetration(penetrated_assets, full=full_penetration)

    # 从 history_data 提取 key 风险信号摘要
    _risk_signals = risk_signals_of(history_data)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("[fingerprint] history 风险信号: %s", _risk_signals)

    return compute_fingerprint(
        total_mv,
        total_cost,
        total_profit,
        total_today_profit,
        categories,
        _details,
        _pen,
        _risk_signals,
        # 提示词文本版本：标签/表头等静态文案改动也须换键（否则复用按旧口径生成的结论）
        PROMPT_SCHEMA_VERSION,
        # 事实校验规则版本：校验修正的正文会回写模块缓存（键不变），故规则语义变化
        # 也须换键，否则旧缓存里被旧规则改错的正文会继续被复用
        FACT_CHECK_RULES_VERSION,
    )


def get_cache_ttl_llm(subtype: str = "global_macro") -> float:
    """LLM 模块缓存 TTL —— **直接读缓存注册表**（本模块不持有任何映射表或默认值）。

    模块到数据类型的唯一事实在 ``core/data_registry.py``：LLM 模块的 ``data_type``
    即 ``llm_<settings_suffix>``（辩论三键在 ``_CACHE_ONLY_REGISTRY`` 里同形态）。
    因此本函数只是把模块键换成 ``data_type`` 后交给 :func:`cache.get_ttl`，
    运行时优先级也全部由注册表那一条链决定：

    1. ``config.json → cache_ttl.llm_<subtype>``（用户覆盖，最高优先）
    2. 注册表默认值（`DataModuleDef.cache_ttl`）
    3. ``CACHE_DAILY``（未注册类型兜底，同时打 WARNING 让漏登记可见）

    好处：读侧、启动清理、统计、配置模板读的是**同一份数字**，不存在「两套配置
    各写一遍、漏一处就静默借用别的模块 TTL」的漂移面。

    Args:
        subtype: LLM 模块键（global_macro / expert_review / health_check /
            penetration_deep / news_correlation / self_review / holding_change /
            debate_pro / debate_con / debate_synthesis）

    Returns:
        过期时间（秒）
    """
    from src.python.cache import get_ttl
    from src.python.core.data_registry import get_registered_data_types

    data_type = f"llm_{subtype}"
    if data_type not in get_registered_data_types():
        logger.warning(
            "[llm] 模块 %s 未在 data_registry 登记（缓存 TTL 按日级默认值处理）——新增 LLM 模块须登记 DataModuleDef",
            subtype,
        )
    return get_ttl(data_type)
