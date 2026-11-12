"""判断依据章内块 — 数据装配（形态 A：行动建议章内块，纯确定性，零 LLM）。

「新章装事实，LLM 章装解释」的确定性侧单一数据源：只读 `signal_ledger` /
持仓 / 配置 / `decision_ledger`，不取外部数据、不触碰任何 LLM 链路
（设计稿 `docs/plan/investment-decision-basis-design.md` §2/§3）。

契约（数据子契约，`pipeline_data` 键 `decision_basis_data`，附录 H 登记）：
  enabled     功能开关 `decision_basis` 生效值；False → 双端完全隐藏（回滚通道）
  available   数据可用性（账本可读即 True；空账本走「暂无信号记录」空态）
  reason      不可用原因（available=False 时呈现「数据不可用：<原因>」）
  title       区块显示名「判断依据」（双端同源单一真值）
  summary     一句话结论（折叠组 summary）
  backtest_as_of 回测产物的最新运行日（YYYY-MM-DD，随 docs/tmp/decision-quality/
              产物刷新；产物缺失回落到归档结论采样日，见 backtest_run_date）
  signals     信号清单（判断类信号各一行：口径/样本/区分度/标注，见设计稿 §2.1）
  confidence  信号可信度（规则仲裁四枚举，非模型自评，只描述信号可信度不描述建议胜率）
  risk_budget 风险预算块（上限 vs 现状三行：单品种权重 / 行业权重 / 组合回撤；
              只摄上限与现状，不产动作；缺数据时 available=False + reason）
  discipline  纪律明细块（复用「交易纪律」块已产出的触发条：规则/品种/当前值/
              距阈值 + 阶段化执行口径说明；只读，不改触发逻辑）
  settlement  结算摘要块（按结算交易日聚合最近 5 批 × 5/20/60 视界均值与超额；
              未到期视界显式「未到期」，不按 0 呈现）

硬约束（设计稿 §2.1）：
  - 任何字段数值来自确定性计算（信号账本 / 持仓 / 配置），不由 LLM 生成或改写；
  - `basis`/`n_obs`/`ic`/`monotonic` 三组字段必填（可空但须显式给出）——
    缺任一则该信号不进方向轴（`in_direction_axis` 判定）；
  - 区分度三态如实标注（未回测 / 样本不足 / 已回测通过·未通过），
    无结论一律「未回测」，不填先验；
  - 首批回测结论以本模块常量登记（`BACKTEST_CONCLUSIONS`，含来源脚本、
    讨论稿指针），不新增配置键、不写运行时账本、不散落硬编码；
  - 回测采样日不写死常量：由 `backtest_run_date()` 读产物日期派生，
    产物缺失才回落 `BACKTEST_DATE_FALLBACK`；
  - 零 LLM 依赖：装配与仲裁函数不接任何 LLM 参数，`enable_llm` 两态输出一致。
"""

from __future__ import annotations

from typing import Any

from src.python.analysis.portfolio_constraints import evaluate_constraints, max_single_weight, status_of
from src.python.config import get_config
from src.python.config.features import is_feature_enabled

# ── 子模块 re-export（聚合门面：对外导入面不变）────────────────
from src.python.report.decision_basis_settlement import (  # noqa: F401
    PERFORMANCE_TITLE,
    SETTLEMENT_HORIZONS,
    SETTLEMENT_MAX_BATCHES,
    _mean,
    _tone_class_of,
    _tone_of,
    build_performance,
    build_settlement_summary,
    performance_verdict,
)
from src.python.report.decision_basis_signals import (  # noqa: F401
    BACKTEST_CONCLUSIONS,
    _build_signal_rows,
    BACKTEST_DATE_FALLBACK,
    BACKTEST_REF,
    BACKTEST_SOURCE,
    DISCRIMINATION_FAILED,
    DISCRIMINATION_INSUFFICIENT,
    DISCRIMINATION_NOT_BACKTESTED,
    DISCRIMINATION_PASSED,
    PERF_PHASE_ASSEMBLY,
    SIGNAL_TYPES,
    _BASIS_LABELS,
    _BASIS_PRICE_PROXY,
    _BASIS_VALUATION_REAL,
    _DEFAULT_CONCLUSION,
    _DIRECTION_ENUM,
    _DIRECTION_LABELS,
    _DISCRIMINATION_LABELS,
    backtest_run_date,
    in_direction_axis,
)

#: 功能开关名（登记见 config/_feature_registry.py，TUI [C] 面板可切换）
FEATURE_FLAG = "decision_basis"
#: 区块显示名（双端同源；归一化名与 section_block_registry 清单一致）
BLOCK_TITLE = "判断依据"

#: 可信度等级标签（规则四枚举的展示名）
_LEVEL_LABELS: dict[str, str] = {"high": "高", "medium": "中", "low": "低", "unknown": "暂不可判"}
#: 可信度 → data-status 语义色（ok/warn/info，不用涨跌域色；设计契约）
_LEVEL_STATUS_CLASS: dict[str, str] = {
    "high": "data-status-ok",
    "medium": "data-status-info",
    "low": "data-status-warn",
    "unknown": "data-status-info",
}


def is_decision_basis_enabled() -> bool:
    """开关 `decision_basis` 生效值（默认开——纯事实块，不增加风险）。"""
    return is_feature_enabled(FEATURE_FLAG)


# ── 风险预算（上限 vs 现状：只读呈现，不产动作）──────────
# 分工：本块只摆「上限 / 现状 / 是否超限」，超限之后的动作在「再平衡信号」块，
# 两处不重复动作文案（同一阈值表）。行业上限无可配置键 → 显式「未配置上限」，不臆造。
RISK_ITEM_SINGLE = "单品种权重"
RISK_ITEM_INDUSTRY = "行业权重"
RISK_ITEM_DRAWDOWN = "组合回撤"
RISK_UNCONFIGURED = "未配置上限"
RISK_UNEVALUATED = "未评估"


def _fmt_pct(value: float | None) -> str:
    """百分比展示（百分数数值口径，与 `discipline.*_pct` 同源；None → —）。"""
    return "—" if value is None else f"{value:g}%"


def _to_float(value: Any, default: float = 0.0) -> float:
    """配置值 → float（非数值/缺失回退默认值，不抛错：配置由用户手改）。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_risk_budget(
    holdings_details: list[dict[str, Any]] | None = None,
    total_mv: float | None = None,
    portfolio_peak_mv: float | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """装配风险预算块（单品种 / 行业 / 回撤三行，上限与现状各自可缺）。

    阈值来源单一：单品种取 `rebalance.threshold`（经 `resolve_rebalance_config`
    应用 profile 预设）、回撤取 `discipline.drawdown_pct`（经
    `resolve_discipline_config` 填充默认值），不新增配置键；行业上限无配置键，
    固定显式「未配置上限」。

    Args:
        holdings_details: 持仓明细行（含 market_value/name/code）。
        total_mv: 组合总市值（≤ 0 或无明细时该块不可用）。
        portfolio_peak_mv: 组合历史峰值市值（None → 回撤现状「未评估」）。
        config: 全局配置字典（None 时读当前配置）。

    Returns:
        {available, reason, items[{item, max_pct, current_pct, breached,
        max_label, current_label, note}], breached_count}
    """
    if not holdings_details or isinstance(total_mv, bool) or not isinstance(total_mv, (int, float)) or total_mv <= 0:
        # 非数值入参（缺省/异常装配）一律按不可用处理，不抛错、不臆造 0 值
        return {"available": False, "reason": "缺少持仓市值", "items": [], "breached_count": 0}

    from src.python.analysis.rebalance import resolve_rebalance_config
    from src.python.analysis.trade_discipline import resolve_discipline_config

    cfg = config if config is not None else get_config()
    single_max_pct = _to_float(resolve_rebalance_config(cfg.get("rebalance")).get("threshold")) * 100
    discipline = resolve_discipline_config(cfg.get("discipline"))
    drawdown_max_pct = -abs(_to_float(discipline.get("drawdown_pct")))

    items: list[dict[str, Any]] = []
    single_pct, single_holder, _ = max_single_weight(holdings_details, total_mv)
    items.append(
        {
            "item": RISK_ITEM_SINGLE,
            "max_pct": round(single_max_pct, 2),
            "current_pct": None if single_pct is None else round(single_pct, 2),
            "breached": single_pct is not None and single_pct > single_max_pct,
            "max_label": _fmt_pct(round(single_max_pct, 2)),
            "current_label": RISK_UNEVALUATED if single_pct is None else _fmt_pct(round(single_pct, 2)),
            "note": f"最大：{single_holder}" if single_holder else "无有效市值行",
        }
    )
    items[-1]["status_label"], items[-1]["status_class"] = status_of(
        items[-1]["max_pct"], items[-1]["current_pct"], items[-1]["breached"]
    )
    items.append(
        {
            "item": RISK_ITEM_INDUSTRY,
            "max_pct": None,
            "current_pct": None,
            "breached": False,
            "max_label": RISK_UNCONFIGURED,
            "current_label": RISK_UNEVALUATED,
            "note": "无行业上限配置键",
        }
    )
    items[-1]["status_label"], items[-1]["status_class"] = status_of(None, None, False)
    if (
        isinstance(portfolio_peak_mv, (int, float))
        and not isinstance(portfolio_peak_mv, bool)
        and portfolio_peak_mv > 0
    ):
        # 正数=跌幅；市值创新高时回撤归零（不出现「负回撤」）
        drawdown_pct = max(0.0, (portfolio_peak_mv - total_mv) / portfolio_peak_mv * 100)
        current_drawdown = -drawdown_pct
        items.append(
            {
                "item": RISK_ITEM_DRAWDOWN,
                "max_pct": round(drawdown_max_pct, 2),
                "current_pct": round(current_drawdown, 2),
                "breached": current_drawdown <= drawdown_max_pct,
                "max_label": _fmt_pct(round(drawdown_max_pct, 2)),
                "current_label": _fmt_pct(round(current_drawdown, 2)),
                "note": "相对历史峰值",
            }
        )
    else:
        items.append(
            {
                "item": RISK_ITEM_DRAWDOWN,
                "max_pct": round(drawdown_max_pct, 2),
                "current_pct": None,
                "breached": False,
                "max_label": _fmt_pct(round(drawdown_max_pct, 2)),
                "current_label": RISK_UNEVALUATED,
                "note": "缺历史峰值",
            }
        )
    for item in items[2:]:
        item["status_label"], item["status_class"] = status_of(item["max_pct"], item["current_pct"], item["breached"])
    return {
        "available": True,
        "reason": "",
        "items": items,
        "breached_count": sum(1 for it in items if it["breached"]),
    }


# ── 纪律明细（上下文与是否应执行：只读复用纪律触发条，不改触发逻辑）──────
DISCIPLINE_REGIME_DOWN = "down"
DISCIPLINE_REGIME_NORMAL = "normal"
DISCIPLINE_REGIME_UNKNOWN = "unknown"
_REGIME_LABELS: dict[str, str] = {
    DISCIPLINE_REGIME_DOWN: "下跌段",
    DISCIPLINE_REGIME_NORMAL: "常态段",
    DISCIPLINE_REGIME_UNKNOWN: "未评估",
}


def _discipline_regime(total_mv: float | None, portfolio_peak_mv: float | None, drawdown_threshold_pct: float) -> str:
    """所处阶段（规则化判定）：距回撤线过半即「下跌段」，否则「常态段」。

    仅在峰值与市值可用时判定；两者缺失一律「未评估」，不做主观推断。
    """
    if (
        not isinstance(total_mv, (int, float))
        or isinstance(total_mv, bool)
        or total_mv <= 0
        or not isinstance(portfolio_peak_mv, (int, float))
        or isinstance(portfolio_peak_mv, bool)
        or portfolio_peak_mv <= 0
    ):
        return DISCIPLINE_REGIME_UNKNOWN
    drawdown_pct = max(0.0, (portfolio_peak_mv - total_mv) / portfolio_peak_mv * 100)
    threshold = max(abs(drawdown_threshold_pct), 1.0)  # 阈值缺失/0 时按 1% 兜底，避免恒判下跌段
    return DISCIPLINE_REGIME_DOWN if drawdown_pct >= threshold / 2 else DISCIPLINE_REGIME_NORMAL


def _discipline_note(rule: str, regime: str, *, stop_present: bool) -> tuple[str, str]:
    """单条纪律的上下文说明与执行口径（规则化模板，零 LLM）。

    Returns:
        (说明, 执行口径标签)
    """
    is_stop = "止损线" in rule
    is_take = "止盈线" in rule
    is_drawdown = "回撤线" in rule
    if regime == DISCIPLINE_REGIME_UNKNOWN:
        return "缺历史峰值，无法判断所处阶段：按阈值口径执行", "按阈值执行"
    if regime == DISCIPLINE_REGIME_DOWN:
        if is_stop or is_drawdown:
            prefix = "与止损同向触发：避免双重减仓；" if is_drawdown and stop_present else ""
            return f"{prefix}下跌段：单点阈值易被波动打穿，执行前确认趋势未反转", "宜确认后执行"
        if is_take:
            return "下跌段：已达止盈线，兑现前确认趋势", "按阈值执行"
    return "常态段：按阈值口径执行", "按阈值执行"


def build_discipline_detail(
    discipline_signals: list[dict[str, Any]] | None = None,
    total_mv: float | None = None,
    portfolio_peak_mv: float | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """装配纪律明细块（触发条 + 距阈值 + 阶段化执行口径说明）。

    数据来源是「交易纪律」块已算出的触发条（`action_data["discipline_signals"]`），
    本函数**不重算触发、不写静默状态**——保证纪律引擎是唯一触发真值，本块只补
    「为什么此刻该/不该执行」的上下文，动作仍归既有纪律块。

    Args:
        discipline_signals: 纪律触发条列表（None → 该块不可用；[] → 无触发的空态）。
        total_mv: 组合总市值（判阶段用）。
        portfolio_peak_mv: 组合历史峰值市值（None → 阶段未评估）。
        config: 全局配置字典（None 时读当前配置）。

    Returns:
        {available, reason, regime, regime_label, items[{rule, name, code, value_label,
        distance_label, distance_pct, stance_label, note}], note}
    """
    if discipline_signals is None:
        return {
            "available": False,
            "reason": "未接入纪律信号",
            "regime": DISCIPLINE_REGIME_UNKNOWN,
            "regime_label": _REGIME_LABELS[DISCIPLINE_REGIME_UNKNOWN],
            "items": [],
            "note": "",
        }
    from src.python.analysis.trade_discipline import resolve_discipline_config

    cfg = config if config is not None else get_config()
    drawdown_threshold_pct = abs(_to_float(resolve_discipline_config(cfg.get("discipline")).get("drawdown_pct")))
    regime = _discipline_regime(total_mv, portfolio_peak_mv, drawdown_threshold_pct)
    stop_present = any("止损线" in str(sig.get("rule") or "") for sig in discipline_signals)
    items: list[dict[str, Any]] = []
    for sig in discipline_signals:
        rule = str(sig.get("rule") or "")
        raw_distance = sig.get("distance_pct")
        distance_value: float | None = None
        if isinstance(raw_distance, (int, float)) and not isinstance(raw_distance, bool):
            try:
                distance_value = float(raw_distance)
            except (TypeError, ValueError):  # 防御性：异常载荷按无距阈值呈现
                distance_value = None
        note, stance = _discipline_note(rule, regime, stop_present=stop_present)
        items.append(
            {
                "rule": rule,
                "name": sig.get("name", ""),
                "code": sig.get("code", ""),
                "value_label": sig.get("value", ""),
                "distance_pct": round(distance_value, 2) if distance_value is not None else None,
                "distance_label": (
                    f"超线 {distance_value:.2f}%"
                    if distance_value is not None and distance_value > 0
                    else ("在线上" if distance_value is not None else "—")
                ),
                "stance_label": stance,
                "note": note,
            }
        )
    return {
        "available": True,
        "reason": "",
        "regime": regime,
        "regime_label": _REGIME_LABELS[regime],
        "items": items,
        "note": "本块只说明上下文与执行口径；触发与动作见「交易纪律」块" if items else "当前无纪律触发",
    }


# ── 结算摘要（最近 5 批 × 多视界；批次 = 结算交易日）────────────
# ── 信号可信度仲裁（规则引擎，非模型自评）────────────────────


def _confidence(level: str, reason: str, detail: str) -> dict[str, Any]:
    return {
        "level": level,
        "level_label": _LEVEL_LABELS[level],
        "level_class": _LEVEL_STATUS_CLASS[level],
        "reason": reason,
        "detail": detail,
    }


def _breakdown_detail(signals: list[dict[str, Any]], valid: int) -> str:
    """『有效信号 V/T（回测通过 X、回测未通过 Y、样本不足 Z、未回测 W）』——非零项才列。"""
    counts: dict[str, int] = {}
    for signal in signals:
        key = signal.get("discrimination", DISCRIMINATION_NOT_BACKTESTED)
        counts[key] = counts.get(key, 0) + 1
    parts = [
        f"{_DISCRIMINATION_LABELS[key]} {counts[key]}"
        for key in (
            DISCRIMINATION_PASSED,
            DISCRIMINATION_FAILED,
            DISCRIMINATION_INSUFFICIENT,
            DISCRIMINATION_NOT_BACKTESTED,
        )
        if counts.get(key)
    ]
    total = len(signals)
    return f"有效信号 {valid}/{total}" + (f"（{'、'.join(parts)}）" if parts else "")


def arbitrate_confidence(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """信号可信度仲裁（按序短路；首版不产出 high，防高置信幻觉）。

    规则（设计稿 §2.1）：清单空 → unknown(no_signal)；有效信号 0 →
    unknown(no_valid_signal)；全部口径代理 → low(all_proxy)；方向分裂 →
    low(split_direction)；有效信号 <3 → low(insufficient_signals)；
    ≥3 且方向一致 → medium(direction_aligned)。不做加权投票（权重无依据）。
    有效信号 = 进方向轴（回测通过且字段齐全）的信号。
    """
    if not signals:
        return _confidence("unknown", "no_signal", "暂无信号记录")
    axis = [s for s in signals if s.get("in_axis")]
    valid = len(axis)
    detail = _breakdown_detail(signals, valid)
    if valid == 0:
        return _confidence("unknown", "no_valid_signal", detail)
    if all(s.get("basis") == _BASIS_PRICE_PROXY for s in axis):
        return _confidence("low", "all_proxy", detail)
    if len({s.get("direction") for s in axis}) > 1:
        return _confidence("low", "split_direction", detail)
    if valid < 3:
        return _confidence("low", "insufficient_signals", detail)
    return _confidence("medium", "direction_aligned", detail)


# ── 装配入口 ────────────────────────────────────────────────


BLOCK_HEADLINE_EMPTY = "判断依据：暂无可用数据（信号 / 风险预算 / 纪律均未就绪）"


def build_headline(
    signals: list[dict[str, Any]],
    confidence: dict[str, Any],
    risk_budget: dict[str, Any],
    discipline_detail: dict[str, Any],
) -> list[str]:
    """章首三行摘要（双端逐字同源：HTML 渲染在折叠块上方，Excel 写在块首）。

    三行固定含义：① 有效信号数与可信度档 ② 风险预算超限项 ③ 纪律触发数。
    任一段无可用数据时用否定态文案占位（「未评估」「未接入」），不用空白行；
    三段全部不可用（新装/账本空）时压成一行空态，避免三行均为“未就绪”的噪声。

    Args:
        signals: 信号行清单（`in_axis` 为真的才是有效信号）。
        confidence: `arbitrate_confidence()` 返回值（取 `level_label`）。
        risk_budget: `build_risk_budget()` 返回值（`available` / `breached_count`）。
        discipline_detail: `build_discipline_detail()` 返回值（`available` / `items` / `regime_label`）。

    Returns:
        1~3 行摘要文本（确定性顺序，不随数据漂移）。
    """
    valid = sum(1 for s in signals if s.get("in_axis"))
    risk_available = bool(risk_budget.get("available"))
    discipline_items = discipline_detail.get("items") or []
    discipline_available = bool(discipline_detail.get("available"))
    if not signals and not risk_available and not discipline_available:
        return [BLOCK_HEADLINE_EMPTY]
    if signals:
        label = confidence.get("level_label") or "暂不可判"
        lines = [f"信号：有效 {valid}/{len(signals)} · 可信度 {label}"]
    else:
        lines = ["信号：暂无信号记录"]
    if not risk_available:
        lines.append("风险预算：未评估")
    elif risk_budget.get("breached_count"):
        lines.append(f"风险预算：超限 {risk_budget['breached_count']} 项")
    else:
        lines.append("风险预算：未超限")
    if not discipline_available:
        lines.append("纪律：未接入")
    elif discipline_items:
        lines.append(f"纪律：触发 {len(discipline_items)} 条（{discipline_detail.get('regime_label') or '未知'}）")
    else:
        lines.append("纪律：未触发")
    return lines


def build_decision_basis_data(
    holdings_details: list[dict[str, Any]] | None = None,
    total_mv: float | None = None,
    portfolio_peak_mv: float | None = None,
    discipline_signals: list[dict[str, Any]] | None = None,
    settlement_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """装配判断依据块数据（纯确定性：只读账本快照与已装配持仓，零取数零 LLM）。

    不重复读盘：持仓明细与总市值由编排层传入（`prepare_report_data` 已装配），
    回撤现状仅在历史峰值就绪后传入（full/both 路径峰值就绪后重装配一次）。

    Args:
        holdings_details: 持仓明细行（缺省 → 风险预算块不可用，信号部分照常）。
        total_mv: 组合总市值（缺省 0 → 风险预算块不可用）。
        portfolio_peak_mv: 组合历史峰值市值（缺省 → 回撤现状「未评估」）。
        discipline_signals: 纪律触发条（`action_data["discipline_signals"]` 只读透传；
            缺省 → 纪律明细块不可用）。
        settlement_decisions: `fold_ledger()` 的 decisions（缺省读当前账本）。

    Returns:
        数据子契约 dict（见模块 docstring）；开关关闭 → 仅 ``{"enabled": False}``。
    """
    if not is_decision_basis_enabled():
        return {"enabled": False}
    signals = _build_signal_rows()
    confidence = arbitrate_confidence(signals)
    risk_budget = build_risk_budget(holdings_details, total_mv, portfolio_peak_mv)
    discipline_detail = build_discipline_detail(discipline_signals, total_mv, portfolio_peak_mv)
    settlement_summary = build_settlement_summary(settlement_decisions)
    constraints = evaluate_constraints(holdings_details, total_mv)
    valid = sum(1 for s in signals if s.get("in_axis"))
    parts = [f"有效信号 {valid}/{len(signals)}" if signals else "暂无信号记录"]
    if risk_budget.get("breached_count"):
        parts.append(f"风险预算超限 {risk_budget['breached_count']} 项")
    if discipline_detail.get("items") and discipline_detail.get("regime_label"):
        parts.append(f"纪律触发 {len(discipline_detail['items'])} 条（{discipline_detail['regime_label']}）")
    if settlement_summary.get("batches"):
        parts.append(f"结算 {len(settlement_summary['batches'])} 批")
    if constraints.get("breached_count"):
        parts.append(f"约束标注 {constraints['breached_count']} 项")
    parts.append(f"信号可信度：{confidence['level_label']}")
    data: dict[str, Any] = {
        "enabled": True,
        "available": True,
        "reason": "",
        "title": BLOCK_TITLE,
        # 章首三行摘要（可见性保障：块默认折叠，读者不展开也能读到关键事实）
        "headline": build_headline(signals, confidence, risk_budget, discipline_detail),
        "summary": f"{BLOCK_TITLE}：" + " · ".join(parts),
        "backtest_as_of": backtest_run_date(),
        "confidence": confidence,
        "signals": signals,
        "risk_budget": risk_budget,
        "discipline": discipline_detail,
        "settlement": settlement_summary,
    }
    if constraints.get("enabled"):
        # 仅开关开启时出现该键：关闭时输出与未接线逐字节一致（回滚通道）
        data["constraints"] = constraints
    return data
