"""TUI 持仓录入面板（`tui/handlers_holdings`）交互分支覆盖。

覆盖点：
  - 账户/标的选择：非法编号、越界、卖出无持仓、路径分隔符账户名、新代码校验
  - 份额/金额/价格/交易日收集：``a``=全部、非数字、非正值、回车取行情、净值缺失降级手填
  - 场外买入两种口径：按金额（净值未公布则不成立）与按份额
  - 重复录入防线与价格量级校验（偏离超阈须二次确认）
  - 保存：文件被改动/草稿为空/丢弃草稿/只写持仓不记流水/写盘异常
  - 退出守卫：继续编辑 / 保存后退出（保存失败不退出）/ 丢弃退出
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.python.core.holdings_editor import PRICE_KIND_EXCHANGE, PRICE_KIND_OTC, SIDE_BUY, SIDE_SELL
from src.python.tui import handlers_holdings as hh

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class _Book:
    """HoldingsBook 最小替身：只实现面板用到的那几个面。"""

    def __init__(self, *, filepath: str = "/tmp/h.xlsx", accounts: dict | None = None) -> None:
        self.filepath = filepath
        self.accounts = accounts if accounts is not None else {"主账户": []}
        self.drafts: list[Any] = []
        self.saved: list[bool] = []

    def total_rows(self) -> int:
        return sum(len(rows) for rows in self.accounts.values())

    @property
    def account_names(self) -> list[str]:
        return list(self.accounts)

    def rows(self, account: str) -> list[Any]:
        return self.accounts.get(account, [])

    def dirty_accounts(self) -> set[str]:
        return {intent.account for intent in self.drafts}

    def is_dirty(self, account: str, code: str) -> bool:
        return any(i.account == account and i.code == code for i in self.drafts)

    def apply(self, intent) -> None:
        self.drafts.append(intent)

    def revert_last(self):
        return self.drafts.pop() if self.drafts else None

    def save(self, append_flows: bool = True) -> None:
        self.saved.append(append_flows)
        self.drafts.clear()


def _intent(**overrides) -> SimpleNamespace:
    base = dict(
        account="主账户",
        name="某基金",
        code="110020",
        side=SIDE_BUY,
        shares=100.0,
        price=1.2,
        trade_date="2026-07-01",
        action_label="买入",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _session(book: _Book | None = None, mtime: float = 0.0) -> hh._Session:
    return hh._Session(book=book or _Book(), mtime=mtime)


def _asks(monkeypatch, answers: list[Any]) -> None:
    monkeypatch.setattr(hh, "_ask", lambda _p: answers.pop(0))


class TestDispatchAlias:
    def test_alias_triggers_matching_action(self):
        hits: list[str] = []
        items = [
            hh.PanelItem("1", "查看", action=lambda: hits.append("list")),
            hh.PanelItem("2", "录入", action=lambda: hits.append("record")),
        ]

        hh._dispatch_alias(" p ", items)

        assert hits == ["record"]

    def test_unknown_text_reports_invalid(self, capsys):
        hh._dispatch_alias("z", [hh.PanelItem("1", "查看", action=lambda: None)])

        assert "无效选择" in capsys.readouterr().out

    def test_alias_without_action_is_noop(self, capsys):
        hh._dispatch_alias("L", [hh.PanelItem("1", "查看", kind="return")])

        assert capsys.readouterr().out == ""


class TestRenderFrame:
    def test_dirty_count_shown(self):
        session = _session(_Book())
        session.book.drafts.append(_intent())
        items = hh._panel_items(session)

        lines = hh._render_frame(session, hh.NavState(count=len(items)), items)

        assert any("1 笔变更待保存" in line for line in lines)

    def test_clean_state_and_aliases(self):
        session = _session(_Book())

        lines = hh._render_frame(session, hh.NavState(count=5), hh._panel_items(session))

        assert any("当前无未保存变更" in line for line in lines)
        assert any("[L]" in line and "查看持仓（含未保存变更）" in line for line in lines)

    def test_continue_entry_appears_after_first_draft(self):
        session = _session(_Book())
        session.last = ("主账户", "110020", "某基金", SIDE_BUY)

        keys = [item.key for item in hh._panel_items(session)]

        assert "6" in keys


class TestListPositions:
    def test_empty_book_hints_entry(self, capsys):
        hh._list_positions(_Book(accounts={}))

        assert "当前没有持仓记录" in capsys.readouterr().out

    def test_empty_account_and_dirty_rows(self, capsys):
        book = _Book(
            accounts={
                "空账户": [],
                "主账户": [SimpleNamespace(name="某基金", code="110020", shares=10.0, cost_price=1.0)],
            }
        )
        book.drafts.append(_intent())

        hh._list_positions(book)

        out = capsys.readouterr().out
        assert "（空账户）" in out
        assert "尚未保存" in out


class TestPickAccount:
    def test_number_selects_existing(self, monkeypatch):
        _asks(monkeypatch, ["1"])

        assert hh._pick_account(_Book()) == "主账户"

    def test_out_of_range_number(self, monkeypatch, capsys):
        _asks(monkeypatch, ["9"])

        assert hh._pick_account(_Book()) is None
        assert "无效编号" in capsys.readouterr().out

    def test_new_account_name_returned(self, monkeypatch):
        _asks(monkeypatch, ["新账户"])

        assert hh._pick_account(_Book()) == "新账户"

    def test_path_separator_rejected(self, monkeypatch, capsys):
        _asks(monkeypatch, ["a/b"])

        assert hh._pick_account(_Book()) is None
        assert "路径分隔符" in capsys.readouterr().out

    def test_cancel_paths(self, monkeypatch):
        _asks(monkeypatch, [None])

        assert hh._pick_account(_Book()) is None


class TestPickAsset:
    def test_sell_without_rows_rejected(self, monkeypatch, capsys):
        _asks(monkeypatch, [])

        assert hh._pick_asset(_Book(accounts={"主账户": []}), "主账户", SIDE_SELL) is None
        assert "没有可卖出的持仓" in capsys.readouterr().out

    def test_sell_new_code_rejected(self, monkeypatch, capsys):
        book = _Book(accounts={"主账户": [SimpleNamespace(name="某基金", code="110020", shares=1.0)]})
        _asks(monkeypatch, ["N"])

        assert hh._pick_asset(book, "主账户", SIDE_SELL) is None
        assert "卖出只能选择已有持仓" in capsys.readouterr().out

    def test_digit_out_of_range(self, monkeypatch, capsys):
        _asks(monkeypatch, ["5"])

        assert hh._pick_asset(_Book(), "主账户", SIDE_BUY) is None
        assert "无效选择" in capsys.readouterr().out

    def test_selects_existing_row(self, monkeypatch):
        book = _Book(accounts={"主账户": [SimpleNamespace(name="某基金", code="110020", shares=1.0)]})
        _asks(monkeypatch, ["1"])

        assert hh._pick_asset(book, "主账户", SIDE_BUY) == ("某基金", "110020")

    def test_new_asset_route(self, monkeypatch):
        _asks(monkeypatch, ["n"])
        monkeypatch.setattr(hh, "_input_new_asset", lambda: ("新标的", "600519"))

        assert hh._pick_asset(_Book(), "主账户", SIDE_BUY) == ("新标的", "600519")


class TestInputNewAsset:
    def test_invalid_code(self, monkeypatch, capsys):
        _asks(monkeypatch, ["12ab"])

        assert hh._input_new_asset() is None
        assert "代码应为 6 位数字" in capsys.readouterr().out

    def test_name_resolved_from_market(self, monkeypatch):
        _asks(monkeypatch, ["600519"])
        monkeypatch.setattr(hh, "_resolve_name", lambda _c: "贵州茅台")

        assert hh._input_new_asset() == ("贵州茅台", "600519")

    def test_name_typed_when_unresolved(self, monkeypatch):
        _asks(monkeypatch, ["600519", "自定义名"])
        monkeypatch.setattr(hh, "_resolve_name", lambda _c: "")

        assert hh._input_new_asset() == ("自定义名", "600519")

    def test_blank_typed_name_cancels(self, monkeypatch):
        _asks(monkeypatch, ["600519", "   "])
        monkeypatch.setattr(hh, "_resolve_name", lambda _c: "")

        assert hh._input_new_asset() is None


class TestAskHelpers:
    def test_entry_mode_default_is_amount(self, monkeypatch):
        _asks(monkeypatch, [""])

        assert hh._ask_entry_mode() == "amount"

    def test_entry_mode_shares(self, monkeypatch):
        _asks(monkeypatch, ["2"])

        assert hh._ask_entry_mode() == "shares"

    def test_entry_mode_invalid(self, monkeypatch, capsys):
        _asks(monkeypatch, ["9"])

        assert hh._ask_entry_mode() is None
        assert "无效选择" in capsys.readouterr().out

    def test_entry_mode_zero_defaults_to_amount(self, monkeypatch):
        _asks(monkeypatch, ["0"])

        assert hh._ask_entry_mode() == "amount", "回车与 0 同义：默认按金额录入"

    def test_amount_rejects_non_numeric(self, monkeypatch, capsys):
        _asks(monkeypatch, ["abc"])

        assert hh._ask_amount() is None
        assert "金额应为数字" in capsys.readouterr().out

    def test_amount_rejects_non_positive(self, monkeypatch, capsys):
        _asks(monkeypatch, ["-1"])

        assert hh._ask_amount() is None
        assert "金额必须大于 0" in capsys.readouterr().out

    def test_amount_parsed(self, monkeypatch):
        _asks(monkeypatch, ["1000"])

        assert hh._ask_amount() == 1000.0

    def test_shares_all_uses_available(self, monkeypatch):
        _asks(monkeypatch, ["a"])

        assert hh._ask_shares("卖出", 33.0) == 33.0

    def test_shares_all_without_available(self, monkeypatch, capsys):
        _asks(monkeypatch, ["a"])

        assert hh._ask_shares("卖出") is None
        assert "没有可卖出的份额" in capsys.readouterr().out

    def test_shares_rejects_bad_number(self, monkeypatch, capsys):
        _asks(monkeypatch, ["x"])

        assert hh._ask_shares("买入") is None
        assert "份额应为数字" in capsys.readouterr().out

    def test_shares_rejects_non_positive(self, monkeypatch, capsys):
        _asks(monkeypatch, ["0"])

        assert hh._ask_shares("买入") is None

    def test_shares_parsed(self, monkeypatch):
        _asks(monkeypatch, ["12.5"])

        assert hh._ask_shares("买入") == pytest.approx(12.5)

    def test_trade_date_defaults_to_today(self, monkeypatch):
        from datetime import date

        _asks(monkeypatch, [""])

        assert hh._ask_trade_date() == date.today().isoformat()

    def test_trade_date_invalid(self, monkeypatch, capsys):
        _asks(monkeypatch, ["not-a-date"])

        assert hh._ask_trade_date() is None
        assert "[ERR]" in capsys.readouterr().out

    def test_trade_date_normalized(self, monkeypatch):
        _asks(monkeypatch, ["2026/07/01"])

        assert hh._ask_trade_date() == "2026-07-01"

    def test_parse_price_rejects_text(self, capsys):
        assert hh._parse_price("x") is None
        assert "价格应为数字" in capsys.readouterr().out

    def test_parse_price_rejects_non_positive(self, capsys):
        assert hh._parse_price("0") is None
        assert "价格必须大于 0" in capsys.readouterr().out

    def test_parse_price_ok(self):
        assert hh._parse_price(" 1.23 ") == pytest.approx(1.23)

    def test_confirm_defaults_to_no(self, monkeypatch):
        _asks(monkeypatch, [""])

        assert hh._confirm("继续？") is False

    def test_confirm_accepts_yes_variants(self, monkeypatch):
        for answer in ("y", "YES", " 是 "):
            _asks(monkeypatch, [answer])
            assert hh._confirm("继续？") is True


class TestPriceKindAndSanity:
    def test_resolve_kind_direct(self, monkeypatch):
        monkeypatch.setattr("src.python.core.holdings_editor.resolve_entry_kind", lambda c, n: PRICE_KIND_EXCHANGE)

        assert hh._resolve_price_kind("600519", "贵州茅台") == PRICE_KIND_EXCHANGE

    def test_overlap_hint_otc(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "src.python.core.holdings_editor.resolve_entry_kind",
            lambda c, n: (_ for _ in ()).throw(ValueError("overlap")),
        )
        monkeypatch.setattr(hh, "price_kind_from_quote", lambda _d: PRICE_KIND_OTC, raising=False)
        monkeypatch.setattr("src.python.fetcher.price.price_kind_from_quote", lambda _d: PRICE_KIND_OTC)
        monkeypatch.setattr(hh, "_market_data", lambda _c: {})

        assert hh._resolve_price_kind("001234", "某基金") == PRICE_KIND_OTC
        assert "场外基金" in capsys.readouterr().out

    def test_overlap_asks_user_and_defaults_exchange(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.core.holdings_editor.resolve_entry_kind",
            lambda c, n: (_ for _ in ()).throw(ValueError("overlap")),
        )
        monkeypatch.setattr("src.python.fetcher.price.price_kind_from_quote", lambda _d: None)
        monkeypatch.setattr(hh, "_market_data", lambda _c: {})
        _asks(monkeypatch, [""])

        assert hh._resolve_price_kind("001234", "x") == PRICE_KIND_EXCHANGE

    def test_overlap_user_choice_invalid_then_otc(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "src.python.core.holdings_editor.resolve_entry_kind",
            lambda c, n: (_ for _ in ()).throw(ValueError("overlap")),
        )
        monkeypatch.setattr("src.python.fetcher.price.price_kind_from_quote", lambda _d: None)
        monkeypatch.setattr(hh, "_market_data", lambda _c: {})
        _asks(monkeypatch, ["9", "2"])

        assert hh._resolve_price_kind("001234", "x") is None
        assert hh._resolve_price_kind("001234", "x") == PRICE_KIND_OTC
        assert "无效选择" in capsys.readouterr().out

    def test_price_sanity_without_reference_passes(self):
        assert hh._price_sanity("x", 100.0, 0.0) is True

    def test_price_sanity_within_threshold_passes(self):
        assert hh._price_sanity("x", 1.05, 1.0) is True

    def test_price_sanity_far_off_asks_confirmation(self, monkeypatch, capsys):
        asked: list[str] = []
        monkeypatch.setattr(hh, "_confirm", lambda q: asked.append(q) or True)

        assert hh._price_sanity("x", 10.0, 1.0) is True
        assert asked, "偏离超阈必须要求二次确认"
        assert "相差" in capsys.readouterr().out


class TestAskPriceBranches:
    def test_exchange_manual_price(self, monkeypatch):
        _asks(monkeypatch, ["1.5"])
        monkeypatch.setattr(hh, "_resolve_quote", lambda _c: 1.48)

        assert hh._ask_exchange_price("600519", "贵州茅台") == (pytest.approx(1.5), pytest.approx(1.48))

    def test_exchange_enter_uses_quote(self, monkeypatch):
        _asks(monkeypatch, [""])
        monkeypatch.setattr(hh, "_resolve_quote", lambda _c: 1.48)

        assert hh._ask_exchange_price("600519", "贵州茅台") == (pytest.approx(1.48), pytest.approx(1.48))

    def test_exchange_no_quote_falls_back_to_typed(self, monkeypatch, capsys):
        _asks(monkeypatch, ["", "2.0"])
        monkeypatch.setattr(hh, "_resolve_quote", lambda _c: 0.0)

        assert hh._ask_exchange_price("600519", "x") == (pytest.approx(2.0), 0.0)
        assert "未取到当前行情" in capsys.readouterr().out

    def test_exchange_no_quote_and_blank_aborts(self, monkeypatch):
        _asks(monkeypatch, ["", ""])
        monkeypatch.setattr(hh, "_resolve_quote", lambda _c: 0.0)

        assert hh._ask_exchange_price("600519", "x") is None

    def test_otc_manual_price_uses_nav_reference(self, monkeypatch):
        _asks(monkeypatch, ["1.234"])
        monkeypatch.setattr(hh, "_nav_reference", lambda _c, _d: 1.23)

        assert hh._ask_otc_price("110020", "2026-07-01") == (pytest.approx(1.234), pytest.approx(1.23))

    def test_otc_nav_missing_allows_typed_price(self, monkeypatch, capsys):
        _asks(monkeypatch, ["", "9.9"])
        monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_nav_on_trade_date", lambda _c, _d: None)

        assert hh._ask_otc_price("110020", "2026-07-01") == (pytest.approx(9.9), 0.0)
        assert "取不到" in capsys.readouterr().out

    def test_otc_nav_missing_and_blank_aborts(self, monkeypatch):
        _asks(monkeypatch, ["", ""])
        monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_nav_on_trade_date", lambda _c, _d: None)

        assert hh._ask_otc_price("110020", "2026-07-01") is None

    def test_otc_exact_date_nav_used(self, monkeypatch):
        _asks(monkeypatch, [""])
        monkeypatch.setattr(
            "src.python.fetcher.nav_lookup.resolve_nav_on_trade_date",
            lambda _c, _d: {"nav": 1.234, "nav_date": "2026-07-01", "exact_date": True},
        )

        assert hh._ask_otc_price("110020", "2026-07-01") == (pytest.approx(1.234), pytest.approx(1.234))

    def test_otc_fallback_date_requires_confirmation(self, monkeypatch, capsys):
        _asks(monkeypatch, ["", ""])
        monkeypatch.setattr(
            "src.python.fetcher.nav_lookup.resolve_nav_on_trade_date",
            lambda _c, _d: {"nav": 1.2, "nav_date": "2026-06-30", "exact_date": False},
        )
        monkeypatch.setattr(hh, "_confirm", lambda _q: False)

        assert hh._ask_otc_price("110020", "2026-07-01") is None
        assert "采用" in capsys.readouterr().out

    def test_resolve_quote_tolerates_bad_payload(self, monkeypatch):
        monkeypatch.setattr(hh, "_market_data", lambda _c: {"price": "abc"})

        assert hh._resolve_quote("600519") == 0.0


class TestCollectTradeFields:
    def test_exchange_flow(self, monkeypatch):
        _asks(monkeypatch, ["10", "2026-07-01", "1.2"])
        monkeypatch.setattr(hh, "_resolve_quote", lambda _c: 1.2)

        fields = hh._collect_trade_fields("x", "600519", SIDE_BUY, PRICE_KIND_EXCHANGE, _Book(), "主账户")

        assert fields is not None
        assert fields[0] == pytest.approx(10.0) and fields[2] == "2026-07-01"

    def test_sell_uses_held_shares(self, monkeypatch):
        book = _Book(accounts={"主账户": [SimpleNamespace(name="x", code="600519", shares=7.0)]})
        _asks(monkeypatch, ["a", "", "1.2"])
        monkeypatch.setattr(hh, "_resolve_quote", lambda _c: 1.2)

        fields = hh._collect_trade_fields("x", "600519", SIDE_SELL, PRICE_KIND_EXCHANGE, book, "主账户")

        assert fields is not None and fields[0] == pytest.approx(7.0)

    def test_otc_buy_amount_mode_converts_by_nav(self, monkeypatch, capsys):
        _asks(monkeypatch, ["1", "2026-07-01", "1000"])
        monkeypatch.setattr(
            "src.python.fetcher.nav_lookup.resolve_purchase_shares",
            lambda _c, _d, _a: {"shares": 800.0, "nav": 1.25, "nav_date": "2026-07-01", "exact_date": True},
        )

        fields = hh._collect_trade_fields("x", "110020", SIDE_BUY, PRICE_KIND_OTC, _Book(), "主账户")

        assert fields is not None
        assert fields[0] == pytest.approx(800.0) and fields[1] == pytest.approx(1.25)
        assert any("金额" in line for line in fields[3]), "按金额录入须回显金额与折算净值"

    def test_otc_buy_amount_mode_nav_missing_aborts(self, monkeypatch, capsys):
        _asks(monkeypatch, ["1", "2026-07-01", "1000"])
        monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_purchase_shares", lambda _c, _d, _a: None)

        assert hh._collect_trade_fields("x", "110020", SIDE_BUY, PRICE_KIND_OTC, _Book(), "主账户") is None
        assert "净值尚未公布" in capsys.readouterr().out

    def test_otc_buy_shares_mode(self, monkeypatch):
        _asks(monkeypatch, ["2", "2026-07-01", "100", ""])
        monkeypatch.setattr(
            "src.python.fetcher.nav_lookup.resolve_nav_on_trade_date",
            lambda _c, _d: {"nav": 1.25, "nav_date": "2026-07-01", "exact_date": True},
        )

        fields = hh._collect_trade_fields("x", "110020", SIDE_BUY, PRICE_KIND_OTC, _Book(), "主账户")

        assert fields is not None and fields[3] == []


class TestRecordFlow:
    def _setup(
        self, monkeypatch, *, kind=PRICE_KIND_EXCHANGE, sanity=True, confirm=True, duplicate=None, apply_error=None
    ):
        session = _session(_Book())
        monkeypatch.setattr(hh, "_pick_account", lambda _b: "主账户")
        monkeypatch.setattr(hh, "_pick_asset", lambda _b, _a, _s: ("某基金", "110020"))
        monkeypatch.setattr(hh, "_resolve_price_kind", lambda _c, _n: kind)
        monkeypatch.setattr(hh, "_collect_trade_fields", lambda *_a, **_k: (10.0, 1.2, "2026-07-01", ["  附加行"], 1.2))
        monkeypatch.setattr(hh, "_price_sanity", lambda *a: sanity)
        monkeypatch.setattr(hh, "_find_duplicate", lambda *a: duplicate)
        monkeypatch.setattr(hh, "_confirm", lambda _q: confirm)
        if apply_error is not None:
            monkeypatch.setattr(session.book, "apply", lambda _i: (_ for _ in ()).throw(ValueError(apply_error)))
        return session

    def test_success_records_draft_and_last(self, monkeypatch, capsys):
        session = self._setup(monkeypatch)

        hh._record(session, SIDE_BUY)

        assert len(session.book.drafts) == 1
        assert session.last == ("主账户", "110020", "某基金", SIDE_BUY)
        out = capsys.readouterr().out
        assert "已加入草稿" in out and "附加行" in out

    def test_price_sanity_rejection_aborts(self, monkeypatch, capsys):
        session = self._setup(monkeypatch, sanity=False)

        hh._record(session, SIDE_BUY)

        assert session.book.drafts == []
        assert "已取消本笔录入" in capsys.readouterr().out

    def test_duplicate_rejected_when_confirmation_declined(self, monkeypatch, capsys):
        session = self._setup(monkeypatch, duplicate=_intent(), confirm=False)

        hh._record(session, SIDE_BUY)

        assert session.book.drafts == []
        assert "完全相同的录入" in capsys.readouterr().out

    def test_duplicate_accepted_when_confirmed(self, monkeypatch, capsys):
        session = self._setup(monkeypatch, duplicate=_intent(), confirm=True)

        hh._record(session, SIDE_BUY)

        assert len(session.book.drafts) == 1

    def test_apply_value_error_reported(self, monkeypatch, capsys):
        session = self._setup(monkeypatch, apply_error="份额为负")

        hh._record(session, SIDE_BUY)

        assert "份额为负" in capsys.readouterr().out

    def test_cancel_at_account_pick(self, monkeypatch, capsys):
        session = _session(_Book())
        monkeypatch.setattr(hh, "_pick_account", lambda _b: None)

        hh._record(session, SIDE_BUY)

        assert session.book.drafts == []
        assert "已取消本笔录入" in capsys.readouterr().out

    def test_cancel_at_asset_pick(self, monkeypatch):
        session = _session(_Book())
        monkeypatch.setattr(hh, "_pick_account", lambda _b: "主账户")
        monkeypatch.setattr(hh, "_pick_asset", lambda _b, _a, _s: None)

        hh._record(session, SIDE_BUY)

        assert session.book.drafts == []

    def test_cancel_at_kind_resolution(self, monkeypatch):
        session = _session(_Book())
        monkeypatch.setattr(hh, "_pick_account", lambda _b: "主账户")
        monkeypatch.setattr(hh, "_pick_asset", lambda _b, _a, _s: ("x", "110020"))
        monkeypatch.setattr(hh, "_resolve_price_kind", lambda _c, _n: None)

        hh._record(session, SIDE_BUY)

        assert session.book.drafts == []

    def test_preset_skips_pickers(self, monkeypatch):
        session = _session(_Book())
        monkeypatch.setattr(hh, "_pick_account", lambda _b: pytest.fail("preset 不应再选账户"))
        monkeypatch.setattr(hh, "_resolve_price_kind", lambda _c, _n: PRICE_KIND_EXCHANGE)
        monkeypatch.setattr(hh, "_collect_trade_fields", lambda *_a, **_k: (1.0, 1.0, "2026-07-01", [], 1.0))
        monkeypatch.setattr(hh, "_price_sanity", lambda *a: True)
        monkeypatch.setattr(hh, "_find_duplicate", lambda *a: None)

        hh._record(session, SIDE_BUY, preset=("主账户", "110020", "某基金"))

        assert len(session.book.drafts) == 1


class TestUndoAndSave:
    def test_undo_without_drafts_hints(self, capsys):
        hh._undo_last(_session(_Book()))

        assert "没有可撤销的录入" in capsys.readouterr().out

    def test_undo_reports_remaining(self, monkeypatch, capsys):
        book = _Book()
        book.drafts.append(_intent())
        _asks(monkeypatch, [])

        hh._undo_last(_session(book))

        assert "已撤销" in capsys.readouterr().out

    def test_save_without_drafts_hints(self, capsys):
        hh._save(_session(_Book()))

        assert "没有待保存的变更" in capsys.readouterr().out

    def test_save_aborts_when_file_changed(self, monkeypatch, tmp_path):
        book = _Book(filepath=str(tmp_path / "h.xlsx"))
        book.drafts.append(_intent())
        errors: list[str] = []
        monkeypatch.setattr(hh, "emit_error", lambda msg, _d, advice=None: errors.append(msg))

        hh._save(_session(book, mtime=0.0))

        assert book.saved == []
        assert errors, "文件被外部改动时必须拒绝写回"

    def test_save_cancel_keeps_drafts(self, monkeypatch, tmp_path):
        book = _Book(filepath=str(tmp_path / "h.xlsx"))
        book.drafts.append(_intent())
        _asks(monkeypatch, ["0"])
        monkeypatch.setattr(hh, "_file_unchanged", lambda _s: True)

        hh._save(_session(book))

        assert book.saved == [] and len(book.drafts) == 1

    def test_save_discard_drafts(self, monkeypatch, tmp_path, capsys):
        book = _Book(filepath=str(tmp_path / "h.xlsx"))
        book.drafts.append(_intent())
        _asks(monkeypatch, ["2"])
        monkeypatch.setattr(hh, "_file_unchanged", lambda _s: True)

        hh._save(_session(book))

        assert book.saved == [] and book.drafts == []
        assert "已丢弃" in capsys.readouterr().out

    def test_save_default_records_trade_flows(self, monkeypatch, tmp_path):
        book = _Book(filepath=str(tmp_path / "h.xlsx"))
        (tmp_path / "h.xlsx").write_text("x", encoding="utf-8")
        book.drafts.append(_intent())
        _asks(monkeypatch, [""])
        monkeypatch.setattr(hh, "_file_unchanged", lambda _s: True)
        monkeypatch.setattr(hh, "_backup_file", lambda _p: str(tmp_path / "h.xlsx.bak"))

        hh._save(_session(book))

        assert book.saved == [True]

    def test_save_n_writes_positions_only(self, monkeypatch, tmp_path):
        book = _Book(filepath=str(tmp_path / "h.xlsx"))
        (tmp_path / "h.xlsx").write_text("x", encoding="utf-8")
        book.drafts.append(_intent())
        _asks(monkeypatch, ["n"])
        monkeypatch.setattr(hh, "_file_unchanged", lambda _s: True)
        monkeypatch.setattr(hh, "_backup_file", lambda _p: "")

        hh._save(_session(book))

        assert book.saved == [False]

    def test_save_write_error_routes_to_emit_error(self, monkeypatch, tmp_path):
        book = _Book(filepath=str(tmp_path / "h.xlsx"))
        book.drafts.append(_intent())
        _asks(monkeypatch, [""])
        errors: list[str] = []
        monkeypatch.setattr(hh, "_file_unchanged", lambda _s: True)
        monkeypatch.setattr(hh, "_backup_file", lambda _p: "")
        monkeypatch.setattr(hh, "emit_error", lambda msg, _d, advice=None: errors.append(msg))
        monkeypatch.setattr(book, "save", lambda append_flows=True: (_ for _ in ()).throw(OSError("disk")))

        hh._save(_session(book))

        assert errors == ["disk"]

    def test_backup_failure_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hh.shutil, "copy2", lambda *a, **k: (_ for _ in ()).throw(OSError("denied")))

        assert hh._backup_file(str(tmp_path / "h.xlsx")) == ""

    def test_file_unchanged_handles_missing_file(self, monkeypatch, capsys):
        session = _session(_Book(filepath="/nonexistent/h.xlsx"))
        monkeypatch.setattr(hh, "emit_error", lambda msg, _d, advice=None: print(msg))

        assert hh._file_unchanged(session) is False
        assert "不可访问" in capsys.readouterr().out


class TestExitGuard:
    def test_enter_keeps_editing(self, monkeypatch):
        _asks(monkeypatch, [""])

        assert hh._exit_guard(_session(_Book())) is False

    def test_invalid_choice_keeps_editing(self, monkeypatch, capsys):
        _asks(monkeypatch, ["zzz"])

        assert hh._exit_guard(_session(_Book())) is False
        assert "无效选择" in capsys.readouterr().out

    def test_none_keeps_editing(self, monkeypatch):
        _asks(monkeypatch, [None])

        assert hh._exit_guard(_session(_Book())) is False

    def test_save_and_exit_only_when_drafts_cleared(self, monkeypatch):
        book = _Book()
        book.drafts.append(_intent())
        session = _session(book)
        _asks(monkeypatch, ["1", "1"])
        monkeypatch.setattr(hh, "_save", lambda s: None)

        assert hh._exit_guard(session) is False, "保存失败（草稿未清空）不得退出"

        monkeypatch.setattr(hh, "_save", lambda s: s.book.drafts.clear())
        assert hh._exit_guard(session) is True

    def test_discard_exits(self, monkeypatch):
        _asks(monkeypatch, ["2"])

        assert hh._exit_guard(_session(_Book())) is True


class TestPanelEntry:
    def test_no_file_selected_returns(self, monkeypatch):
        entered: list[str] = []
        monkeypatch.setattr(hh, "select_holdings_file", lambda: "")
        monkeypatch.setattr(hh, "panel_loop", lambda *a, **k: entered.append("panel"))

        hh.run_holdings_entry_panel()

        assert entered == [], "未选文件时不得进入面板"

    def test_load_failure_reports_and_returns(self, monkeypatch, tmp_path):
        target = tmp_path / "h.xlsx"
        target.write_text("x", encoding="utf-8")
        messages: list[str] = []
        monkeypatch.setattr(hh, "select_holdings_file", lambda: str(target))
        monkeypatch.setattr(hh, "load_book", lambda _p: (_ for _ in ()).throw(OSError("bad")))
        monkeypatch.setattr(hh, "print_error_with_hint", lambda e, msg: messages.append(msg))

        hh.run_holdings_entry_panel()

        assert messages == ["读取持仓文件失败"]

    def test_loop_returns_without_drafts(self, monkeypatch, tmp_path, capsys):
        target = tmp_path / "h.xlsx"
        target.write_text("x", encoding="utf-8")
        monkeypatch.setattr(hh, "select_holdings_file", lambda: str(target))
        monkeypatch.setattr(hh, "load_book", lambda _p: _Book(filepath=str(target)))
        monkeypatch.setattr(hh, "panel_loop", lambda *a, **k: None)

        hh.run_holdings_entry_panel()

        assert "已载入" in capsys.readouterr().out
