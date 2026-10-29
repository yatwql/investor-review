# -*- coding: utf-8 -*-
"""持仓录入编辑层边缘场景（超卖 / 未知标的 / 页签冲突）。

正面路径见 ``test_holdings_editor.py``；本文件只放拒绝类断言——写入路径必须
在**改文件之前**中止，且错误信息能让用户自己纠正。
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from src.python.core.holdings_editor import SIDE_BUY, SIDE_SELL, TradeIntent, load_book
from src.test._holdings_fixture import make_holdings_file

pytestmark = [pytest.mark.unit, pytest.mark.unit_core, pytest.mark.edge]


def _intent(**overrides) -> TradeIntent:
    base = {
        "account": "股票账户",
        "name": "长江电力",
        "code": "600900",
        "side": SIDE_SELL,
        "shares": 100,
        "price": 25.0,
        "trade_date": "2026-07-01",
    }
    base.update(overrides)
    return TradeIntent(**base)


def _edge_file(tmp_path: Path) -> Path:
    """单账户 + 自定义非持仓页签、无流水页签（边缘用例基线）。"""
    return make_holdings_file(
        tmp_path,
        stock_rows=[["长江电力", "600900", 1000, 20.0]],
        with_fund_sheet=False,
        with_flow_sheet=False,
        extra_sheets={"备注": [["说明"], ["自定义页签，不是持仓主表"]]},
    )


def test_sell_more_than_held_raises(tmp_path: Path):
    book = load_book(str(_edge_file(tmp_path)))
    with pytest.raises(ValueError, match="超过当前持有"):
        book.apply(_intent(shares=1001))
    assert book.drafts == []
    assert book.rows("股票账户")[0].shares == pytest.approx(1000)


def test_sell_unknown_asset_raises(tmp_path: Path):
    book = load_book(str(_edge_file(tmp_path)))
    with pytest.raises(ValueError, match="没有"):
        book.apply(_intent(code="000001", name="平安银行"))


def test_non_positive_shares_or_price_rejected(tmp_path: Path):
    book = load_book(str(_edge_file(tmp_path)))
    with pytest.raises(ValueError, match="份额必须大于 0"):
        book.apply(_intent(side=SIDE_BUY, shares=0))
    with pytest.raises(ValueError, match="价格必须大于 0"):
        book.apply(_intent(side=SIDE_BUY, price=0))


def test_unknown_side_rejected(tmp_path: Path):
    book = load_book(str(_edge_file(tmp_path)))
    with pytest.raises(ValueError, match="操作方向"):
        book.apply(_intent(side="transfer"))


def test_empty_account_rejected(tmp_path: Path):
    book = load_book(str(_edge_file(tmp_path)))
    with pytest.raises(ValueError, match="账户名不能为空"):
        book.apply(_intent(account="  "))


def test_new_account_colliding_with_other_sheet_raises(tmp_path: Path):
    book = load_book(str(_edge_file(tmp_path)))
    book.apply(_intent(account="备注", side=SIDE_BUY, name="贵州茅台", code="600519", price=1700.0))
    with pytest.raises(ValueError, match="非持仓页签同名"):
        book.save()


def test_flow_sheet_header_mismatch_blocks_save(tmp_path: Path):
    path = _edge_file(tmp_path)
    wb = openpyxl.load_workbook(path)
    bad = wb.create_sheet("交易流水")
    bad.append(["日期", "代码", "说明"])
    wb.save(path)
    wb.close()

    book = load_book(str(path))
    book.apply(_intent(side=SIDE_BUY, shares=10, price=21.0))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="表头不匹配"):
        book.save(append_flows=True)
    assert path.read_bytes() == before  # 原文件未被改写
    assert len(book.drafts) == 1
