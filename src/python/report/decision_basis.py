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
    回测日期、讨论稿指针），不新增配置键、不写运行时账本、不散落硬编码；
  - 零 LLM 依赖：装配与仲裁函数不接任何 LLM 参数，`enable_llm` 两态输出一致。
"""

from __future__ import annotations

from typing import Any

from src.python.analysis.portfolio_constraints import evaluate_constraints, max_single_weight, status_of
from src.python.config import get_config
from src.python.config.features import is_feature_enabled
from src.python.core import signal_ledger as sl
from src.python.core.decision_ledger import DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT, fold_ledger

#: 功能开关名（登记见 config/_feature_registry.py，TUI [C] 面板可切换）
FEATURE_FLAG = "decision_basis"
#: 区块显示名（双端同源；归一化名与 section_block_registry 清单一致）
BLOCK_TITLE = "判断依据"

# ── 区分度三态（设计稿 §2.1 discrimination 契约）──────────────
DISCRIMINATION_NOT_BACKTESTED = "not_backtested"
DISCRIMINATION_INSUFFICIENT = "insufficient_sample"
DISCRIMINATION_PASSED = "passed"
DISCRIMINATION_FAILED = "failed"

_DISCRIMINATION_LABELS: dict[str, str] = {
    DISCRIMINATION_NOT_BACKTESTED: "未回测",
    DISCRIMINATION_INSUFFICIENT: "样本不足",
    DISCRIMINATION_PASSED: "回测通过",
    DISCRIMINATION_FAILED: "回测未通过",
}

# ── 首批回测结论登记（唯一事实源；复跑回测出新结论后更新本表 + changelog）──
# 来源：scripts/eval-decision-quality.py（阶段 horizon/factor-ic/valuation，
# 判据预注册：视界 5/20/60 交易日、样本门槛 100、|IC| 拒绝线 0.05、三分位单调）；
# 结论证据见归档讨论稿 `docs/archive/v0.16.x/investment-decision-quality/investment-decision-quality.md` §8.1。
BACKTEST_SOURCE = "scripts/eval-decision-quality.py"
BACKTEST_DATE = "2026-11-02"
BACKTEST_REF = "docs/archive/v0.16.x/investment-decision-quality/investment-decision-quality.md §8.1"

BACKTEST_CONCLUSIONS: dict[str, dict[str, Any]] = {
    # 估值分位：5 日视界两口径（n=117）均无区分度 → 已回测未通过，不进方向轴；
    # 代理 IC=+0.0399 / 真实 IC=−0.0267 同判无区分度 → 不在管线内计算真实
    # PE/PB 口径，口径透明由 basis=price_proxy 表达（账本 detail.pe/pb 为 null）。
    sl.SIGNAL_VALUATION: {
        "discrimination": DISCRIMINATION_FAILED,
        "n_backtest": 117,
        "ic": 0.0399,
        "monotonic": False,
        "note": "价格分位代理；5 日视界回测未通过（叙述性维度），不进方向轴",
    },
    # 因子目录：因子单因子 IC 回测已跑、单因子 × 视界最大可结算样本 19 < 100 门槛 → 样本不足。
    sl.SIGNAL_FACTOR_CATALOG: {
        "discrimination": DISCRIMINATION_INSUFFICIENT,
        "n_backtest": 19,
        "ic": None,
        "monotonic": None,
        "note": "样本不足 n=19（<100 不裁决）",
    },
}
_DEFAULT_CONCLUSION: dict[str, Any] = {
    "discrimination": DISCRIMINATION_NOT_BACKTESTED,
    "n_backtest": None,
    "ic": None,
    "monotonic": None,
    "note": "未回测",
}

# ── 清单覆盖的判断类信号（按稳定顺序呈现）────────────────────
# 排除再平衡超限：它是动作信号，已由「① 再平衡信号」块呈现，本块只装判断依据，
# 与既有块分工见设计稿 §3「与既有块分工」行。
SIGNAL_TYPES: tuple[str, ...] = (
    sl.SIGNAL_MARKET_TEMPERATURE,
    sl.SIGNAL_VALUATION,
    sl.SIGNAL_TAIL_RISK,
    sl.SIGNAL_STYLE_FACTOR,
    sl.SIGNAL_FACTOR_CATALOG,
)

# ── 展示映射（装配层算好，渲染层零计算——渲染数据走模板 context）────────
_DIRECTION_ENUM: dict[int, str] = {DIRECTION_LONG: "bullish", DIRECTION_SHORT: "bearish", DIRECTION_FLAT: "neutral"}
_DIRECTION_LABELS: dict[int, str] = {DIRECTION_LONG: "看多", DIRECTION_SHORT: "看空", DIRECTION_FLAT: "中性"}

_BASIS_PRICE_PROXY = "price_proxy"
_BASIS_VALUATION_REAL = "valuation_real"
_BASIS_LABELS: dict[str, str] = {
    _BASIS_VALUATION_REAL: "真实估值",
    _BASIS_PRICE_PROXY: "价格代理",
    "rule_based": "规则推导",
    "stat_model": "统计模型",
    "unknown": "未知",
}

#: 各信号类型的口径（估值分位按 detail.pe/pb 特判，见 _basis_of）
_BASIS_BY_TYPE: dict[str, str] = {
    sl.SIGNAL_MARKET_TEMPERATURE: _BASIS_PRICE_PROXY,
    sl.SIGNAL_TAIL_RISK: "stat_model",
    sl.SIGNAL_STYLE_FACTOR: "stat_model",
    sl.SIGNAL_FACTOR_CATALOG: "stat_model",
}

#: 各信号类型的观测样本字段（账本 detail 键；缺失 → None 显式给出）
_N_OBS_KEY: dict[str, str] = {
    sl.SIGNAL_MARKET_TEMPERATURE: "sample_count",
    sl.SIGNAL_VALUATION: "sample_count",
    sl.SIGNAL_TAIL_RISK: "sample_size",
    sl.SIGNAL_STYLE_FACTOR: "sample_count",
    sl.SIGNAL_FACTOR_CATALOG: "computed",
}

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


# ── 信号清单装配（只读账本快照，零取数零 LLM）────────────────


def _basis_of(signal_type: str, detail: dict[str, Any]) -> str:
    """口径判定：估值分位按账本事实（detail.pe/pb 均为 null ⇒ 价格分位代理）。"""
    if signal_type == sl.SIGNAL_VALUATION:
        if detail.get("pe") is None and detail.get("pb") is None:
            return _BASIS_PRICE_PROXY
        return _BASIS_VALUATION_REAL
    return _BASIS_BY_TYPE.get(signal_type, "unknown")


def in_direction_axis(
    basis: str | None,
    n_obs: Any,
    ic: Any,
    monotonic: Any,
    discrimination: str | None,
) -> bool:
    """信号是否进方向轴：区分度回测通过 **且** 三组必填字段齐全且口径非 unknown。

    设计稿 §2.1：`basis`/`n_obs`/`ic`/`monotonic` 缺任一即不进方向轴；
    `unknown` 口径不得进方向轴。负向用例见 test_decision_basis。
    """
    return (
        discrimination == DISCRIMINATION_PASSED
        and basis not in (None, "", "unknown")
        and n_obs is not None
        and ic is not None
        and monotonic is not None
    )


def _latest_signals() -> dict[str, dict[str, Any]]:
    """读账本快照，取各判断类信号的最新一条（写入顺序末条即最新，同 fold 口径）。"""
    latest: dict[str, dict[str, Any]] = {}
    for record in sl.load_signals():
        if not isinstance(record, dict):
            continue
        signal_type = record.get("signal_type")
        if signal_type in SIGNAL_TYPES:
            latest[signal_type] = record  # 追加顺序覆盖 → 末条即最新
    return latest


def _build_signal_rows() -> list[dict[str, Any]]:
    """信号清单行（字段齐即显式给出，可空值为 None；note 如实标注区分度三态）。"""
    rows: list[dict[str, Any]] = []
    latest = _latest_signals()
    for signal_type in SIGNAL_TYPES:
        record = latest.get(signal_type)
        if record is None:
            continue
        raw_detail = record.get("detail")
        detail: dict[str, Any] = raw_detail if isinstance(raw_detail, dict) else {}
        conclusion = BACKTEST_CONCLUSIONS.get(signal_type, _DEFAULT_CONCLUSION)
        basis = _basis_of(signal_type, detail)
        n_obs = detail.get(_N_OBS_KEY.get(signal_type, ""))
        ic = conclusion.get("ic")
        monotonic = conclusion.get("monotonic")
        discrimination = conclusion.get("discrimination", DISCRIMINATION_NOT_BACKTESTED)
        eligible = in_direction_axis(basis, n_obs, ic, monotonic, discrimination)
        direction = record.get("direction", DIRECTION_FLAT)
        if not isinstance(direction, int):
            direction = DIRECTION_FLAT
        rows.append(
            {
                "name": sl.SIGNAL_TYPE_LABELS.get(signal_type, signal_type),
                "direction": _DIRECTION_ENUM.get(direction, "neutral"),
                "direction_label": _DIRECTION_LABELS.get(direction, "中性"),
                "basis": basis,
                "basis_label": _BASIS_LABELS.get(basis, "未知"),
                "basis_sample_label": (
                    f"{_BASIS_LABELS.get(basis, '未知')}·n={n_obs}"
                    if n_obs is not None
                    else _BASIS_LABELS.get(basis, "未知")
                ),
                "n_obs": n_obs,
                "n_backtest": conclusion.get("n_backtest"),
                "ic": ic,
                "monotonic": monotonic,
                "discrimination": discrimination,
                # 无效信号标「仅参考」（中性态，不染状态色——设计契约）
                "discrimination_label": _DISCRIMINATION_LABELS.get(discrimination, "未回测")
                + ("" if eligible else "（仅参考）"),
                "note": conclusion.get("note", "未回测"),
                "in_axis": eligible,
            }
        )
    return rows


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
SETTLEMENT_HORIZONS: tuple[int, ...] = (5, 20, 60)
SETTLEMENT_MAX_BATCHES = 5


def _tone_of(value: float | None) -> str:
    """涨跌域色变量（红涨绿跌，A 股口径；与状态域互斥，不混用）。"""
    if value is None or value == 0:
        return ""
    return "--profit" if value > 0 else "--loss"


def _tone_class_of(value: float | None) -> str:
    """涨跌域语义类（红涨绿跌；零/缺失不加类，与状态域互斥）。"""
    if value is None or value == 0:
        return ""
    return "tone-profit" if value > 0 else "tone-loss"


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_settlement_summary(
    decisions: list[dict[str, Any]] | None = None,
    *,
    max_batches: int = SETTLEMENT_MAX_BATCHES,
) -> dict[str, Any]:
    """装配结算摘要块（最近 N 批 × 5/20/60 视界，均值收益与均值超额）。

    批次口径 = 结算交易日（与「历史决策复盘」块同一数据源 `fold_ledger`，不另算
    一套）；超额 = 该条原始收益 − 同期基准收益，基准缺失的条目只计入收益均值。

    Args:
        decisions: `fold_ledger()` 的 decisions（含 `settlements` 多视界映射）；
            None 时读当前账本。
        max_batches: 批次上限（默认 5）。

    Returns:
        {available, reason, horizons, batches[{date, n, cells[{horizon, n,
        state, mean_return_pct, mean_excess_pct, value_label, excess_label,
        color_var}]}], note}
    """
    ledger_decisions: list[dict[str, Any]] = (
        decisions if decisions is not None else list(fold_ledger().get("decisions") or [])
    )
    # settle_date → horizon → [(raw_return, excess|None)]
    buckets: dict[str, dict[int, list[tuple[float, float | None]]]] = {}
    for decision in ledger_decisions:
        settlements = decision.get("settlements") or {}
        if not isinstance(settlements, dict):
            continue
        for raw_horizon, event in settlements.items():
            if not isinstance(event, dict):
                continue
            try:
                horizon = int(raw_horizon)
            except (TypeError, ValueError):
                continue
            settle_date = str(event.get("settle_date") or "")
            raw_return = event.get("raw_return")
            if not settle_date or not isinstance(raw_return, (int, float)) or isinstance(raw_return, bool):
                continue
            try:
                raw_value = float(raw_return)
            except (TypeError, ValueError):
                continue
            bench_return = event.get("bench_return")
            excess: float | None = None
            if isinstance(bench_return, (int, float)) and not isinstance(bench_return, bool):
                try:
                    excess = raw_value - float(bench_return)
                except (TypeError, ValueError):
                    excess = None
            buckets.setdefault(settle_date, {}).setdefault(horizon, []).append((raw_value, excess))

    dates = sorted(buckets, reverse=True)[: max(int(max_batches), 1)]
    batches: list[dict[str, Any]] = []
    for date in dates:
        cells: list[dict[str, Any]] = []
        batch_n = 0
        for horizon in SETTLEMENT_HORIZONS:
            samples: list[tuple[float, float | None]] = buckets[date].get(horizon) or []
            batch_n = max(batch_n, len(samples))
            if not samples:
                cells.append(
                    {
                        "horizon": horizon,
                        "n": 0,
                        "state": "pending",
                        "mean_return_pct": None,
                        "mean_excess_pct": None,
                        "value_label": "未到期",
                        "excess_label": "—",
                        "color_var": "",
                        "tone_class": "",
                    }
                )
                continue
            mean_return = _mean([raw for raw, _ in samples])
            excess_values = [exc for _, exc in samples if exc is not None]
            mean_excess = _mean(excess_values)
            return_pct = None if mean_return is None else mean_return * 100
            excess_pct = None if mean_excess is None else mean_excess * 100
            cells.append(
                {
                    "horizon": horizon,
                    "n": len(samples),
                    "state": "settled",
                    "mean_return_pct": None if return_pct is None else round(return_pct, 2),
                    "mean_excess_pct": None if excess_pct is None else round(excess_pct, 2),
                    # 展示口径：收益（超额）——超额缺失只显示收益
                    "value_label": "—" if return_pct is None else f"{return_pct:+.2f}%",
                    "excess_label": "—" if excess_pct is None else f"{excess_pct:+.2f}%",
                    "color_var": _tone_of(return_pct),
                    "tone_class": _tone_class_of(return_pct),
                }
            )
        batches.append({"date": date, "n": batch_n, "cells": cells})
    return {
        "available": True,
        "reason": "",
        "horizons": list(SETTLEMENT_HORIZONS),
        "batches": batches,
        "note": ("批次按结算交易日聚合（上限 5 批），更多明细见「历史决策复盘」块" if batches else "暂无结算样本"),
    }


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
        "summary": f"{BLOCK_TITLE}：" + " · ".join(parts),
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
