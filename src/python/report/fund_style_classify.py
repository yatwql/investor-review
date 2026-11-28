"""基金风格判定 — 基金风格分类计算。

根据持仓个股的市值+PE 数据，按六宫格风格箱判定基金风格。
三级降级链路：push2（精确）→ Tencent（可靠）→ 代码段估算（兜底）。
"""

from __future__ import annotations

import logging

from typing import Any

from src.python.core.code_utils import is_a_share_code, is_a_share_stock
from src.python.fetcher.fund_style_extended import prefetch_extended_data
from src.python.report.fund_style_base import (
    _ensure_tencent_provider_registered,
    _get_size_from_code,
    _market_cap_to_size,
    _pe_to_style,
)


logger = logging.getLogger("invest")


# ═══════════════════════════════════════════════════════════
#  单只股票风格判定
# ═══════════════════════════════════════════════════════════


def _classify_stock(
    code: str,
    market_cap: float | None,
    pe: float | None,
    industry_avg_pe: float | None = None,
) -> dict[str, Any]:
    """对单只股票进行风格判定。

    方案 A（push2 数据可用）→ 精确判定
    方案 C（数据不可用）→ 代码段降级

    Returns:
        {"size": "大盘"/"中盘"/"小盘"/"--",
         "style": "价值"/"成长"/"混合"/"--",
         "is_estimated": bool}  # True 表示使用了降级方案
    """
    if market_cap is not None and market_cap > 0:
        size = _market_cap_to_size(market_cap)
    else:
        size = _get_size_from_code(code)
        return {"size": size, "style": "混合", "is_estimated": True}

    if pe is not None and pe > 0:
        style = _pe_to_style(pe, industry_avg_pe)
        return {"size": size, "style": style, "is_estimated": False}
    else:
        return {"size": size, "style": "混合", "is_estimated": True}


# ═══════════════════════════════════════════════════════════
#  基金风格判定
# ═══════════════════════════════════════════════════════════
def _get_industry_avg_pe(codes: list[str], names_by_code: dict[str, str] | None = None) -> dict[str, float]:
    """获取每只股票对应行业的平均 PE。

    行业归属与 PE 取自**同一次** ``fetch_industry_data`` 请求（provider 的 push2
    响应本就同时带出 f127 与 f9），按行业分组后以 **中位数** 作为行业平均 PE
    基准（抗离群值）。**不得**为取 PE 再单独请求一次 push2——同一代码同一轮
    重复取数正是会话缓存要消除的浪费。

    Args:
        codes: 6 位 A 股代码列表
        names_by_code: 可选 ``{code: name}``；提供时按「A 股个股」判定，
            排除 00 前缀重叠区场外基金（如基金成分股列表含场外基金代码时）

    Returns:
        {code: industry_avg_pe, ...} 映射；
        仅包含有行业分类且 PE > 0 的股票；
        当无可用数据时返回 ``{}``（方案 C 降级走代码段估算）。
    """
    try:
        # 会话缓存变体：行业平均 PE 每个基金都要查一次，直接取数会让
        # 「取不到」的代码在多阶段重复探测（同键未命中告警噪音）。
        from src.python.fetcher.industry import fetch_industry_data_cached as fetch_industry_data
    except ImportError:
        logger.warning("行业数据 fetcher 模块不可用，行业平均 PE 功能降级")
        return {}

    if not codes:
        return {}

    try:
        # ── 第一遍：获取行业归属 + PE 数据 ──────────────────────
        code_industry: dict[str, str] = {}
        industry_pes: dict[str, list[float]] = {}

        for code in codes:
            if names_by_code is not None:
                if not is_a_share_stock(names_by_code.get(code, ""), code):
                    continue
            elif not is_a_share_code(code):
                continue

            # push2 行业分类 + 扩展行情（通过 fetcher → chain → provider 路径）。
            # 同一次请求已带回 PE（f9），无需再发一次取价请求。
            industry_data = fetch_industry_data(code)
            if not industry_data:
                continue
            industry = industry_data.get("industry", "")
            if not industry:
                continue

            pe = industry_data.get("pe")
            if pe is None or pe <= 0:
                continue

            code_industry[code] = industry
            if industry not in industry_pes:
                industry_pes[industry] = []
            industry_pes[industry].append(pe)

        if not industry_pes:
            return {}

        # ── 第二遍：计算各行业 PE 中位数 ────────────────────────
        industry_avg: dict[str, float] = {}
        for ind, pe_list in industry_pes.items():
            sorted_pe = sorted(pe_list)
            n = len(sorted_pe)
            if n == 1:
                industry_avg[ind] = sorted_pe[0]
            elif n % 2 == 1:
                industry_avg[ind] = sorted_pe[n // 2]
            else:
                industry_avg[ind] = (sorted_pe[n // 2 - 1] + sorted_pe[n // 2]) / 2.0

        # ── 第三遍：代码 → 行业平均 PE 映射 ─────────────────────
        return {code: industry_avg[ind] for code, ind in code_industry.items() if ind in industry_avg}
    except Exception:  # noqa: BLE001 — 行业平均 PE 获取异常
        logger.warning("行业平均 PE 获取异常", exc_info=True)
        return {}


def _classify_stock_styles(
    holdings: list[dict],
    reg: Any,
    industry_avg_pe_map: dict[str, float],
) -> tuple[list[dict], dict[str, float], dict[str, float], float, bool]:
    """逐只股票读取缓存数据并判定风格。

    Returns:
        (stock_styles, size_weights, style_weights, total_weight, has_estimated)
    """
    from src.python.core.provider_registry import NOT_FOUND

    stock_styles: list[dict[str, Any]] = []
    total_weight = 0.0
    size_weights: dict[str, float] = {"大盘": 0.0, "中盘": 0.0, "小盘": 0.0}
    style_weights: dict[str, float] = {"价值": 0.0, "成长": 0.0, "混合": 0.0}
    has_estimated = False

    for h in holdings:
        code = (h.get("code") or "").strip()
        name = h.get("name", "")
        ratio = abs(h.get("ratio", 0) or 0)
        if ratio <= 0:
            continue

        _cached = reg.session_cache_get("extended", code) if code and is_a_share_stock(name, code) else NOT_FOUND
        ext_data = _cached if _cached is not NOT_FOUND else None
        industry_avg_pe = industry_avg_pe_map.get(code)

        if isinstance(ext_data, dict) and ext_data:
            mc = ext_data.get("market_cap")
            pe = ext_data.get("pe")
            result = _classify_stock(code, mc, pe, industry_avg_pe)
        else:
            result = _classify_stock(code, None, None)
            result["is_estimated"] = True

        if result["is_estimated"]:
            has_estimated = True

        size = result.get("size", "--")
        style = result.get("style", "混合")

        stock_styles.append(
            {
                "name": name,
                "code": code,
                "ratio": ratio,
                "size": size,
                "style": style,
                "is_estimated": result.get("is_estimated", False),
            }
        )

        if size in size_weights:
            size_weights[size] += ratio
        if style in style_weights:
            style_weights[style] += ratio
        total_weight += ratio

    return stock_styles, size_weights, style_weights, total_weight, has_estimated


def _finalize_fund_style(
    fund_code: str,
    stock_styles: list[dict],
    total_weight: float,
    size_weights: dict[str, float],
    style_weights: dict[str, float],
    has_estimated: bool,
) -> dict[str, Any]:
    """按权重确定最终风格并组装结果。"""
    if total_weight <= 0:
        return {"code": fund_code, "style": "--", "is_estimated": False, "details": []}

    dominant_size = max(size_weights, key=lambda k: size_weights[k])
    dominant_style = max(style_weights, key=lambda k: style_weights[k])
    style_label = f"{dominant_size}{dominant_style}"

    return {
        "code": fund_code,
        "style": style_label,
        "is_estimated": has_estimated,
        "details": stock_styles,
    }


def classify_fund_style(
    fund_code: str,
    holdings: list[dict[str, Any]],
) -> dict[str, Any]:
    """判定一只基金的风格。

    Args:
        fund_code: 基金代码（仅用于日志/索引）
        holdings: [{name, code, ratio}, ...] 该基金的前 N 大持仓

    Returns:
        {"code": fund_code,
         "style": "大盘成长"/"--",
         "is_estimated": bool,
         "details": [{"name", "code", "size", "style", "ratio", "is_estimated"}, ...]}
    """
    _ensure_tencent_provider_registered()  # 惰性注册（避免模块级副作用）
    from src.python.core.provider_registry import get_registry

    reg = get_registry()

    if not holdings:
        return {"code": fund_code, "style": "--", "is_estimated": False, "details": []}

    # 获取所有持仓股票代码
    stock_codes = [h.get("code", "").strip() for h in holdings if h.get("code")]
    stock_codes = [c for c in stock_codes if c]
    names_by_code = {str(h.get("code", "")).strip(): str(h.get("name", "") or "") for h in holdings if h.get("code")}

    # 获取行业平均 PE
    industry_avg_pe_map = _get_industry_avg_pe(stock_codes, names_by_code) if stock_codes else {}

    # ── 预取阶段：并行填充 registry session_cache ──
    prefetch_extended_data(holdings, reg)

    # ── 判定阶段：逐只股票读取缓存数据判定风格 ──
    stock_styles, size_weights, style_weights, total_weight, has_estimated = _classify_stock_styles(
        holdings,
        reg,
        industry_avg_pe_map,
    )

    # ── 按权重确定最终风格 ──
    return _finalize_fund_style(
        fund_code,
        stock_styles,
        total_weight,
        size_weights,
        style_weights,
        has_estimated,
    )
