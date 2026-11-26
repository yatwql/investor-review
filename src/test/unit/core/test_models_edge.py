"""边缘测试：Holding dataclass 极端值 / 空值 / 负值场景。

覆盖 `src/python/core/models.py` 的 Holding 在负份额、空账户名/名称/代码、港股特殊代码
等极端输入下的取值行为（dataclass 不做校验，原样保留输入）。

运行：
  pytest src/test/unit/core/test_models_edge.py -v
"""

from __future__ import annotations

import unittest

import pytest

from src.python.core.models import Holding

pytestmark = [pytest.mark.unit, pytest.mark.unit_core, pytest.mark.edge]


class TestHoldingEdgeCases(unittest.TestCase):
    """Holding 边缘情况测试。"""

    def test_negative_shares(self) -> None:
        """负份额（dataclass 不校验）。"""
        h = Holding(account="证券", name="股票", code="000001", shares=-100.0, cost_price=10.0)
        self.assertEqual(h.shares, -100.0)

    def test_empty_code(self) -> None:
        """代码为空字符串。"""
        h = Holding(account="证券", name="现金", code="", shares=100, cost_price=1.0)
        self.assertEqual(h.code, "")

    def test_empty_account(self) -> None:
        """账户名为空字符串。"""
        h = Holding(account="", name="股票", code="000001", shares=100, cost_price=10.0)
        self.assertEqual(h.account, "")

    def test_empty_name(self) -> None:
        """名称为空字符串。"""
        h = Holding(account="证券", name="", code="000001", shares=100, cost_price=10.0)
        self.assertEqual(h.name, "")

    def test_code_with_special_chars(self) -> None:
        """代码含特殊字符（港股带后缀）→ 校验层判为格式可疑。"""
        from src.python.core.holding_status import STATUS_BAD_CODE_FORMAT, classify_code_format

        h = Holding(account="港股", name="腾讯控股", code="00700.HK", shares=1000, cost_price=300.0)
        # dataclass 保留原始代码，格式判定由校验层输出（数据质量仪表盘据此标注）
        self.assertEqual(classify_code_format(h.code), STATUS_BAD_CODE_FORMAT)

    def test_shares_as_float(self) -> None:
        """份额为浮点数。"""
        h = Holding(account="证券", name="股票", code="000001", shares=100.5, cost_price=10.0)
        self.assertIsInstance(h.shares, float)

    def test_repr_contains_all_fields(self) -> None:
        """repr 包含所有字段。"""
        h = Holding(account="证券", name="长江电力", code="600900", shares=800, cost_price=17.65)
        r = repr(h)
        self.assertIn("Holding", r)
        self.assertIn("account=", r)
        self.assertIn("name=", r)
        self.assertIn("code=", r)
        self.assertIn("shares=", r)
        self.assertIn("cost_price=", r)
