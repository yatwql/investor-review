"""实验项转正 / 撤销的自动裁决汇编 —— 读数取值、判据逐条、结论与建议动作。

定位：**判据阈值不在此处新造**。`report_qa` 直接取 `qa/telemetry.py` 的转正判据与
其 `verdict.checks`；`decision_reflection` 取计划文档「决策跨期反思闭环转正判据」小节
的两级门槛（方向性样本量 + 超额符号），其中样本量门槛的落地常量是本模块的
``PROMOTE_DIRECTIONAL_SAMPLE``。
本模块只做汇编：**不改开关、不摘 ``experimental`` 标签**——转正/撤销仍是人工变更并进台账。

口径：
  - 项清单从注册表派生（``config.features.experimental_flags()``），不写字面量项数，
    新增实验项自动出现在裁决输出里；
  - 没有读数适配器的实验项输出「判据未接读数源」，不臆造成绩；
  - 结论四种：可转正 / 继续观察 / 撤销候选 / 无读数；撤销候选优先于观察
    （账本长期不增长时不该继续挂在「观察」里）。
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger("invest")

__all__ = [
    "PROMOTE_DIRECTIONAL_SAMPLE",
    "QA_REVOKE_IDLE_ATTEMPTS",
    "QA_REVOKE_IDLE_DAYS",
    "STATE_NO_READING",
    "STATE_OBSERVING",
    "STATE_PROMOTE_ELIGIBLE",
    "STATE_REVOKE_CANDIDATE",
    "action_notices",
    "collect_verdicts",
    "format_verdict_lines",
]

#: `decision_reflection` 转正的 5 日视界方向性样本下限（门槛来源：实验项转正判据小节）
PROMOTE_DIRECTIONAL_SAMPLE = 100

#: `report_qa` 撤销死线：近 N 天新增提问少于 M 条视为「用户不用」
QA_REVOKE_IDLE_DAYS = 90
QA_REVOKE_IDLE_ATTEMPTS = 10

STATE_PROMOTE_ELIGIBLE = "promote_eligible"
STATE_OBSERVING = "observing"
STATE_REVOKE_CANDIDATE = "revoke_candidate"
STATE_NO_READING = "no_reading"

_STATE_LABELS = {
    STATE_PROMOTE_ELIGIBLE: "可转正",
    STATE_OBSERVING: "继续观察",
    STATE_REVOKE_CANDIDATE: "撤销候选",
    STATE_NO_READING: "无读数",
}


def _read_decision_reflection() -> dict[str, Any]:
    """决策跨期反思闭环的读数：方向性样本量 + 超额均值符号。"""
    from src.python.core.decision_ledger import fold_ledger

    fold = fold_ledger()
    total = int(fold.get("directional_total") or 0)
    alpha = fold.get("alpha_mean")
    alpha_value = float(alpha) if isinstance(alpha, (int, float)) else None
    checks = [
        {
            "name": f"方向性样本 ≥ {PROMOTE_DIRECTIONAL_SAMPLE}",
            "passed": total >= PROMOTE_DIRECTIONAL_SAMPLE,
            "actual": total,
        },
        {
            "name": "超额均值 > 0",
            "passed": alpha_value is not None and alpha_value > 0,
            "actual": "—" if alpha_value is None else f"{alpha_value * 100:.2f}%",
        },
    ]
    return {"checks": checks, "revoke": False, "note": ""}


def _read_report_qa() -> dict[str, Any]:
    """报告追问的读数：转正判据逐条（阈值与结论来自 `qa/telemetry.py`）+ 撤销死线。"""
    from src.python.qa.telemetry import summarize_qa_usage

    summary = summarize_qa_usage(days=30)
    verdict = summary.get("verdict") or {}
    checks = [
        {"name": check.get("name", ""), "passed": bool(check.get("passed")), "actual": check.get("actual")}
        for check in (verdict.get("checks") or [])
    ]
    idle_attempts = int(summarize_qa_usage(days=QA_REVOKE_IDLE_DAYS).get("attempts") or 0)
    revoke = idle_attempts < QA_REVOKE_IDLE_ATTEMPTS
    note = f"近 {QA_REVOKE_IDLE_DAYS} 天新增提问 {idle_attempts} 条" if revoke else ""
    return {"checks": checks, "revoke": revoke, "note": note}


#: 开关名 → 读数适配器（未登记的实验项输出「判据未接读数源」）
_READERS: dict[str, Callable[[], dict[str, Any]]] = {
    "decision_reflection": _read_decision_reflection,
    "report_qa": _read_report_qa,
}


def _evaluate(flag: str, label: str) -> dict[str, Any]:
    reader = _READERS.get(flag)
    base: dict[str, Any] = {"flag": flag, "label": label}
    if reader is None:
        return {
            **base,
            "state": STATE_NO_READING,
            "reason": "判据未接读数源（补读数适配器后自动纳入裁决）",
            "checks": [],
        }
    try:
        reading = reader()
    except Exception as exc:  # noqa: BLE001 — 读数函数来自外部探针（可抛任意异常），异常即「无读数」状态并如实记录原因
        return {**base, "state": STATE_NO_READING, "reason": f"读数失败：{type(exc).__name__}: {exc}", "checks": []}

    checks = list(reading.get("checks") or [])
    if reading.get("revoke"):
        state = STATE_REVOKE_CANDIDATE
    elif checks and all(bool(check.get("passed")) for check in checks):
        state = STATE_PROMOTE_ELIGIBLE
    else:
        state = STATE_OBSERVING
    return {**base, "state": state, "reason": reading.get("note", ""), "checks": checks}


def collect_verdicts() -> list[dict[str, Any]]:
    """逐项裁决当前注册表里的实验项（顺序 = 注册表顺序）。

    Returns:
        列表，每项含 ``flag`` / ``label`` / ``state`` / ``reason`` / ``checks``
        （``checks`` 为 ``[{name, passed, actual}]``，无读数时为空）。
    """
    from src.python.config.features import experimental_flags

    return [_evaluate(flag, declaration.label) for flag, declaration in experimental_flags()]


def _check_text(checks: list[dict[str, Any]]) -> str:
    parts = [
        f"{check.get('name')}（实测 {check.get('actual')}，{'达标' if check.get('passed') else '未达标'}）"
        for check in checks
    ]
    return "；".join(parts)


def format_verdict_lines(verdicts: list[dict[str, Any]]) -> list[str]:
    """把裁决结果渲染成自检可读行（每项一行 + 判据明细）。"""
    lines: list[str] = []
    for verdict in verdicts:
        state_key = str(verdict.get("state") or "")
        state = _STATE_LABELS.get(state_key, state_key)
        head = f"{verdict.get('label')}（{verdict.get('flag')}）→ {state}"
        detail = _check_text(verdict.get("checks") or [])
        if detail:
            head = f"{head} — {detail}"
        reason = str(verdict.get("reason") or "")
        if reason:
            head = f"{head}；{reason}"
        lines.append(head)
    return lines


def action_notices(verdicts: list[dict[str, Any]] | None = None) -> list[str]:
    """需要人工决策的提醒行（可转正 / 撤销候选），供自检摘要与日志使用。

    空列表表示所有实验项都还在观察期或无读数——此时不该催促任何动作。
    """
    actionable = [
        verdict
        for verdict in (verdicts if verdicts is not None else collect_verdicts())
        if verdict.get("state") in (STATE_PROMOTE_ELIGIBLE, STATE_REVOKE_CANDIDATE)
    ]
    notices: list[str] = []
    for verdict in actionable:
        state_key = str(verdict.get("state") or "")
        label = _STATE_LABELS.get(state_key, state_key)
        notices.append(f"实验项「{verdict.get('label')}」已达{label}判据，请按计划文档裁决（不自动改开关）")
    return notices
