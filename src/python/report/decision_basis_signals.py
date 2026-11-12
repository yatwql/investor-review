"""判断依据章内块 — 信号清单装配与回测结论登记（由 `decision_basis.py` 聚合门面 re-export）。

只读信号账本快照：区分度三态如实标注（未回测 / 样本不足 / 回测通过·未通过），
首批回测结论以本模块常量登记（`BACKTEST_CONCLUSIONS`，含来源脚本与讨论稿指针），
采样日由 `backtest_run_date()` 从产物日期派生、产物缺失才回落兜底常量。
零 LLM 依赖、零外部取数。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.python.core import signal_ledger as sl
from src.python.core.decision_ledger import DIRECTION_FLAT, DIRECTION_LONG, DIRECTION_SHORT

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
#: 产物缺失时的兜底采样日（归档讨论稿 §8.1 结论的采样日，不随开发演进）
BACKTEST_DATE_FALLBACK = "2026-11-02"
BACKTEST_REF = "docs/archive/v0.16.x/investment-decision-quality/investment-decision-quality.md §8.1"

#: 装配阶段名（perf 计时口径，full/both 双路径共用同一字面量）
PERF_PHASE_ASSEMBLY = "判断依据块装配"


def backtest_run_date(products_dir: str | Path | None = None) -> str:
    """回测产物的最新运行日（``YYYY-MM-DD``）。

    回测结论会随样本累积变化（累计成熟样本过后重跑），采样日因此不能写成常量——
    日期口径由 `core/eval_status.last_eval_date()` 单一实现（读产物目录内最新一份
    JSON 的修改日期），产物缺失（新克隆/产物被清理）时回落到归档结论采样日
    ``BACKTEST_DATE_FALLBACK``，全部只读。

    Args:
        products_dir: 产物目录（测试注入 ``tmp_path`` 用；缺省取 `docs/tmp/decision-quality`）。

    Returns:
        日期字符串；产物缺失或不可读时返回兜底值。
    """
    from src.python.core.eval_status import last_eval_date

    try:
        latest = last_eval_date(products_dir)
    except OSError:
        latest = None
    return latest.strftime("%Y-%m-%d") if latest is not None else BACKTEST_DATE_FALLBACK


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
