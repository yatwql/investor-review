"""持仓明细行的双形态取值（`core/detail_view.detail_value`）——形态分派单源。

背景：明细在管线里以两种表示流动（`DetailRow` 对象 / 明细字典），二者各自被不同层
独占消费，短期无法收敛为单形态。本模块是**唯一**的形态分派点：新增读取点走它，
而不是每处再写一遍 `isinstance(dict)` 分支（那会让漏改面随读取点线性增长）。
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.python.core.detail_view import detail_value

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@dataclass
class _Row:
    """最小对象形态（对齐 DetailRow 的取值面：同名字段 + 属性访问）。"""

    code: str
    price: float | None = None
    nav_date: str | None = None


def test_dict_and_object_return_same_value():
    """同一字段在两种形态上取到同一值（这是双形态共存的前提契约）。"""
    assert detail_value({"code": "600900", "price": 12.5}, "code") == "600900"
    assert detail_value(_Row(code="600900", price=12.5), "code") == "600900"
    assert detail_value({"price": 12.5}, "price") == 12.5
    assert detail_value(_Row(code="x", price=12.5), "price") == 12.5


class _Bare:
    """无 ``nav_date`` 属性的对象（模拟「该行确实没有这个字段」）。"""

    code = "x"


def test_missing_field_returns_same_default_for_both_shapes():
    """**缺字段**时两种形态回退到同一默认值（各自写死不同缺省会让上游切换形态时静默变形）。"""
    assert detail_value({}, "nav_date", "—") == "—"
    assert detail_value(_Bare(), "nav_date", "—") == "—"


def test_present_but_none_field_is_not_replaced_by_default():
    """字段存在且值为 None → 返回 None（不被默认值顶替）；两种形态口径一致。

    注意对象形态的固有差异：dataclass 声明了字段就一定有属性（值可能为 None），
    因此「值 None」与「缺属性」是两件事——消费方需要兜底时自己 `or ""`，
    取值层不做真值判断（否则 0 / 空串会被误当缺失）。
    """
    assert detail_value({"nav_date": None}, "nav_date", "—") is None
    assert detail_value(_Row(code="x", nav_date=None), "nav_date", "—") is None


def test_none_row_returns_default():
    """行本身为 None（可选明细）→ 默认值，不抛异常。"""
    assert detail_value(None, "code", "") == ""
    assert detail_value(None, "price") is None


def test_falsey_values_are_not_treated_as_missing():
    """0 / 空串属有效值：调用方自行决定是否当缺省，取值层不做真值判断。"""
    assert detail_value({"price": 0.0}, "price", 99.0) == 0.0
    assert detail_value(_Row(code="", price=0.0), "code", "fallback") == ""
