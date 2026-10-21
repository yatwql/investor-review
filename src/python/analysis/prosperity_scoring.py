"""景气度框架诊断 —— 评分内核（配置默认值 + 权重常量 + 六维打分器）。

职责边界：本模块只做**确定性打分**（入参是已就绪契约数据，出参是六维得分与依据）；
视图装配与对外入口在 ``analysis/prosperity_framework.py``（该模块 re-export 本模块的
私有名，保持既有测试与报告层 import 面不变）。

与 ``prosperity_framework.py`` 的拆分轴是「评分 vs 装配」，两侧单向依赖（装配 → 评分），无循环。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.analysis.prosperity_signals import (
    _benchmark_returns,
    _pct,
    _snapshot_holding_codes,  # noqa: F401  # re-export：迁移名保持 import 面不变
    _top10_concentration_pct,
    _turnover_proxy_pct,
)
from src.python.core.num_utils import finite_or

from ._prosperity_inputs import (  # noqa: F401 — 兼容既有导入面
    _FALLBACK_CONFIG,
    _boom_weights,
    _config_defaults_for_module,
    _fund_type_fallback_label,
    _matches,
    _sector_weight_items,
    estimated_fund_codes,
    roe_by_code_from_rows,
)

logger = logging.getLogger("invest")


# ── 默认配置（可经 config.json 的 `prosperity_framework` 段覆盖） ─────────


# 默认配置：单一事实来源为配置层（`config/_config_defaults`），本模块只做读取

DEFAULT_CONFIG: dict[str, Any] = _config_defaults_for_module()
# 评级阈值（对齐上游评分卡口径：≥80 高度契合 / 60–79 较契合 / 40–59 部分契合 / <40 不契合）
RATING_THRESHOLDS: tuple[tuple[int, str, str], ...] = (
    (80, "high_fit", "高度契合"),
    (60, "partial_fit", "较契合"),
    (40, "weak_fit", "部分契合"),
    (0, "low_fit", "不契合"),
)
# 维度权重（满分）
_W_BOOM = 25
_W_ROE = 20
_W_GLOBAL = 15
_W_LIQUIDITY = 10
_W_CONCENTRATION = 15
_W_PERFORMANCE = 15
# 低 ROE 判定阈值（ROE < 10% 视为「低位、存在修复弹性」）
_LOW_ROE_THRESHOLD = 0.10
# 全面变现天数分档（日）
_LIQUIDITY_TIERS = ((1.0, 10), (3.0, 7), (5.0, 4))
_LIQUIDITY_FLOOR = 2
# 换手代理分档（%）
_TURNOVER_TIERS = ((15.0, 7), (8.0, 5), (3.0, 3))
_TURNOVER_FLOOR = 1


def _cfg(config: dict[str, Any] | None) -> dict[str, Any]:
    """合并用户配置与默认配置（仅覆盖本模块声明的键）。"""
    merged = dict(DEFAULT_CONFIG)
    section = (config or {}).get("prosperity_framework") if isinstance(config, dict) else None
    if isinstance(section, dict):
        for key, value in section.items():
            if key in merged and isinstance(value, type(merged[key])):
                merged[key] = value
    return merged


def _rating(score_pct: int) -> tuple[str, str]:
    for threshold, key, label in RATING_THRESHOLDS:
        if score_pct >= threshold:
            return key, label
    return "low_fit", "不契合"


def _unverified_dimension(key: str, name: str, max_score: int, reason: str) -> dict[str, Any]:
    """构造「未验证」维度结果（不计分、给出可读原因）。"""
    return {
        "key": key,
        "name": name,
        "score": 0,
        "max_score": max_score,
        "status": "unverified",
        "evidence": [],
        "unverified": [reason],
    }


def _guard_dimension(build, key: str, name: str, max_score: int) -> dict[str, Any]:
    """执行单维计算；异常时降级为「未验证」维度（**不得**让单维异常拖垮整份契约）。"""
    try:
        return build()
    except Exception:
        logger.warning("[prosperity_framework] 维度「%s」计算异常，已降级为未验证", name, exc_info=True)
        return _unverified_dimension(key, name, max_score, "该维计算异常，已跳过（详见日志）")


def _score_boom(
    penetration_data: dict[str, Any] | None,
    holdings_details: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    boom, defensive, evidence, _scope = _boom_weights(penetration_data, holdings_details, cfg)
    base = _W_BOOM * min(1.0, boom / 60.0)
    penalty = _W_BOOM * defensive * 0.5 / 100.0
    score = max(0, min(_W_BOOM, round(base - penalty)))
    if boom >= 60:
        evidence.append("景气方向占比 ≥60% → 达满分档")
    elif boom > 0:
        evidence.append(f"景气方向占比 {boom:.2f}% → 按 60% 满分档线性折算")
    else:
        evidence.append("未命中任何景气关键词 → 该维 0 分")
    if defensive:
        evidence.append(f"防御/红利方向占比 {defensive:.2f}% 触发反向扣减")
    return {
        "key": "boom_cycle",
        "name": "景气方向/通胀属性",
        "score": score,
        "max_score": _W_BOOM,
        "status": "scored",
        "evidence": evidence,
        "unverified": [],
    }


def _score_roe(
    holdings_details: list[dict[str, Any]],
    financial_indicator_data: dict[str, Any] | None,
    fund_roe_estimates: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    """返回 (维度结果, {code: roe})。契约缺失 → unverified（不给分）。

    fund_roe_estimates：基金重仓股 ROE 加权推演值（`estimate_fund_roe_batch` 产出），
    仅对无直接 ROE 的基金持仓生效；推演值计入评分但在证据中标注「按框架推演」，
    并合并进返回的 roe_by_code 供持仓视角展示（渲染侧据 estimated 集合标注）。
    """
    rows = ((financial_indicator_data or {}).get("rows") or []) if financial_indicator_data else []
    if not rows:
        return (
            {
                "key": "roe_elasticity",
                "name": "ROE 低位弹性",
                "score": 0,
                "max_score": _W_ROE,
                "status": "unverified",
                "evidence": [],
                "unverified": ["未取到个股 ROE（功能开关 `stock_fundamentals`（个股基本面）默认关）→ 该维不计分"],
            },
            {},
        )

    roe_by_code = roe_by_code_from_rows(rows)
    estimable = estimated_fund_codes(fund_roe_estimates, set(roe_by_code))
    improving: set[str] = set()
    for row in rows:
        code = str(row.get("code") or "")
        if code and str(row.get("trend") or "").startswith("改善"):
            improving.add(code)

    total = sum(finite_or(getattr(d, "market_value", 0.0)) for d in holdings_details)
    estimates = fund_roe_estimates or {}
    estimated: list[tuple[str, str, float]] = []  # (name, code, covered_pct)
    low_roe_weight = 0.0
    high_roe_weight = 0.0
    missing: list[str] = []
    for d in holdings_details:
        code = getattr(d, "code", "")
        name = getattr(d, "name", code)
        weight = _pct(finite_or(getattr(d, "market_value", 0.0)), total)
        roe = roe_by_code.get(code)
        if roe is None and code in estimable:
            # 基金重仓股加权推演值：计入评分，证据标注推演属性
            est = estimates.get(code) or {}
            roe = float(est["roe"])
            roe_by_code[code] = roe
            estimated.append((name, code, float(est.get("covered_pct") or 0.0)))
        if roe is None:
            missing.append(f"{name}（{code}）")
            continue
        if roe < _LOW_ROE_THRESHOLD:
            low_roe_weight += weight
            if code in improving:
                low_roe_weight += 0.0  # 改善趋势已在证据中标注，计分见下
        else:
            high_roe_weight += weight

    improving_weight = sum(
        _pct(finite_or(getattr(d, "market_value", 0.0)), total)
        for d in holdings_details
        if getattr(d, "code", "") in improving
    )
    base = _W_ROE * min(1.0, low_roe_weight / 50.0)
    bonus = min(4.0, improving_weight / 25.0 * 4.0)
    score = max(0, min(_W_ROE, round(base + bonus)))
    evidence = [
        f"低 ROE（<{_LOW_ROE_THRESHOLD:.0%}）持仓权重 {low_roe_weight:.2f}%（按 50% 满分档折算）",
        f"ROE 年度趋势改善的持仓权重 {improving_weight:.2f}%（加分项）",
    ]
    if high_roe_weight:
        evidence.append(f"已处高位 ROE 的持仓权重 {high_roe_weight:.2f}%（框架偏好低位修复，故不加分）")
    if estimated:
        est_weight = sum(
            _pct(finite_or(getattr(d, "market_value", 0.0)), total)
            for d in holdings_details
            if getattr(d, "code", "") in {c for _, c, _ in estimated}
        )
        basis = estimates.get(estimated[0][1], {}).get("basis", "")
        basis_label = "前十大重仓" if basis == "top10_holdings" else basis
        evidence.append(
            f"基金 ROE 按重仓股加权推演：{len(estimated)} 只基金（组合权重 {est_weight:.2f}%，{basis_label}口径）——按框架推演，非基金披露口径"
        )
    unverified = []
    if missing:
        unverified.append(
            f"未取到 ROE 的标的 {len(missing)} 只：" + "、".join(missing[:5]) + ("…" if len(missing) > 5 else "")
        )
    return (
        {
            "key": "roe_elasticity",
            "name": "ROE 低位弹性",
            "score": score,
            "max_score": _W_ROE,
            "status": "partial" if missing else "scored",
            "evidence": evidence,
            "unverified": unverified,
        },
        roe_by_code,
    )


def _score_global_edge(
    penetration_data: dict[str, Any] | None,
    holdings_details: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    from src.python.core.code_utils import is_a_share_code, is_hk_stock_code

    items, covered, pen_pct, fallback_pct, fallback_count = _sector_weight_items(penetration_data, holdings_details)
    edge = sum(w for text, w in items if _matches(text, cfg["global_edge_keywords"]))

    total_mv = sum(finite_or(getattr(d, "market_value", 0.0)) for d in holdings_details)
    offshore = sum(
        finite_or(getattr(d, "market_value", 0.0))
        for d in holdings_details
        if not is_a_share_code(getattr(d, "code", "")) or is_hk_stock_code(getattr(d, "code", ""))
    )
    offshore_pct = _pct(offshore, total_mv)
    base = _W_GLOBAL * min(1.0, edge / 40.0)
    bonus = min(5.0, offshore_pct / 20.0 * 5.0)
    score = max(0, min(_W_GLOBAL, round(base + bonus)))
    return {
        "key": "global_edge",
        "name": "全球视野/中国比较优势",
        "score": score,
        "max_score": _W_GLOBAL,
        "status": "scored",
        "evidence": [
            f"命中「中国有全球比较优势」关键词的权重 {edge:.2f}%（按 40% 满分档折算；"
            f"口径同维度①（穿透底层 + 持仓自身板块叠加归一，穿透项 {pen_pct:.2f}%）",
            f"非 A 股 / 港股等境外及港股通资产占比 {offshore_pct:.2f}%（全球暴露加分，上限 5 分）",
        ],
        "unverified": [],
    }


def _is_scored_otc(signal: dict[str, Any]) -> bool:
    """场外信号是否计入④维计分池：有天数，且来源为配置上限（用户口径）或类型默认档（推演）。"""
    if signal.get("liquidation_days") is None:
        return False
    return bool(signal.get("daily_redemption_limit")) or signal.get("estimate_basis") == "type_default"


def _is_otc_default_tier(signal: dict[str, Any]) -> bool:
    """是否为类型默认档（非实测口径）的场外信号。"""
    return signal.get("estimate_basis") == "type_default" and signal.get("liquidation_days") is not None


def _score_liquidity(liquidity_signals: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not liquidity_signals:
        return {
            "key": "liquidity",
            "name": "流动性",
            "score": 0,
            "max_score": _W_LIQUIDITY,
            "status": "unverified",
            "evidence": [],
            "unverified": ["未取得流动性信号（场内变现天数需行情 K 线缓存；场外品种无赎回上限）→ 该维不计分"],
        }

    measurable = [s for s in liquidity_signals if s.get("type") == "stock" and s.get("liquidation_days") is not None]
    otc_all = [s for s in liquidity_signals if s.get("type") == "otc"]
    # 场外计入两档：配置赎回上限（用户实测口径）与类型默认档（推演口径，标非实测）
    otc_scored = [s for s in otc_all if _is_scored_otc(s)]
    otc_default_tier = [s for s in otc_all if _is_otc_default_tier(s)]
    otc_configured = [s for s in otc_scored if s not in otc_default_tier]
    otc_unscored = [s for s in otc_all if not _is_scored_otc(s)]
    assumed = [s for s in liquidity_signals if s.get("type") == "assumed_liquid"]
    scored_pool = measurable + otc_scored
    if not scored_pool:
        return {
            "key": "liquidity",
            "name": "流动性",
            "score": 0,
            "max_score": _W_LIQUIDITY,
            "status": "unverified",
            "evidence": [],
            "unverified": [
                f"无可计算的变现/赎回天数（场外 {len(otc_all)} 只 / 数据缺失按充足处理 {len(assumed)} 只）→ 该维不计分"
            ],
        }

    worst_days = max(finite_or(s.get("liquidation_days")) for s in scored_pool)
    score = _LIQUIDITY_FLOOR
    for limit, tier_score in _LIQUIDITY_TIERS:
        if worst_days < limit:
            score = tier_score
            break
    unverified = []
    if otc_unscored:
        unverified.append(f"场外品种 {len(otc_unscored)} 只（无赎回上限且类型未识别，未计入）")
    if assumed:
        unverified.append(f"成交额数据缺失、按「流动性充足」假设计算的品种 {len(assumed)} 只")
    evidence = [
        f"最差品种全额变现/赎回天数 {worst_days:.1f} 日（<1 日 → 10 分，<3 日 → 7 分，<5 日 → 4 分，否则 2 分）",
        f"可计算场内品种 {len(measurable)} 只",
    ]
    if otc_configured or otc_default_tier:
        evidence.append(
            f"场外品种计入 {len(otc_scored)} 只"
            f"（配置赎回上限 {len(otc_configured)} 只 / 类型默认档 {len(otc_default_tier)} 只——类型默认档为非实测口径）"
        )
    return {
        "key": "liquidity",
        "name": "流动性",
        "score": score,
        "max_score": _W_LIQUIDITY,
        "status": "partial" if (otc_unscored or assumed or otc_default_tier) else "scored",
        "evidence": evidence,
        "unverified": unverified,
    }


def _score_concentration(
    holdings_details: list[dict[str, Any]],
    snapshots: list[Any] | None,
    cfg: dict[str, Any],
) -> tuple[dict[str, Any], float | None, float | None]:
    concentration = _top10_concentration_pct(holdings_details)
    turnover = _turnover_proxy_pct(snapshots)
    target = float(cfg["concentration_target_pct"])

    if concentration is None:
        conc_score = None
    elif concentration <= 0:
        conc_score = None
    elif concentration <= target:
        conc_score = 8.0
    elif concentration <= target * 1.4:
        conc_score = 5.0
    else:
        conc_score = 3.0

    if turnover is None:
        turn_score = None
    else:
        turn_score = _TURNOVER_FLOOR
        for limit, tier_score in _TURNOVER_TIERS:
            if turnover >= limit:
                turn_score = tier_score
                break

    evidence: list[str] = []
    unverified: list[str] = []
    if concentration is not None:
        evidence.append(
            f"前十大集中度 {concentration:.2f}%（框架目标 ≤{target:.0f}%：达标 8 分 / 1.4 倍内 5 分 / 更高 3 分）"
        )
    else:
        unverified.append("无可计算的前十大集中度（无正市值持仓）")
    if turnover is not None:
        evidence.append(
            f"换手代理（最近两期快照持仓集合变动率）{turnover:.2f}% → {'高换手加分' if turnover >= 8 else '换手偏低'}"
        )
    else:
        unverified.append("无历史快照（<2 期）→ 换手代理不可算（周期拼接子项不计分）")

    if conc_score is None and turn_score is None:
        status, score = "unverified", 0
    elif conc_score is None or turn_score is None:
        status = "partial"
        score = round((conc_score or 0.0) + (turn_score or 0.0))
    else:
        status, score = "scored", round(conc_score + turn_score)
    score = max(0, min(_W_CONCENTRATION, score))
    return (
        {
            "key": "concentration_cycle",
            "name": "集中度与周期拼接",
            "score": score,
            "max_score": _W_CONCENTRATION,
            "status": status,
            "evidence": evidence,
            "unverified": unverified,
        },
        concentration,
        turnover,
    )


def _score_performance(history_data: dict[str, Any] | None) -> dict[str, Any]:
    data = history_data or {}
    status = data.get("status")
    # status: ok（正常）/ degraded（部分持仓缺失，收益口径可用但需标注）/ unavailable（不可用）
    if not data or data.get("total_return_pct") is None or status not in (None, "ok", "degraded"):
        return {
            "key": "performance",
            "name": "业绩与回撤印证",
            "score": 0,
            "max_score": _W_PERFORMANCE,
            "status": "unverified",
            "evidence": [],
            "unverified": ["无可用组合历史走势数据（`history` 配置关闭 / status=unavailable / 样本不足）→ 该维不计分"],
        }

    total_return_pct = finite_or(data.get("total_return_pct"))
    max_drawdown_pct = abs(finite_or(data.get("max_drawdown_pct")))
    bench_pairs = _benchmark_returns(data.get("benchmarks"))
    bench_best_name, bench_best = max(bench_pairs, key=lambda x: x[1]) if bench_pairs else (None, None)

    score = 8 if total_return_pct > 0 else 3
    evidence = [f"组合区间累计收益 {total_return_pct:+.2f}%"]
    if bench_best is not None:
        label = f"{bench_best_name} {bench_best:+.2f}%" if bench_best_name else f"{bench_best:+.2f}%"
        if total_return_pct >= bench_best:
            score += 4
            evidence.append(f"跑赢最强对比基准（{label}）→ 加分")
        else:
            evidence.append(f"未跑赢最强对比基准（{label}）")
    elif data.get("benchmarks"):
        evidence.append("对比基准数据不可解析，仅按组合自身收益/回撤计分")
    drawdown_available = bool(data.get("drawdown_available", True))
    if drawdown_available:
        if max_drawdown_pct <= 15:
            score += 3
            evidence.append(f"最大回撤 {max_drawdown_pct:.2f}%（≤15% → 加分；框架视回撤为进攻性资产的自然结果）")
        elif max_drawdown_pct <= 25:
            score += 1
            evidence.append(f"最大回撤 {max_drawdown_pct:.2f}%（≤25% → 小幅加分）")
        else:
            evidence.append(f"最大回撤 {max_drawdown_pct:.2f}%（>25%）")
    else:
        evidence.append("历史样本不足（<60 交易日）→ 回撤子项未计分（收益部分仍计入）")

    unverified = []
    if status == "degraded":
        unverified.append("组合历史数据 status=degraded（部分持仓缺历史），收益/回撤口径可能不完整")
    if not drawdown_available:
        unverified.append("历史样本不足（<60 交易日）→ 回撤子项不计分")
    return {
        "key": "performance",
        "name": "业绩与回撤印证",
        "score": max(0, min(_W_PERFORMANCE, score)),
        "max_score": _W_PERFORMANCE,
        "status": "partial" if unverified else "scored",
        "evidence": evidence,
        "unverified": unverified,
    }
