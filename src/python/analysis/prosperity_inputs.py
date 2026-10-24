"""景气度评分的输入与权重来源：配置默认值、板块权重聚合、权重/阈值常量。

从 :mod:`analysis.prosperity_scoring` 拆出——评分与诊断（各维度打分函数）
留在原模块；本模块只提供「喂给评分的词表/权重/阈值」（单向依赖：评分 → 输入）。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.analysis.prosperity_signals import (
    _pct,
)
from src.python.core.num_utils import finite_or

logger = logging.getLogger("invest")


def _config_defaults_for_module() -> dict[str, Any]:
    """从配置层单一事实来源读取默认关键词与阈值（`config/_config_defaults._DEFAULT_CONFIG`）。

    词表只维护一处（配置层），本模块不再另存一份 —— 否则两处漂移会导致
    「config.json 加了词、模块默认值里没有」这类假命中（真实持仓复核踩到）。
    配置层不可用时退回内置最小词表（保持功能可用）。
    """
    try:
        from src.python.config import _config_defaults as _cd

        section = _cd._DEFAULT_CONFIG.get("prosperity_framework") or {}
        if section:
            return {key: value for key, value in section.items() if key in _FALLBACK_CONFIG}
    except Exception:  # 配置层不可用（如极简运行环境）→ 退回内置
        logger.debug("[prosperity_framework] 配置层默认值不可读，使用内置回退词表", exc_info=True)
    return dict(_FALLBACK_CONFIG)


_FALLBACK_CONFIG: dict[str, Any] = {
    # 内置最小词表（仅当配置层不可读时使用；正常路径以配置层为准）
    "boom_keywords": [
        "光通信",
        "光模块",
        "算力",
        "数据中心",
        "液冷",
        "半导体",
        "存储",
        "芯片",
        "AI",
        "电力设备",
        "电网",
        "储能",
        "新能源",
        "电池",
        "光伏",
        "有色",
        "铜",
        "稀土",
        "军工",
        "创新药",
        "科技",
        "高端装备",
        "制造",
        "能源资源",
        "电力",
    ],
    "global_edge_keywords": [
        "光通信",
        "光模块",
        "半导体设备",
        "半导体材料",
        "芯片",
        "电力设备",
        "电网",
        "锂电",
        "电池",
        "光伏",
        "储能",
        "消费电子",
        "新能源",
        "高端装备",
        "制造",
        "电力",
    ],
    "defensive_keywords": [
        "银行",
        "白酒",
        "食品饮料",
        "公用事业",
        "红利",
        "地产",
        "房地产",
        "保险",
        "消费",
        "债",
        "货币",
        "现金",
    ],
    "concentration_target_pct": 50.0,
}


def _matches(text: str, keywords: list[str]) -> bool:
    """关键词命中（大小写不敏感的子串匹配）。"""
    lowered = str(text or "").lower()
    return any(str(k).lower() in lowered for k in keywords)


def _fund_type_fallback_label(name: str, code: str) -> str:
    """板块识别失败时的**基金类型兜底标签**（返回可被关键词匹配消费的文本）。

    背景（真实持仓复核）：`classify_sector` 依赖品种名称关键词表，QDII/联接/债基/
    宽基 ETF 等常返回 `--`，导致并集口径下大批权重"无板块信息"（实测约 51% 权重）。
    本函数按**基金类型**给出保守标签，标签文本只命中「防御」侧词或不命中任何侧
    （**绝不**把固收/宽基塞进景气侧）：

      - 债券/货币/超短债等固收 → ``债券现金``（命中 `defensive_keywords` 的「债」「货币」）
      - QDII/海外标的 → ``境外资产``（中性；境外暴露已由维度③的境外占比单独加分）
      - 宽基/指数/ETF 联接 → ``宽基指数``（中性）
      - 其余（主动权益等） → ``未分类资产``（中性）

    优先级说明：**ETF/指数判定先于货币基金判定** —— `code_utils.is_money_fund_by_name`
    对含「现金」字样的非货基（如「国证自由现金流 ETF」）也会返回 True，若先判货币会把
    场内权益 ETF 误标为固收/现金，故此处以 ETF/指数为最高优先级。
    """
    from src.python.core.code_utils import (
        is_bond_fund_by_name,
        is_convertible_bond_by_name,
        is_etf_by_name_or_code,
        is_index_fund_by_name,
        is_index_link_by_name,
        is_money_fund_by_name,
        is_qdii_extended,
    )

    if is_etf_by_name_or_code(name, code) or is_index_fund_by_name(name) or is_index_link_by_name(name):
        return "宽基指数"
    if is_qdii_extended(name):
        return "境外资产"
    if is_bond_fund_by_name(name) or is_convertible_bond_by_name(name) or is_money_fund_by_name(name):
        return "债券现金"
    return "未分类资产"


def _sector_weight_items(
    penetration_data: dict[str, Any] | None,
    holdings_details: list[dict[str, Any]],
) -> tuple[list[tuple[str, float]], float, float, float, int]:
    """构造「板块/概念 → 权重」清单（**并集口径 + 类型兜底 + 归一化**）。

    口径（含两轮真实持仓修订）：

      - **视角一（穿透底层）**：穿透 top10 每项按其 `ratio_pct` 计入；
      - **视角二（持仓自身）**：每个直接持仓按自身组合权重计入 —— 板块优先取
        `classify_sector`，识别失败（`--`，QDII/联接/债基/宽基 ETF 常见）时用
        `_fund_type_fallback_label` 的**基金类型标签**兜底（固收→防御侧、
        境外/宽基/主动权益→中性，绝不进景气侧）；**直接持有的证券**（其代码在
        top10 的 `codes` 中）已在视角一计入，视角二跳过以避免重复；
      - 两视角叠加后按合计**归一**为 100（阈值口径 = 「占合计的占比」；穿透项与
        持仓自身对同一基金会有部分重合，属口径设计，非重复计数错误）。

    Returns:
        (items, covered_pct, penetration_pct, fallback_pct, fallback_count)
    """
    from src.python.report.penetration import classify_sector

    raw: list[tuple[str, float]] = []
    top10 = (penetration_data or {}).get("top10") or []
    covered_codes: set[str] = set()
    pen_pct = 0.0
    for item in top10:
        if not isinstance(item, dict):
            continue
        text = " ".join([str(item.get("name", "")), str(item.get("sector", "")), " ".join(item.get("concepts") or [])])
        weight = finite_or(item.get("ratio_pct"))
        raw.append((text, weight))
        pen_pct += weight
        for code in item.get("codes") or []:
            covered_codes.add(str(code))
        # 注：`sources`（贡献该底层的基金）**不**加入去重集合 —— 基金持仓按其自身
        # 板块/类型标签单独计入（两视角叠加），否则基金权重只能由 top10 底层代表，
        # 实测覆盖率仅 48%（其余 52% 权重无信息）。

    total = sum(finite_or(getattr(d, "market_value", 0.0)) for d in holdings_details)
    fallback_pct = 0.0
    fallback_count = 0
    for d in holdings_details:
        code = str(getattr(d, "code", ""))
        if code and code in covered_codes:
            continue  # 已由穿透项计入，避免重复计数
        name = str(getattr(d, "name", ""))
        weight = _pct(finite_or(getattr(d, "market_value", 0.0)), total)
        sector = classify_sector(name, code)
        if sector in ("--", "", None):
            # 兜底项**只用类型标签参与关键词判定**（不带名称）：类型兜底本就是保守降级，
            # 若把名称一并带入，「自由现金流 ETF」会被防御词「现金」误命中为固收/现金。
            label = _fund_type_fallback_label(name, code)
            raw.append((label, weight))
            fallback_pct += weight
            fallback_count += 1
        else:
            raw.append((f"{sector} {name}", weight))

    covered = sum(w for _, w in raw)
    if covered <= 0:
        return [], 0.0, round(pen_pct, 2), 0.0, 0
    items = [(text, round(w / covered * 100, 2)) for text, w in raw]
    return items, round(covered, 2), round(pen_pct, 2), round(fallback_pct, 2), fallback_count


def _boom_weights(
    penetration_data: dict[str, Any] | None,
    holdings_details: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> tuple[float, float, list[str], str]:
    """返回 (景气占比, 防御占比, 证据, 口径说明)。

    口径：**并集** —— 穿透 top10 各底层标的（含基金持仓拆解）+ 未被穿透覆盖的直接持仓，
    合计覆盖≈100% 市值（见 `_sector_weight_items`）。
    """
    items, covered, pen_pct, fallback_pct, fallback_count = _sector_weight_items(penetration_data, holdings_details)
    # 互斥归类（防御优先）：同一标的可能既命中景气词又命中防御词（如「电力」与「公用事业」
    # 类文本、「债」「现金」类策略名），若各计一次会使两者之和 >100%，故按防御优先归类。
    defensive = sum(w for text, w in items if _matches(text, cfg["defensive_keywords"]))
    boom = sum(
        w for text, w in items if _matches(text, cfg["boom_keywords"]) and not _matches(text, cfg["defensive_keywords"])
    )
    scope = f"口径：穿透底层（{pen_pct:.2f}%）+ 持仓自身板块/类型，两视角叠加（合计 {covered:.2f}%）后归一"
    evidence = [
        f"{scope}",
        f"命中景气关键词的权重 {boom:.2f}%、防御/红利关键词 {defensive:.2f}%（同一标的按防御优先归类，互斥不重复计）",
        f"基金类型兜底 {fallback_count} 只（{fallback_pct:.2f}% 权重，按固收/境外/宽基等类型标签，不计入景气侧）",
    ]
    return boom, defensive, evidence, scope


def roe_by_code_from_rows(rows: list[dict[str, Any]] | None) -> dict[str, float]:
    """从财务指标契约行提取 {代码: ROE}（ROE 解析的唯一事实来源）。

    `_score_roe` / 推演集合判定 / 编排层补取免重取的 `known_roe` 三处共用本函数，
    避免同一解析规则多处各写一份而漂移（含非数值 ROE 的过滤）。
    """
    result: dict[str, float] = {}
    for row in rows or []:
        code = str(row.get("code") or "")
        roe = row.get("roe")
        if code and isinstance(roe, (int, float)):
            result[code] = float(roe)
    return result


def estimated_fund_codes(
    fund_roe_estimates: dict[str, dict[str, Any]] | None,
    direct_roe_codes: set[str] | None = None,
) -> set[str]:
    """推演值实际生效的基金代码集合（推演集合判定的唯一事实来源）。

    规则：有可用推演 roe 且**无直接 ROE**（直接口径优先）。
    评分侧（按缺直接 ROE 的持仓取用推演值）与契约说明/持仓视角标注侧共用本函数，
    避免两边各自判定“哪些是推演值”而漂移。
    """
    direct = direct_roe_codes or set()
    return {
        code
        for code, est in (fund_roe_estimates or {}).items()
        if isinstance((est or {}).get("roe"), (int, float)) and code not in direct
    }
