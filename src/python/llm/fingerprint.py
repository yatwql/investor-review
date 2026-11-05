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
    "cache_key_salts",
    "compute_fingerprint",
    "extract_stable_categories",
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


def extract_stable_categories(categories: dict | None) -> dict[str, list]:
    """从分类汇总中提取稳定结构（类型 → 排序后的 (代码, 名称) 列表）。

    分类汇总的值是 Holding 对象（含市值/盈亏/本日盈亏/占比等行情派生字段），
    直接进哈希会在每次行情刷新后换键——本函数只保留**分类结果本身**
    （某品种归到哪一类、这一类里有哪些品种），与报价无关。

    Args:
        categories: ``classify_holdings`` 产出的 {类型: [Holding, ...]}（也接受 dict 元素）

    Returns:
        {类型: [(code, name), ...]}，类型键与条目均排序以保确定性
    """
    if not categories:
        return {}
    result: dict[str, list] = {}
    for key in sorted(categories):
        raw = categories[key]
        # 只认可迭代的品种集：调用方传别的形态（如计数）属契约外，按空类处理，
        # 不让指纹构造抛异常（指纹异常会让整轮报告落不了缓存键）
        items = raw if isinstance(raw, (list, tuple, set, frozenset)) else []
        entries: list[tuple[str, str]] = []
        for item in items:
            if isinstance(item, dict):
                entries.append((str(item.get("code", "")), str(item.get("name", ""))))
            else:
                entries.append((str(getattr(item, "code", "") or ""), str(getattr(item, "name", "") or "")))
        result[str(key)] = sorted(entries)
    return result


def extract_stable_penetration(
    penetrated_assets: list[dict] | None, full: bool = False, include_sector: bool = False
) -> list[dict]:
    """从穿透资产中提取稳定的（无行情波动）字段。

    Args:
        penetrated_assets: 穿透 TOP10 资产列表
        full: 若为 True 则包含 mv/ratio/sector（**仅诊断用途**，mv/ratio 为行情派生值）
        include_sector: 若为 True 则额外包含 sector（行业归属，结构性事实，与报价无关）

    Returns:
        稳定字段的字典列表
    """
    if include_sector and full:
        raise ValueError("include_sector 与 full 互斥：full 是诊断口径，include_sector 是入键口径")
    result: list[dict] = []
    if penetrated_assets:
        for a in penetrated_assets:
            entry = {"name": a.get("name", ""), "codes": a.get("codes", [])}
            if include_sector:
                entry["sector"] = a.get("sector", "")
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
"""风险信号键（唯一声明点；**仅诊断用**，不入缓存键——见 build_llm_fingerprint 纪律）。"""


def risk_signals_of(history_data: dict | None) -> dict:
    """从 history_data 提取风险信号子集（不含 bars 等易变载荷）。

    **仅用于指纹组件诊断**（``fingerprint_components``）：这些指标由最新一根 K 线
    算出，行情刷新即变末位，入键会把缓存寿命压到分钟级。
    """
    if not history_data or not isinstance(history_data, dict):
        return {}
    return {key: history_data[key] for key in RISK_SIGNAL_KEYS if key in history_data}


def build_llm_fingerprint(
    holdings_details: list[dict] | None = None,
    penetrated_assets: list[dict] | None = None,
    categories: dict | None = None,
    full_penetration: bool = False,
    history_data: dict | None = None,
) -> str:
    """构建 LLM 模块的缓存指纹：**只锁结构与口径，不锁行情**。

    键内容（全部与报价无关，同日重跑逐字节不变）：
      - 持仓结构：name/code/cost（份额×成本价，随交易变、不随行情变）
      - 分类结构：类型 → [(code, name)]（某品种归哪类，不含市值/盈亏）
      - 穿透结构：name/codes（+ sector，full_penetration=True 时）
      - 两个版本盐（提示词文本版本 / 事实校验规则版本）

    刻意**不入键**（属行情/时效数据，由缓存 TTL 兜底；这些值仍然进提示词）：
      - 总市值/总成本/总盈亏/本日盈亏（行情派生，已不再作为入参）
      - history_data 派生风险信号（总收益/年化波动/最大回撤，由最新 K 线现算）

    为何这样切：行情派生量（含浮点末位）每次刷新都变，入键等于把 TTL 锁死在
    「行情刷新周期」（本机实测：20:49 与 22:01 两轮持仓与市值完全相同，仍因
    美股开盘后净值/风险指标变化而 4/4 全 miss）。结构与口径变了才真需要重算，
    其余交给 TTL——TTL 的语义本就允许「几小时前的结论」。

    Args:
        holdings_details: 持仓明细（提取 name/code/cost；成本由此逐笔承载）
        penetrated_assets: 穿透资产列表
        categories: 分类汇总（经 extract_stable_categories 只取分类结构）
        full_penetration: 为 True 时穿透资产额外包含 sector（行业归属，结构性字段）
        history_data: 组合历史走势数据（不参与哈希）

    Returns:
        指纹哈希值（前 12 位）
    """
    _details = extract_stable_holdings(holdings_details)
    _pen = extract_stable_penetration(penetrated_assets, include_sector=full_penetration)

    return compute_fingerprint(
        extract_stable_categories(categories),
        _details,
        _pen,
        # 提示词文本版本：标签/表头等静态文案改动也须换键（否则复用按旧口径生成的结论）
        PROMPT_SCHEMA_VERSION,
        # 事实校验规则版本：校验修正的正文会回写模块缓存（键不变），故规则语义变化
        # 也须换键，否则旧缓存里被旧规则改错的正文会继续被复用
        FACT_CHECK_RULES_VERSION,
    )


def cache_key_salts() -> dict[str, str]:
    """LLM 缓存键里的**版本盐**（进键但不进数据）——单源出口，供首尾日志与排障引用。

    两个版本号都会改变四个可回写模块与辩论键的缓存键：
      - 提示词文本版本（`rate_caliber.PROMPT_SCHEMA_VERSION`）：静态文案改动换键；
      - 事实校验规则版本（`fact_checker.FACT_CHECK_RULES_VERSION`）：校验修正会回写
        模块缓存且键不变，规则语义变化须换键，否则旧缓存里按先前规则写过的正文继续复用。

    为什么要在运行首尾打出来：模块重算的归因只有「键变了」这一信号，而版本盐是最
    省事的解释项——看不到它就要靠翻代码与比对指纹，才能判断这次整批重算是版本递增
    所致还是缓存被清理所致。
    """
    return {"prompt_schema": PROMPT_SCHEMA_VERSION, "fact_rules": FACT_CHECK_RULES_VERSION}


def log_cache_key_salts(where: str) -> None:
    """把版本盐打成一行 INFO（`where` 为「本轮开始」/「本轮结束」等位置描述）。"""
    salts = cache_key_salts()
    logger.info(
        "[llm] LLM 缓存键版本盐（%s）：提示词=%s 校验规则=%s（任一递增即整批改键重算）",
        where,
        salts["prompt_schema"],
        salts["fact_rules"],
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
