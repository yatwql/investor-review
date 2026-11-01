"""检查 9：账本日期实参写死绝对日期（时间炸弹）。

背景：信号账本 / 决策账本按保留期（730 天）在**写侧即裁剪**——
`signal_ledger.append_signals` / `decision_ledger.append_decision` 追加后立刻调
`prune_jsonl_by_age(retention_days=..., date_key="report_date")`。测试若把
`report_date="2026-09-01"` 这类绝对日期实参写进账本调用，用例会在「日期 + 保留期」
之后静默退化成「账本为空 / 键缺失」，失败信息完全看不出是日期过期
（同类形态已在多个测试文件上暴雷）。

正确写法：从当天回推派生（`_d(offset)` / `date.today() - timedelta(days=N)`）。

判定口径刻意收窄以避免伪信号：
- 只看**账本类调用的日期实参**（`LEDGER_DATE_CALLS` × `DATE_KWARGS`），不波及普通 fixture 数据；
- 实参可以是字面量，也可以是模块级 `NAME = "<日期>"` 常量转手；
- 只有落在「当前年 ±2 年」窗口内的近期/未来日期才算炸弹——`"2020-01-02"` 这种
  远过去锚点（语义是「必过期」）不会随墙钟腐化，不报。
"""

from __future__ import annotations
from _test_redundancy._common import (
    _call_name,
)

import ast
import datetime as _dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录共享模块（_checklib）
from _shared.checklib import rel  # noqa: E402


#: 账本写入/裁剪类调用：这些调用的日期实参进账本，会被保留期裁剪按 now() 判定。
LEDGER_DATE_CALLS = frozenset(
    {
        "append_decision",
        "append_settlement",
        "append_signal",
        "append_signals",
        "register_deterministic_signals",
        # 账本写入包装层（内部转调 append_decision / append_signals 并触发写侧裁剪）
        "register_action_decisions",
        "register_llm_decisions",
        "build_signal",
        "build_decision",
        "prune_jsonl_by_age",
    }
)

#: 承载账本日期的关键字参数名（幂等键 / 保留期判定都用它）。
DATE_KWARGS = ("report_date", "settle_date", "date")

#: 只有「当前年 ±NEAR_YEARS」内的日期算时间炸弹；更早的是稳定的「必过期」锚点。
NEAR_YEARS = 2

_ABS_DATE = re.compile(r"^(20\d{2})-(\d{2})-(\d{2})")


def _is_near_year(year: int, today: _dt.date | None = None) -> bool:
    """该年份是否落在「当前年 ±NEAR_YEARS」（会随墙钟推进腐化的区间）。"""
    ref = today or _dt.date.today()
    return ref.year - NEAR_YEARS <= year <= ref.year + NEAR_YEARS


def _module_date_constants(tree: ast.Module) -> dict[str, str]:
    """模块级 `NAME = "<日期>"` → {NAME: 字面量}（识别经常量转手的日期实参）。"""
    found: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            found[node.targets[0].id] = node.value.value
    return found


def _literal_date(expr: ast.expr, consts: dict[str, str]) -> str | None:
    """日期实参 → 字面量（支持模块级常量名）；非日期字面量返回 None。"""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name) and expr.id in consts:
        return consts[expr.id]
    return None


def check_ledger_absolute_dates(tree: ast.Module, path: Path) -> list[str]:
    """I：账本日期实参写死绝对日期——保留期过后用例静默失效。"""
    consts = _module_date_constants(tree)
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _call_name(node)
        if call_name not in LEDGER_DATE_CALLS:
            continue
        for kw in node.keywords:
            if kw.arg not in DATE_KWARGS:
                continue
            literal = _literal_date(kw.value, consts)
            if literal is None:
                continue
            match = _ABS_DATE.match(literal.strip())
            if not match or not _is_near_year(int(match.group(1))):
                continue
            findings.append(
                f'{rel(path)}:{kw.value.lineno}: 账本日期实参写死绝对日期（{call_name}({kw.arg}="{literal}")）'
                "——账本按保留期在写侧裁剪（prune_jsonl_by_age 按 now() 判定），"
                "该用例会在「日期 + 保留期」之后静默变成空账本；改用从当天回推派生（如 `_d(-2)`）"
            )
    return findings
