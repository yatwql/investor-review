# -*- coding: utf-8 -*-
"""TUI 持仓录入面板（tui/handlers_holdings.py）单元测试。

钉住三条硬约束：P/B 只进草稿不动文件、S 必须确认后才写、场外买入按金额录入时
净值未公布不得成立（份额要等官方净值）。网络取数全部 mock（名称/行情/净值）。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.python.core.holdings_editor import SIDE_BUY, TradeIntent, load_book
from src.test._holdings_fixture import make_holdings_file
from src.python.tui import handlers_holdings as hh

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


def _ui_file(tmp_path: Path) -> Path:
    """面板用例基线：一个 A 股账户 + 一个场外基金账户，无流水页签。"""
    return make_holdings_file(
        tmp_path,
        stock_rows=[["长江电力", "600900", 1000, 20.0]],
        fund_rows=[["易方达蓝筹精选混合", "005827", 200, 2.0]],
        with_flow_sheet=False,
    )


@pytest.fixture
def feed(monkeypatch: pytest.MonkeyPatch):
    """把面板输入替换为预设答案序列（用尽后按 Esc 处理）。"""

    def _feed(*answers: str) -> None:
        answers_iter = iter(answers)

        def _fake(_prompt, **_kwargs):
            try:
                return next(answers_iter)
            except StopIteration as exc:
                raise EOFError from exc

        monkeypatch.setattr(hh, "input_choice", _fake)

    return _feed


def test_buy_new_exchange_asset_enters_draft_without_touching_file(
    tmp_path: Path, feed, monkeypatch: pytest.MonkeyPatch
):
    path = _ui_file(tmp_path)
    before = path.read_bytes()
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path))
    monkeypatch.setattr(
        "src.python.fetcher.price.fetch_market_data",
        lambda code, expected_name="": {"name": "贵州茅台", "code": code, "price": 1700.0},
    )
    feed("1", "N", "600519", "10", "2026-07-01", "", "y")

    hh._record(session, SIDE_BUY)

    assert len(session.book.drafts) == 1
    draft = session.book.drafts[0]
    assert (draft.name, draft.code, draft.shares, draft.price) == ("贵州茅台", "600519", 10.0, 1700.0)
    assert path.read_bytes() == before


def test_otc_buy_by_amount_derives_shares_from_nav(tmp_path: Path, feed, monkeypatch: pytest.MonkeyPatch):
    path = _ui_file(tmp_path)
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path))
    monkeypatch.setattr(
        "src.python.fetcher.nav_lookup.resolve_purchase_shares",
        lambda code, trade_date, amount: {
            "shares": amount / 1.25,
            "nav": 1.25,
            "nav_date": "2026-07-01",
            "exact_date": True,
        },
    )
    feed("2", "1", "", "2026-07-01", "1000", "y")

    hh._record(session, SIDE_BUY)

    assert len(session.book.drafts) == 1
    draft = session.book.drafts[0]
    assert draft.shares == pytest.approx(800.0)
    assert draft.price == pytest.approx(1.25)


def test_otc_buy_by_amount_rejected_when_nav_not_published(
    tmp_path: Path, feed, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    path = _ui_file(tmp_path)
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path))
    monkeypatch.setattr("src.python.fetcher.nav_lookup.resolve_purchase_shares", lambda *a, **k: None)
    feed("2", "1", "", "2026-07-01", "1000")

    hh._record(session, SIDE_BUY)

    assert session.book.drafts == []
    assert "尚未公布" in capsys.readouterr().out


def test_save_refuses_when_file_modified_after_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    path = _ui_file(tmp_path)
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path) - 5)
    session.book.apply(
        TradeIntent(
            account="股票账户",
            name="长江电力",
            code="600900",
            side=SIDE_BUY,
            shares=100,
            price=21.0,
            trade_date="2026-07-01",
        )
    )
    before = path.read_bytes()

    hh._save(session)

    assert path.read_bytes() == before
    assert len(session.book.drafts) == 1
    assert "已被其他程序修改" in capsys.readouterr().out


def test_save_writes_only_after_confirmation(tmp_path: Path, feed, capsys: pytest.CaptureFixture[str]):
    path = _ui_file(tmp_path)
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path))
    session.book.apply(
        TradeIntent(
            account="股票账户",
            name="长江电力",
            code="600900",
            side=SIDE_BUY,
            shares=100,
            price=21.0,
            trade_date="2026-07-01",
        )
    )
    before = path.read_bytes()
    feed("n", "n")  # 不记流水、不确认写入

    hh._save(session)

    assert path.read_bytes() == before
    assert len(session.book.drafts) == 1
    out = capsys.readouterr().out
    assert "本次待保存变更（1 笔）" in out
    assert "已取消保存" in out

    feed("", "y")  # 默认不记流水、确认写入
    hh._save(session)

    assert session.book.drafts == []
    assert path.read_bytes() != before


def test_list_positions_marks_unsaved_rows_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """查看持仓：本次未保存的行标 ``*`` 并给图例，已保存的行不标。"""
    path = _ui_file(tmp_path)
    book = load_book(str(path))
    book.apply(
        TradeIntent(
            account="股票账户",
            name="长江电力",
            code="600900",
            side=SIDE_BUY,
            shares=100,
            price=21.0,
            trade_date="2026-07-01",
        )
    )

    hh._list_positions(book)

    out = capsys.readouterr().out
    dirty_lines = [line for line in out.splitlines() if "长江电力" in line]
    clean_lines = [line for line in out.splitlines() if "易方达蓝筹精选混合" in line]
    assert dirty_lines and all("*" in line for line in dirty_lines)
    assert clean_lines and all("*" not in line for line in clean_lines)
    assert "尚未保存" in out


def test_panel_items_use_numbers_with_letter_aliases(tmp_path: Path):
    """二级菜单编号为主入口、字母作别名；卖出用 S（Sell）而非 B（Bid 是买方出价）。"""
    session = hh._Session(book=load_book(str(_ui_file(tmp_path))), mtime=0.0)
    items = hh._panel_items(session)

    assert [item.key for item in items] == ["1", "2", "3", "4", "5", "0"]
    assert hh._ALIAS_BY_KEY == {"1": "L", "2": "P", "3": "S", "4": "W", "5": "U"}
    assert "B" not in hh._ALIAS_BY_KEY.values()
    labels = {item.key: item.label for item in items}
    assert labels["1"].startswith("查看持仓")
    assert labels["4"] == "保存到持仓文件"
    assert items[-1].kind == "return"


def test_letter_alias_dispatches_same_action():
    """字母别名与编号派发同一动作（快路不改变语义）。"""
    called: list[str] = []
    items = [
        hh.PanelItem(str(number), f"动作 {number}", action=lambda key=str(number): called.append(key))
        for number in (1, 2, 3, 4)
    ]

    hh._dispatch_alias("l", items)
    hh._dispatch_alias("W", items)

    assert called == ["1", "4"]


def test_unknown_text_gives_invalid_feedback(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    session = hh._Session(book=load_book(str(_ui_file(tmp_path))), mtime=0.0)
    hh._dispatch_alias("Z", hh._panel_items(session))
    assert "无效选择" in capsys.readouterr().out


def test_confirm_defaults_to_safe_side(feed):
    feed("")
    assert hh._confirm("确认写入持仓文件？") is False


def test_ask_shares_accepts_all_shorthand(feed):
    feed("a")
    assert hh._ask_shares("卖出", 500.0) == pytest.approx(500.0)


def test_ask_shares_rejects_all_without_holdings(feed):
    feed("a")
    assert hh._ask_shares("卖出", None) is None


# ── 歧义判定 / 重复提交 / 价格量级 / 撤销 / 退出守卫 ─────────────


def test_ambiguous_00_code_inferred_from_quote_source(monkeypatch: pytest.MonkeyPatch):
    """00 重叠区先按行情源反推：命中场外净值源即场外，命中行情源即场内。"""
    monkeypatch.setattr(hh, "_market_data", lambda code: {"source_api": "eastmoney"})
    assert hh._resolve_price_kind("005827", "易方达蓝筹") == hh.PRICE_KIND_OTC
    monkeypatch.setattr(hh, "_market_data", lambda code: {"source_api": "tencent"})
    assert hh._resolve_price_kind("000001", "平安银行") == hh.PRICE_KIND_EXCHANGE


def test_ambiguous_00_code_asks_when_quote_missing(feed, monkeypatch: pytest.MonkeyPatch):
    """取不到行情时向用户确认一次；选 2 即场外，回车即场内，0 取消。"""
    monkeypatch.setattr(hh, "_market_data", lambda code: None)
    feed("2")
    assert hh._resolve_price_kind("005827", "易方达蓝筹") == hh.PRICE_KIND_OTC
    feed("")
    assert hh._resolve_price_kind("000001", "平安银行") == hh.PRICE_KIND_EXCHANGE
    feed("0")
    assert hh._resolve_price_kind("000001", "平安银行") is None


def test_non_ambiguous_code_never_asks(feed):
    """非歧义代码（56 开头场内基金 / 名称含基金词）不问，直接判定。"""
    assert hh._resolve_price_kind("510300", "沪深300ETF") == hh.PRICE_KIND_EXCHANGE
    assert hh._resolve_price_kind("007301", "华夏成长混合") == hh.PRICE_KIND_OTC


def test_price_deviation_requires_confirmation(feed):
    """价格与参考价偏离超阈值要二次确认；阈值内不打扰。"""
    feed("n")
    assert hh._price_sanity("长江电力", 12.34, 1.23) is False
    feed("y")
    assert hh._price_sanity("长江电力", 12.34, 1.23) is True
    assert hh._price_sanity("长江电力", 1.25, 1.23) is True
    assert hh._price_sanity("长江电力", 1.25, 0.0) is True  # 无参照直接放行


def test_duplicate_entry_needs_explicit_confirmation(tmp_path: Path, feed, monkeypatch: pytest.MonkeyPatch):
    """连录两笔完全相同 → 第二次必须显式确认，拒绝则不新增。"""
    path = _ui_file(tmp_path)
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path))
    monkeypatch.setattr(
        "src.python.fetcher.price.fetch_market_data",
        lambda code, expected_name="": {"name": "贵州茅台", "code": code, "price": 1700.0},
    )
    answers = ("1", "N", "600519", "10", "2026-07-01", "", "y")

    feed(*answers)
    hh._record(session, SIDE_BUY)
    assert len(session.book.drafts) == 1

    feed(*answers, "n")  # 最后一位是「重复确认」的答复
    hh._record(session, SIDE_BUY)
    assert len(session.book.drafts) == 1


def test_undo_last_removes_entry_and_restores_book(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """撤销上一笔：回到上一笔之前的状态（以文件为基线重放剩余变更）。"""
    path = _ui_file(tmp_path)
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path))
    original = session.book.rows("股票账户")[0].shares
    session.book.apply(
        TradeIntent(
            account="股票账户",
            name="长江电力",
            code="600900",
            side=SIDE_BUY,
            shares=100,
            price=21.0,
            trade_date="2026-07-01",
        )
    )
    session.book.apply(
        TradeIntent(
            account="股票账户",
            name="长江电力",
            code="600900",
            side=SIDE_BUY,
            shares=200,
            price=22.0,
            trade_date="2026-07-02",
        )
    )

    hh._undo_last(session)

    assert len(session.book.drafts) == 1
    assert session.book.rows("股票账户")[0].shares == pytest.approx(original + 100)
    assert "已撤销" in capsys.readouterr().out

    hh._undo_last(session)
    hh._undo_last(session)
    assert session.book.rows("股票账户")[0].shares == pytest.approx(original)
    assert "没有可撤销" in capsys.readouterr().out


def test_exit_guard_offers_three_ways(tmp_path: Path, feed, monkeypatch: pytest.MonkeyPatch):
    """退出守卫：回车=继续编辑，2=丢弃退出，1=保存后退出（保存成功才退出）。"""
    path = _ui_file(tmp_path)
    session = hh._Session(book=load_book(str(path)), mtime=os.path.getmtime(path))
    session.book.apply(
        TradeIntent(
            account="股票账户",
            name="长江电力",
            code="600900",
            side=SIDE_BUY,
            shares=100,
            price=21.0,
            trade_date="2026-07-01",
        )
    )

    feed("")
    assert hh._exit_guard(session) is False
    feed("2")
    assert hh._exit_guard(session) is True

    feed("1", "n", "y")  # 1=保存后退出：不记流水、确认写入
    assert hh._exit_guard(session) is True
    assert session.book.drafts == []
