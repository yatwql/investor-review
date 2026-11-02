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
  risk_budget / discipline / settlement
              后续轮次逐节填充（字段先立、数据后到；任一节缺失 → 该节空态，
              不隐藏整块容器）

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

from src.python.config.features import is_feature_enabled
from src.python.core import signal_ledger as sl
from src.python.core.decision_ledger import DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT

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
# 结论证据见 docs/plan/investment-decision-quality.md §8.1。
BACKTEST_SOURCE = "scripts/eval-decision-quality.py"
BACKTEST_DATE = "2026-11-02"
BACKTEST_REF = "docs/plan/investment-decision-quality.md §8.1"

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


def build_decision_basis_data() -> dict[str, Any]:
    """装配判断依据块数据（纯确定性：只读账本快照，零取数零 LLM、零参数）。

    Returns:
        数据子契约 dict（见模块 docstring）；开关关闭 → 仅 ``{"enabled": False}``。
    """
    if not is_decision_basis_enabled():
        return {"enabled": False}
    signals = _build_signal_rows()
    confidence = arbitrate_confidence(signals)
    valid = sum(1 for s in signals if s.get("in_axis"))
    if signals:
        summary = f"{BLOCK_TITLE}：有效信号 {valid}/{len(signals)} · 信号可信度：{confidence['level_label']}"
    else:
        summary = f"{BLOCK_TITLE}：暂无信号记录 · 信号可信度：暂不可判"
    return {
        "enabled": True,
        "available": True,
        "reason": "",
        "title": BLOCK_TITLE,
        "summary": summary,
        "confidence": confidence,
        "signals": signals,
        "risk_budget": {},
        "discipline": {},
        "settlement": {},
    }
