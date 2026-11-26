# -*- coding: utf-8 -*-
"""Web 持仓录入参数校验与价格补全分支（holdings_edit）。

覆盖：变更清单结构/条数上限、单笔字段校验（账户/代码/方向/品种属性/交易日）、
按金额折算与按份额补全失败文案、场内行情与场外净值两条官方价路径、
mtime 闸门格式非法。

净值/行情取数全部 mock；持仓文件用 tmp 目录合成工作簿，不触碰真实持仓。
"""

from __future__ import annotations

import openpyxl
import pytest

from src.python.web.holdings_edit import (
    MAX_INTENTS,
    HoldingsEditError,
    _parse_intent,
    _parse_intents,
    _positive,
    save,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


def _holdings_file(tmp_path):
    path = tmp_path / "持仓.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.worksheets[0]
    ws.title = "股票账户"
    ws.append(["名称", "代码", "持仓份额", "每份成本"])
    ws.append(["长江电力", "600900", 1000, 20.0])
    wb.save(path)
    return path


@pytest.fixture
def holdings_path(tmp_path, monkeypatch):
    path = _holdings_file(tmp_path)
    monkeypatch.setattr("src.python.web.holdings_edit._holdings_path", lambda: str(path))
    return path


class TestParseIntents:
    @staticmethod
    def _ok_intent() -> dict:
        """一笔合法场内买入（补齐价格，免得取数）。"""
        return {
            "account": "股票账户",
            "code": "600900",
            "name": "长江电力",
            "side": "buy",
            "shares": 100,
            "price": 20.0,
            "trade_date": "2026-10-29",
        }

    def test_empty_list_rejected(self):
        with pytest.raises(HoldingsEditError, match="变更清单为空"):
            _parse_intents({"intents": []})
        with pytest.raises(HoldingsEditError, match="变更清单为空"):
            _parse_intents({"intents": "not-a-list"})

    def test_over_limit_rejected(self):
        with pytest.raises(HoldingsEditError, match=f"单次最多提交 {MAX_INTENTS} 笔变更"):
            _parse_intents({"intents": [{}] * (MAX_INTENTS + 1)})

    def test_non_dict_entry_rejected(self):
        with pytest.raises(HoldingsEditError, match="第 2 笔格式不合法"):
            _parse_intents({"intents": [self._ok_intent(), ["raw"]]})

    def test_valid_intent_passes_through(self):
        intents = _parse_intents({"intents": [self._ok_intent()]})
        assert len(intents) == 1
        assert intents[0].code == "600900"
        assert intents[0].price == pytest.approx(20.0)

    def test_missing_account_and_code_and_bad_side(self):
        base = {"account": "股票账户", "code": "600900", "name": "长江电力", "side": "buy"}
        with pytest.raises(HoldingsEditError, match="第 1 笔缺少账户"):
            _parse_intent({**base, "account": "  "}, 1)
        with pytest.raises(HoldingsEditError, match="第 2 笔缺少证券代码"):
            _parse_intent({**base, "code": ""}, 2)
        with pytest.raises(HoldingsEditError, match="第 3 笔方向非法（应为 buy / sell）"):
            _parse_intent({**base, "side": "hold"}, 3)

    def test_ambiguous_kind_requires_declared(self):
        raw = {"account": "股票账户", "code": "000001", "name": "某00重叠品种", "side": "buy", "shares": 100}
        with pytest.raises(HoldingsEditError, match="需选择品种属性"):
            _parse_intent(raw, 4)

    def test_otc_requires_trade_date(self):
        raw = {
            "account": "基金账户",
            "code": "005827",
            "name": "蓝筹精选",
            "side": "buy",
            "shares": 100,
            "asset_kind": "otc",
        }
        with pytest.raises(HoldingsEditError, match="第 5 笔场外产品必须填写交易日"):
            _parse_intent(raw, 5)

    def test_bad_trade_date_text(self):
        raw = {
            "account": "股票账户",
            "code": "600900",
            "name": "长江电力",
            "side": "buy",
            "shares": 100,
            "trade_date": "2026-13-45",
        }
        with pytest.raises(HoldingsEditError, match="第 6 笔"):
            _parse_intent(raw, 6)


class TestAmountAndPrice:
    def test_amount_conversion_uses_official_nav(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.fetcher.nav_lookup.resolve_purchase_shares",
            lambda code, date_text, amount: {"shares": 1234.5, "nav": 2.0},
        )
        raw = {
            "account": "基金账户",
            "code": "005827",
            "name": "蓝筹精选",
            "side": "buy",
            "amount": 2469,
            "trade_date": "2026-10-29",
            "asset_kind": "otc",
        }
        intent = _parse_intent(raw, 1)
        assert intent.shares == pytest.approx(1234.5)
        assert intent.price == pytest.approx(2.0)
        assert intent.name == "蓝筹精选"

    def test_amount_conversion_without_nav_rejected(self, monkeypatch):
        monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_purchase_shares", lambda *a: None)
        raw = {
            "account": "基金账户",
            "code": "005827",
            "side": "buy",
            "amount": 500,
            "trade_date": "2026-10-29",
            "asset_kind": "otc",
        }
        with pytest.raises(HoldingsEditError, match="官方净值尚未公布"):
            _parse_intent(raw, 2)

    def test_exchange_price_from_market_data(self, monkeypatch):
        monkeypatch.setattr("src.python.fetcher.price.fetch_market_data", lambda code: {"price": "18.75"})
        raw = {"account": "股票账户", "code": "600900", "side": "buy", "shares": 100, "trade_date": "2026-10-29"}
        intent = _parse_intent(raw, 3)
        assert intent.price == pytest.approx(18.75)
        assert intent.name == "600900"  # 缺 name 回落代码

    def test_exchange_price_unavailable(self, monkeypatch):
        monkeypatch.setattr("src.python.fetcher.price.fetch_market_data", lambda code: {"price": "abc"})
        raw = {"account": "股票账户", "code": "600900", "side": "buy", "shares": 100, "trade_date": "2026-10-29"}
        with pytest.raises(HoldingsEditError, match="第 4 笔未取到当前行情，请手填成交价"):
            _parse_intent(raw, 4)

    def test_otc_nav_lookup_missing(self, monkeypatch):
        monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_nav_on_trade_date", lambda *a: None)
        raw = {
            "account": "基金账户",
            "code": "005827",
            "side": "sell",
            "shares": 10,
            "trade_date": "2026-10-29",
            "asset_kind": "otc",
        }
        with pytest.raises(HoldingsEditError, match="取不到 2026-10-29 的官方净值"):
            _parse_intent(raw, 5)

    def test_positive_rejects_non_numeric_and_zero(self):
        with pytest.raises(HoldingsEditError, match="应为数字"):
            _positive("abc", "第 1 笔份额")
        with pytest.raises(HoldingsEditError, match="必须大于 0"):
            _positive(0, "第 1 笔份额")


class TestSaveGate:
    def test_invalid_base_mtime_rejected(self, holdings_path):
        with pytest.raises(HoldingsEditError, match="base_mtime 格式非法"):
            save({"base_mtime": "not-a-number", "intents": []})

    def test_stale_mtime_rejected_with_409_code(self, holdings_path):
        with pytest.raises(HoldingsEditError) as excinfo:
            save({"base_mtime": 1.0, "intents": []})
        assert excinfo.value.code == "HOLDINGS_STALE"
        assert "持仓文件已被其他程序修改" in str(excinfo.value)
