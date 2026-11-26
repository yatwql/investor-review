"""TUI 持仓录入面板（`tui/handlers_holdings`）的取消/降级通道覆盖。

锁住的契约：录入链每一环（账户、标的、新代码、份额、金额、交易日、价格、净值）
都必须有「回车取消」与「取数失败不阻断」两条出口——任一步取消都返回 ``None`` 让
面板回显「已取消本笔」，取数异常只记 warning 并把参考价降为 0，绝不把半成品写进草稿。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from src.python.core.holdings_editor import PRICE_KIND_EXCHANGE, PRICE_KIND_OTC, SIDE_BUY, SIDE_SELL
from src.python.tui import handlers_holdings as hh

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class _Book:
    """HoldingsBook 最小替身：只实现本轮用到的选择面（账户名 / 账户内持仓行）。"""

    def __init__(self, *, accounts: dict | None = None, drafts: list[Any] | None = None) -> None:
        self.filepath = "/tmp/holdings.xlsx"
        self.accounts = accounts if accounts is not None else {"主账户": []}
        self.drafts: list[Any] = drafts if drafts is not None else []

    @property
    def account_names(self) -> list[str]:
        return list(self.accounts)

    def rows(self, account: str) -> list[Any]:
        return self.accounts.get(account, [])

    def total_rows(self) -> int:
        return sum(len(rows) for rows in self.accounts.values())


def _asks(monkeypatch, answers: list[Any]) -> None:
    """按序喂入 ``_ask`` 的回答（``None`` = Esc 取消）。"""
    monkeypatch.setattr(hh, "_ask", lambda _p: answers.pop(0))


def _row(name: str, code: str, shares: float) -> SimpleNamespace:
    return SimpleNamespace(name=name, code=code, shares=shares, cost_price=1.0)


class TestPanelExitGuard:
    def test_exit_guard_accepts_discard_and_leaves_panel(self, monkeypatch, tmp_path, capsys):
        """面板有草稿时退出须经守卫：选 2（丢弃退出）后真正返回，不留循环。"""
        target = tmp_path / "h.xlsx"
        target.write_text("x", encoding="utf-8")
        prompts: list[str] = []

        def _fake_ask(prompt: str) -> str:
            prompts.append(prompt)
            return "2"

        monkeypatch.setattr(hh, "select_holdings_file", lambda: str(target))
        monkeypatch.setattr(hh, "load_book", lambda _p: _Book(drafts=[SimpleNamespace()]))
        monkeypatch.setattr(hh, "panel_loop", lambda *a, **k: None)
        monkeypatch.setattr(hh, "_ask", _fake_ask)

        hh.run_holdings_entry_panel()

        assert "已载入" in capsys.readouterr().out
        assert len(prompts) == 1
        assert "变更未保存" in prompts[0], "守卫提示须点明变更条数与三选项"


class TestPickAccountCancelPaths:
    def test_empty_book_hints_new_account(self, monkeypatch, capsys):
        """无已有账户时提示「输入新账户名即可新建」，且新名直接成为账户。"""
        _asks(monkeypatch, ["新账户"])

        assert hh._pick_account(_Book(accounts={})) == "新账户"
        assert "（暂无账户，输入新账户名即可新建）" in capsys.readouterr().out

    def test_blank_name_cancels(self, monkeypatch):
        """只输空白 = 取消本笔（不建空名账户）。"""
        _asks(monkeypatch, ["   "])

        assert hh._pick_account(_Book()) is None


class TestPickAssetCancelPaths:
    def test_esc_cancels(self, monkeypatch):
        _asks(monkeypatch, [None])

        assert hh._pick_asset(_Book(), "主账户", SIDE_BUY) is None

    def test_blank_input_cancels(self, monkeypatch):
        _asks(monkeypatch, ["  "])

        assert hh._pick_asset(_Book(), "主账户", SIDE_BUY) is None


class TestInputNewAssetCancel:
    def test_esc_cancels(self, monkeypatch):
        """新代码提示处 Esc → 取消本笔（不再追问名称）。"""
        _asks(monkeypatch, [None])

        assert hh._input_new_asset() is None


class TestMarketDataDegrade:
    def test_quote_failure_returns_none_and_warns(self, monkeypatch, caplog):
        """行情取数抛错只记 warning 并返回 None（名称/参考价降级为空/0，不阻断录入）。"""
        monkeypatch.setattr(
            "src.python.fetcher.price.fetch_market_data",
            lambda _code: (_ for _ in ()).throw(RuntimeError("行情源不可用")),
        )

        with caplog.at_level("WARNING"):
            assert hh._market_data("600519") is None

        assert "行情取数异常" in caplog.text
        assert hh._resolve_name("600519") == "", "名称取不到时降级为空串，由调用方手输"


class TestCollectTradeFieldsCancel:
    def test_share_prompt_cancel(self, monkeypatch):
        """份额提示处取消 → 本笔不成立。"""
        _asks(monkeypatch, ["0"])

        assert hh._collect_trade_fields("某基金", "600519", SIDE_BUY, PRICE_KIND_EXCHANGE, _Book(), "主账户") is None

    def test_trade_date_cancel(self, monkeypatch):
        """交易日提示处取消 → 本笔不成立。"""
        _asks(monkeypatch, ["5", "0"])

        assert hh._collect_trade_fields("某基金", "600519", SIDE_BUY, PRICE_KIND_EXCHANGE, _Book(), "主账户") is None

    def test_price_cancel(self, monkeypatch):
        """成交价提示处取消 → 本笔不成立。"""
        _asks(monkeypatch, ["5", "", "0"])

        assert hh._collect_trade_fields("某基金", "600519", SIDE_BUY, PRICE_KIND_EXCHANGE, _Book(), "主账户") is None


class TestCollectOtcBuyCancel:
    def test_invalid_entry_mode_cancels(self, monkeypatch):
        """录入口径输入 1/2 之外的键 → 本笔不成立（不猜口径）。"""
        _asks(monkeypatch, ["9"])

        assert hh._collect_otc_buy("110020", "某基金") is None

    def test_trade_date_cancel(self, monkeypatch):
        _asks(monkeypatch, ["1", "0"])

        assert hh._collect_otc_buy("110020", "某基金") is None

    def test_amount_cancel(self, monkeypatch):
        _asks(monkeypatch, ["1", "", "0"])

        assert hh._collect_otc_buy("110020", "某基金") is None

    def test_shares_cancel(self, monkeypatch):
        _asks(monkeypatch, ["2", "", "0"])

        assert hh._collect_otc_buy("110020", "某基金") is None

    def test_otc_price_cancel(self, monkeypatch):
        _asks(monkeypatch, ["2", "", "5", "0"])

        assert hh._collect_otc_buy("110020", "某基金") is None

    def test_amount_mode_reports_borrowed_nav_date(self, monkeypatch):
        """交易日无净值时按最近净值日折算，并在回显里点明实际净值日期。"""
        _asks(monkeypatch, ["1", "2026-07-04", "1000"])
        monkeypatch.setattr(
            "src.python.fetcher.nav_lookup.resolve_purchase_shares",
            lambda _c, _d, _a: {"shares": 800.0, "nav": 1.25, "nav_date": "2026-07-03", "exact_date": False},
        )

        fields = hh._collect_otc_buy("110020", "某基金")

        assert fields is not None
        shares, nav, trade_date, extra, reference = fields
        assert shares == pytest.approx(800.0)
        assert nav == pytest.approx(1.25)
        assert reference == pytest.approx(nav)
        assert trade_date == "2026-07-04"
        assert any("2026-07-04 无净值" in line and "2026-07-03" in line for line in extra)


class TestAmountAndSharesValidation:
    @pytest.mark.parametrize("answer", [None, "0", "   "])
    def test_amount_cancel_paths(self, monkeypatch, answer):
        """申购金额提示的三种取消口径（Esc / 0 / 空回车）都不成立本笔。"""
        _asks(monkeypatch, [answer])

        assert hh._ask_amount() is None

    def test_non_positive_shares_rejected(self, monkeypatch, capsys):
        """份额 <= 0 视为录入错误（0 已被「取消」占用，故负数须给显式报错）。"""
        _asks(monkeypatch, ["-3"])

        assert hh._ask_shares("买入", None) is None
        assert "份额必须大于 0" in capsys.readouterr().out


class TestHeldSharesLookup:
    def test_sell_without_matching_code_is_none(self):
        """卖出方向但账户内无该代码 → 无可卖份额（不误给 0 份额）。"""
        book = _Book(accounts={"主账户": [_row("某基金", "110020", 10.0)]})

        assert hh._held_shares(book, "主账户", "600519", SIDE_SELL) is None
        assert hh._held_shares(book, "主账户", "110020", SIDE_SELL) == pytest.approx(10.0)


class TestNavReference:
    def test_missing_nav_degrades_to_zero(self, monkeypatch):
        """取不到净值的参考价为 0（后续价格量级校验据此跳过，不误报偏离）。"""
        monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_nav_on_trade_date", lambda _c, _d: None)

        assert hh._nav_reference("110020", "2026-07-01") == 0.0

    def test_nav_returned_from_lookup(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.fetcher.nav_lookup.resolve_nav_on_trade_date",
            lambda _c, _d: {"nav": 1.2345, "nav_date": "2026-07-01", "exact_date": True},
        )

        assert hh._nav_reference("110020", "2026-07-01") == pytest.approx(1.2345)


class TestTradeDatePrompt:
    def test_cancel_returns_none(self, monkeypatch):
        _asks(monkeypatch, ["0"])

        assert hh._ask_trade_date() is None


class TestPriceRouting:
    def test_otc_kind_routes_to_otc_prompt(self, monkeypatch):
        """场外品种走场外价格口径（手填价 + 官方净值作参考价）。"""
        _asks(monkeypatch, ["1.234"])
        monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_nav_on_trade_date", lambda _c, _d: None)

        price, reference = hh._ask_price("110020", "某基金", PRICE_KIND_OTC, "2026-07-01")

        assert price == pytest.approx(1.234)
        assert reference == pytest.approx(0.0)

    def test_exchange_esc_cancels(self, monkeypatch):
        _asks(monkeypatch, [None])

        assert hh._ask_exchange_price("600519", "某证券") is None

    def test_otc_esc_cancels(self, monkeypatch):
        _asks(monkeypatch, [None])

        assert hh._ask_otc_price("110020", "2026-07-01") is None


class TestAskInterrupt:
    @pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
    def test_interrupt_returns_none(self, monkeypatch, exc):
        """提示行收到 EOF / Ctrl+C → 返回 None（按「取消本笔」处理，不抛给面板）。"""
        monkeypatch.setattr(hh, "input_choice", lambda _p: (_ for _ in ()).throw(exc()))

        assert hh._ask("  提示: ") is None
