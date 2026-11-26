"""报告侧百分比格式化原语 — 口径单一来源。

决策依据 / 事件窗对照 / 调仓纪律回放三个报告模块各自带过一份同名 ``_fmt_pct``，
但入参口径并不统一（百分点 vs 小数比例），缺失值表现也不一致（一处直接抛
``ValueError``）。同名不同义使调用点无法自证口径，本模块按口径分两个函数，
**函数名即口径**：调用点无需旁注说明「这是点数还是比例」。

缺失/非数值入参（None、字符串、不可转数值的对象）统一返回 :data:`DASH` —
报告侧「无数据」的既有占位，不用 0 或空串冒充。
"""

from __future__ import annotations

from typing import Any

#: 「无数据」占位符（报告各区块统一口径）
DASH = "—"


def _to_float(value: Any) -> float | None:
    """入参 → float；非数值返回 None（不抛错：报告侧缺数据是常态而非异常）。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_pct_points(value: Any) -> str:
    """百分数点数 → 展示串（入参已是 ``12.5`` 这类点数，输出 ``12.5%``）。

    取 ``%g`` 口径（不补尾随零）：上限/阈值这类配置值本身精度有限，补零只会让
    同一个数字在不同位置出现两种写法。
    """
    number = _to_float(value)
    return DASH if number is None else f"{number:g}%"


def fmt_pct_fraction(value: Any, *, signed: bool = False) -> str:
    """小数比例 → 展示串（``0.125`` → ``12.50%``，``signed=True`` → ``+12.50%``）。

    Args:
        value: 小数比例（1 = 100%）；非数值返回 ``—``。
        signed: 是否强制带正负号 — 收益类需要「涨跌一眼可辨」，权重/换手类不需要。
    """
    number = _to_float(value)
    if number is None:
        return DASH
    return f"{number * 100:+.2f}%" if signed else f"{number * 100:.2f}%"
