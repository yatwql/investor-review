"""持仓明细行的**双形态取值**唯一入口（dict 与含属性对象，如 `DetailRow`）。

为什么需要它：同一条持仓明细在管线里以两种表示流动——`DetailRow` 对象（明细计算
与渲染持有）与明细字典（`build_holding_detail_rows` 的输出，供数据契约与跨层传递）。
两种表示各自被不同层独占消费，短期内无法收敛为单一形态，于是「按需取一个字段」这件事
至少要有**一个**统一实现：否则每加一个读取点就多一处 `isinstance(dict)` 分支，
漏改面随读取点线性增长。

约定：本模块是**唯一**的形态分派点。新增读取明细字段的代码一律走 `detail_value`；
需要写「同时接受两种形态」的函数时，也不得再自写 isinstance 分支。
"""

from __future__ import annotations

from typing import Any

__all__ = ["detail_value"]


def detail_value(row: Any, field: str, default: Any = None) -> Any:
    """从持仓明细行取一个字段值（dict 与含属性对象同语义）。

    Args:
        row: 明细行（dict 或含同名属性的对象）；None → 直接返回默认值。
        field: 字段名（如 ``code`` / ``price`` / ``nav_date``）。
        default: 取不到时的回退值（两种形态共用同一回退，避免各自写死不同缺省）。

    Returns:
        字段值；行内缺该字段（或行为 None）时返回 `default`。
    """
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(field, default)
    return getattr(row, field, default)
