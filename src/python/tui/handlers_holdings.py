"""TUI 持仓录入面板（首页 ``[U] 持仓录入``）。

职责（交互外壳，业务语义全部在 :mod:`src.python.core.holdings_editor`）：
  - 二级菜单（编号为主入口、字母为别名）：``1``/``L`` 查看持仓、``2``/``P`` 录入买入、
    ``3``/``S`` 录入卖出、``4``/``W`` 保存到持仓文件、``5``/``U`` 撤销上一笔、``0`` 返回；
  - ``2`` / ``3`` 只把意图写进内存变更清单（``book.drafts``），文件 mtime 不变；
  - ``4`` 先逐笔回显「用户刚才改变的持仓信息」并列受影响账户条数，用户确认后才原子写回
    文件（写前留 ``.bak`` 备份、写前校验文件未被其他程序改动）；
  - 退出（``0`` / ``Esc``）时有未保存变更 → 二次确认，默认不丢弃（安全侧）。

场外净值取数走 :func:`src.python.fetcher.nav_lookup.resolve_nav_on_trade_date`（当日无
净值取之前最近净值日，并如实回显实际净值日期）；取不到则本笔标失败，允许手填或放弃。
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from src.python.core.ansi_colors import GREEN, RED, RESET, YELLOW
from src.python.core.code_utils import is_six_digit_code
from src.python.core.holdings_editor import (
    PRICE_KIND_EXCHANGE,
    PRICE_KIND_OTC,
    SIDE_BUY,
    SIDE_LABELS,
    SIDE_SELL,
    HoldingsBook,
    TradeIntent,
    load_book,
)
from src.python.core.logger import setup_logger
from src.python.tui.error_tail import emit_error
from src.python.tui.panel_runtime import NavState, PanelItem, panel_loop
from src.python.tui.prompt_text import panel_prompt
from src.python.tui.text_layout import group_heading, style_heading, terminal_columns, wrap_hanging, wrap_prompt
from src.python.tui.tui_handlers import print_error_with_hint, select_holdings_file
from src.python.tui.tui_keys import input_choice

logger = setup_logger()


@dataclass
class _Session:
    """面板会话态（草稿工作副本 + 文件基线 mtime）。

    Attributes:
        book:     内存工作副本（草稿在这里累积）
        mtime:    加载时的文件 mtime；保存前与它比对，防止覆盖他人的改动
    """

    book: HoldingsBook
    mtime: float


def run_holdings_entry_panel() -> None:
    """``[U]`` 面板主入口：选文件 → 载入内存副本 → 二级菜单循环。"""
    filepath = select_holdings_file()
    if not filepath:
        return
    try:
        session = _Session(book=load_book(filepath), mtime=os.path.getmtime(filepath))
    except Exception as e:  # 读取失败统一走提示通道，不进面板
        print_error_with_hint(e, "读取持仓文件失败")
        return

    print(f"  {GREEN}[OK]{RESET} 已载入 {os.path.basename(filepath)}：{session.book.total_rows()} 条持仓")
    items = _panel_items(session)
    while True:
        panel_loop(
            items,
            render=lambda nav: _render_frame(session, nav, items),
            prompt=panel_prompt("选择操作", example="2", default="查看持仓"),
            on_text=lambda text: _dispatch_alias(text, items),
            default_key="1",
        )
        if not session.book.drafts:
            return
        if _exit_guard(session):
            return


#: 二级菜单键位：编号为主入口，字母为别名（数字先行、字母快路）。
_ALIAS_BY_KEY: dict[str, str] = {"1": "L", "2": "P", "3": "S", "4": "W", "5": "U"}


def _panel_items(session: _Session) -> list[PanelItem]:
    """二级菜单项（键位与录入规则的事实位在设计文件「持仓录入」篇）。"""
    return [
        PanelItem(
            "1",
            "查看持仓（含未保存变更）",
            detail="按账户分行展示当前持仓；本次未保存的行标红 *（字母别名 L）",
            action=lambda: _list_positions(session.book),
        ),
        PanelItem(
            "2",
            "录入买入",
            detail="选账户 → 选/输标的 → 份额或金额、价格、交易日；只进内存变更（字母别名 P）",
            action=lambda: _record(session, SIDE_BUY),
        ),
        PanelItem(
            "3",
            "录入卖出",
            detail="选账户 → 选标的 → 份额、价格、交易日；只进内存变更（字母别名 S）",
            action=lambda: _record(session, SIDE_SELL),
        ),
        PanelItem(
            "4",
            "保存到持仓文件",
            detail="回显本次全部变更并确认后写入持仓文件（字母别名 W）",
            action=lambda: _save(session),
        ),
        PanelItem(
            "5",
            "撤销上一笔",
            detail="撤回本次最后一笔录入（不写文件、可重复执行；字母别名 U）",
            action=lambda: _undo_last(session),
        ),
        PanelItem("0", "返回主菜单", kind="return", detail="有未保存变更时会先问「保存 / 丢弃 / 继续」"),
    ]


def _dispatch_alias(text: str, items: list[PanelItem]) -> None:
    """字母别名派发（编号由 ``panel_loop`` 直达；未命中的文本在此反馈）。"""
    token = text.strip().upper()
    for key, letter in _ALIAS_BY_KEY.items():
        if token == letter:
            item = next((it for it in items if it.key == key), None)
            if item is not None and item.action is not None:
                item.action()
            return
    print(f"  {YELLOW}[!]{RESET} 无效选择")


def _render_frame(session: _Session, nav: NavState, items: list[PanelItem]) -> list[str]:
    """面板帧：标题 + 文件与变更状态 + 可派发项（编号为主、字母括号内作别名）。"""
    columns = terminal_columns()
    lines = ["", *group_heading("持仓录入", columns)]
    lines += wrap_hanging(f"  文件：{os.path.basename(session.book.filepath)}", columns)
    if session.book.drafts:
        lines.append(f"  {YELLOW}[!]{RESET} {len(session.book.drafts)} 笔变更待保存（按 4 保存才写入文件）")
    else:
        lines.append("  当前无未保存变更")
    for index, item in enumerate(items):
        alias = _ALIAS_BY_KEY.get(item.key)
        label = f"[{alias}] {item.label}" if alias else item.label
        lines.append(f"  {nav.marker(index)} {item.key}. {label}")
    lines.append("")
    return lines


# ── L：列出当前持仓 ────────────────────────────────────────


def _list_positions(book: HoldingsBook) -> None:
    """按账户分块展示当前持仓：已保存与本次未保存分开标注（未保存行首标红 ``*``）。"""
    columns = terminal_columns()
    if book.total_rows() == 0:
        print(f"  {YELLOW}[!]{RESET} 当前没有持仓记录，可用 2 录入买入")
        return
    dirty_accounts = book.dirty_accounts()
    for account, rows in book.accounts.items():
        print()
        mark = f" {RED}*{RESET}" if account in dirty_accounts else ""
        print(style_heading(f"  ── {account}（{len(rows)} 条）{mark}──"))
        if not rows:
            print("    （空账户）")
            continue
        print("    名称（代码）")
        for row in rows:
            star = f"{RED}*{RESET} " if book.is_dirty(account, row.code) else "  "
            lines = wrap_hanging(f"    {star}{row.name}（{row.code}）", columns, indent="      ")
            print("\n".join(lines))
            print(f"      份额 {row.shares:g} · 每份成本 {row.cost_price:g}")
    if dirty_accounts:
        print()
        print(f"    {RED}*{RESET} = 本次录入、尚未保存（按 4 保存后才写入文件）")


# ── P / B：录入一笔买卖（只进草稿）─────────────────────────


def _record(session: _Session, side: str) -> None:
    """录入一笔买卖意图并应用到内存草稿；任一步取消都不改任何状态。"""
    book = session.book
    label = SIDE_LABELS[side]
    account = _pick_account(book)
    if account is None:
        print("  [!] 已取消本笔录入")
        return
    picked = _pick_asset(book, account, side)
    if picked is None:
        print("  [!] 已取消本笔录入")
        return
    name, code = picked

    kind = _resolve_price_kind(code, name)
    if kind is None:
        print("  [!] 已取消本笔录入")
        return
    fields = _collect_trade_fields(name, code, side, kind, book, account)
    if fields is None:
        print("  [!] 已取消本笔录入")
        return
    shares, price, trade_date, extra_lines, reference = fields

    if not _price_sanity(name, price, reference):
        print("  [!] 已取消本笔录入")
        return
    if _find_duplicate(book, account, code, side, shares, price, trade_date) is not None:
        print(f"  {YELLOW}[!]{RESET} 已有一笔完全相同的录入（同账户/代码/方向/份额/价格/交易日）")
        if not _confirm("确实要再录一笔？"):
            print("  [!] 已取消本笔录入")
            return

    _print_intent_summary(account, name, code, side, shares, price, trade_date, extra_lines)
    if not _confirm("确认加入本次变更？"):
        print("  [!] 已取消本笔录入")
        return
    try:
        book.apply(
            TradeIntent(
                account=account,
                name=name,
                code=code,
                side=side,
                shares=shares,
                price=price,
                trade_date=trade_date,
            )
        )
    except ValueError as e:
        print(f"  {RED}[ERR]{RESET} {e}")
        return
    print(f"  {GREEN}[OK]{RESET} {label}已加入草稿（{len(book.drafts)} 笔待保存，按 S 保存才写入文件）")


def _pick_account(book: HoldingsBook) -> str | None:
    """选账户：编号选已有账户，直接输入名称则新建账户。"""
    names = book.account_names
    print()
    print(style_heading("  ── 选择账户 ──"))
    for index, name in enumerate(names, 1):
        print(f"    {index}. {name}")
    if not names:
        print("    （暂无账户，输入新账户名即可新建）")
    raw = _ask("  回车=取消本笔 · 账户编号（如 1），或直接输入新账户名 · 0 返回: ")
    if raw is None or raw == "0":
        return None
    token = raw.strip()
    if not token:
        return None
    if token.isdigit():
        index = int(token)
        if 1 <= index <= len(names):
            return names[index - 1]
        print(f"  {YELLOW}[!]{RESET} 无效编号")
        return None
    if any(sep in token for sep in ("/", "\\")):
        print(f"  {RED}[ERR]{RESET} 账户名不能包含路径分隔符")
        return None
    return token


def _pick_asset(book: HoldingsBook, account: str, side: str) -> tuple[str, str] | None:
    """选标的：编号选账户内已有持仓，``N`` 输入新代码。"""
    rows = book.rows(account)
    print()
    print(style_heading(f"  ── {account}：选择证券/基金 ──"))
    for index, row in enumerate(rows, 1):
        print(f"    {index}. {row.name}（{row.code}）份额 {row.shares:g}")
    if side == SIDE_SELL and not rows:
        print(f"  {YELLOW}[!]{RESET} 该账户没有可卖出的持仓")
        return None
    print("    N. 输入新代码（当前未持有的证券/基金）")
    raw = _ask("  回车=取消本笔 · 编号或 N（如 1）· 0 返回: ")
    if raw is None or raw == "0":
        return None
    token = raw.strip()
    if not token:
        return None
    if token.upper() == "N":
        if side == SIDE_SELL:
            print(f"  {YELLOW}[!]{RESET} 卖出只能选择已有持仓")
            return None
        return _input_new_asset()
    if token.isdigit():
        index = int(token)
        if 1 <= index <= len(rows):
            return rows[index - 1].name, rows[index - 1].code
    print(f"  {YELLOW}[!]{RESET} 无效选择")
    return None


def _input_new_asset() -> tuple[str, str] | None:
    """录入新代码（名称可自动带出，取不到再手输）。"""
    raw = _ask("  回车=取消本笔 · 证券代码（如 007301）· 0 返回: ")
    if raw is None or raw == "0":
        return None
    code = raw.strip()
    if not is_six_digit_code(code):
        print(f"  {RED}[ERR]{RESET} 代码应为 6 位数字: {code}")
        return None
    name = _resolve_name(code)
    if not name:
        typed = _ask("  回车=取消本笔 · 证券名称（如 华夏成长）· 0 返回: ")
        if typed is None or typed == "0" or not typed.strip():
            return None
        name = typed.strip()
    print(f"  {GREEN}[OK]{RESET} {name}（{code}）")
    return name, code


def _market_data(code: str) -> dict | None:
    """取该代码的行情/净值数据（失败返回 None，不阻断录入）。"""
    try:
        from src.python.fetcher.price import fetch_market_data

        return fetch_market_data(code)
    except Exception:  # 取数失败不阻断录入
        logger.warning("[持仓录入] 行情取数异常: %s", code, exc_info=True)
        return None


def _resolve_name(code: str) -> str:
    """按代码取名称（行情链路，失败返回空串由调用方手输）。"""
    return str((_market_data(code) or {}).get("name") or "").strip()


def _collect_trade_fields(
    name: str, code: str, side: str, kind: str, book: HoldingsBook, account: str
) -> tuple[float, float, str, list[str], float] | None:
    """收集一笔的份额 / 价格 / 交易日 / 系统参考价（``None`` = 取消或本笔不成立）。

    参考价 = 系统自己取到的行情或官方净值（未取到时为 0），供价格量级校验复用，
    不额外发起取数。

    场外**买入**额外区分两种录入口径（关键校验，见 :func:`_collect_otc_buy`）：
    交易日当天只能给申购金额（份额要等当日净值公布后才有），按份额录入只在该交易日
    净值已可用时成立。
    """
    if kind == PRICE_KIND_OTC and side == SIDE_BUY:
        return _collect_otc_buy(code, name)
    shares = _ask_shares(SIDE_LABELS[side], _held_shares(book, account, code, side))
    if shares is None:
        return None
    trade_date = _ask_trade_date()
    if trade_date is None:
        return None
    priced = _ask_price(code, name, kind, trade_date)
    if priced is None:
        return None
    price, reference = priced
    return shares, price, trade_date, [], reference


def _collect_otc_buy(code: str, name: str) -> tuple[float, float, str, list[str], float] | None:
    """场外买入：按金额（当日）或按份额（净值已公布后才成立）。

    按金额：份额 = 金额 / 该交易日官方净值；净值未公布（或该日无净值）时无法换算，
    本笔**不予成立**并提示稍后录入——绝不先按估算净值写进持仓文件。
    按份额：同样要求该交易日净值已可用（作为每份成本），取不到才允许手填价格。
    """
    mode = _ask_entry_mode()
    if mode is None:
        return None
    trade_date = _ask_trade_date()
    if trade_date is None:
        return None

    if mode == "amount":
        amount = _ask_amount()
        if amount is None:
            return None
        from src.python.fetcher.nav_lookup import resolve_purchase_shares

        print("  [..] 正在查询净值...")
        result = resolve_purchase_shares(code, trade_date, amount)
        if result is None:
            print(f"  {YELLOW}[!]{RESET} 该交易日净值尚未公布（或为非交易日），无法把金额换算成份额")
            print("     请于净值公布后再录入本笔（亦可改选按份额录入）")
            return None
        extra = [f"  金额  : {amount:g} 元", f"  净值  : {result['nav']:g}（{result['nav_date']}）"]
        if not result["exact_date"]:
            extra.append(f"  说明  : {trade_date} 无净值，按 {result['nav_date']} 净值折算")
        nav = float(result["nav"])
        return float(result["shares"]), nav, trade_date, extra, nav

    shares = _ask_shares("买入", None)
    if shares is None:
        return None
    priced = _ask_otc_price(code, trade_date)
    if priced is None:
        return None
    price, reference = priced
    return shares, price, trade_date, [], reference


def _ask_entry_mode() -> str | None:
    """场外买入录入口径（``amount`` = 按金额，``shares`` = 按份额）。"""
    raw = _ask("  回车=按金额 · 录入方式（1=按金额 / 2=按份额）· 0 返回: ")
    if raw is None or raw == "0" or not raw.strip():
        return "amount"
    token = raw.strip()
    if token == "1":
        return "amount"
    if token == "2":
        return "shares"
    print(f"  {YELLOW}[!]{RESET} 无效选择")
    return None


def _ask_amount() -> float | None:
    """申购金额（元）。"""
    raw = _ask("  回车=取消本笔 · 申购金额（元，如 1000）· 0 返回: ")
    if raw is None or raw == "0" or not raw.strip():
        return None
    try:
        amount = float(raw.strip())
    except ValueError:
        print(f"  {RED}[ERR]{RESET} 金额应为数字: {raw.strip()}")
        return None
    if amount <= 0:
        print(f"  {RED}[ERR]{RESET} 金额必须大于 0")
        return None
    return amount


def _ask_shares(label: str, available: float | None = None) -> float | None:
    """录入份额（卖出时 ``a`` = 该持仓全部份额）。

    Args:
        label: 方向中文（买入 / 卖出），用于提示。
        available: 当前持有份额（卖出时非 None，供 ``a`` 换算）。
    """
    raw = _ask(f"  回车=取消本笔 · {label}份额（如 100，a=全部）· 0 返回: ")
    if raw is None or raw == "0" or not raw.strip():
        return None
    token = raw.strip()
    if token.lower() == "a":
        if available is None or available <= 0:
            print(f"  {YELLOW}[!]{RESET} 该持仓没有可卖出的份额")
            return None
        return available
    try:
        shares = float(token)
    except ValueError:
        print(f"  {RED}[ERR]{RESET} 份额应为数字: {token}")
        return None
    if shares <= 0:
        print(f"  {RED}[ERR]{RESET} 份额必须大于 0")
        return None
    return shares


def _held_shares(book: HoldingsBook, account: str, code: str, side: str) -> float | None:
    """该账户内某代码的当前持有份额（买入 / 无持仓时 None）。"""
    if side != SIDE_SELL:
        return None
    for row in book.rows(account):
        if row.code == code:
            return float(row.shares)
    return None


_PRICE_DEVIATION_WARN = 0.2
"""价格与参考价偏离告警阈值：超过即要求二次确认（防小数点位错）。"""

_DUP_EPS = 1e-6
"""重复录入判定的浮点容差。"""


def _resolve_price_kind(code: str, name: str) -> str | None:
    """品种价格形态；00 重叠区先按行情源反推，仍不确定再问用户一次。

    Returns:
        ``PRICE_KIND_EXCHANGE`` / ``PRICE_KIND_OTC``；用户取消返回 ``None``。
    """
    from src.python.core.holdings_editor import resolve_entry_kind
    from src.python.fetcher.price import price_kind_from_quote

    try:
        return resolve_entry_kind(code, name)
    except ValueError:
        pass  # 00 重叠区：先按行情源反推，仍不确定再问用户
    hint = price_kind_from_quote(_market_data(code))
    if hint == PRICE_KIND_OTC:
        print("  [..] 行情源判定为场外基金（按交易日取官方净值）")
        return hint
    if hint == PRICE_KIND_EXCHANGE:
        print("  [..] 行情源判定为场内证券（须录成交价）")
        return hint
    raw = _ask("  回车=按场内证券处理 · 品种属性（1=场内证券 2=场外基金）· 0 返回: ")
    if raw is None or raw == "0":
        return None
    token = (raw or "").strip()
    if token in ("", "1"):
        return PRICE_KIND_EXCHANGE
    if token == "2":
        return PRICE_KIND_OTC
    print(f"  {YELLOW}[!]{RESET} 无效选择")
    return None


def _price_sanity(name: str, price: float, reference: float) -> bool:
    """价格量级校验：与系统取到的参考价（行情/净值）偏离超过阈值时要求确认。

    Args:
        name: 标的名称（提示用）。
        price: 用户录入的价格。
        reference: 系统参考价（0 = 无参照，跳过校验）。

    Returns:
        True 表示继续；False 表示放弃本笔。
    """
    if reference <= 0:
        return True
    deviation = abs(price - reference) / reference
    if deviation <= _PRICE_DEVIATION_WARN:
        return True
    print(
        f"  {YELLOW}[!]{RESET} 价格 {price:g} 与参考价 {reference:g} 相差 {deviation * 100:.0f}%（{name}）"
        "——像小数点位置错？"
    )
    return _confirm("确认价格无误？")


def _nav_reference(code: str, trade_date: str) -> float:
    """手填场外价格时的参考净值（取不到返回 0，不阻断录入）。"""
    from src.python.fetcher.nav_lookup import resolve_nav_on_trade_date

    result = resolve_nav_on_trade_date(code, trade_date)
    return float(result["nav"]) if result else 0.0


def _find_duplicate(
    book: HoldingsBook, account: str, code: str, side: str, shares: float, price: float, trade_date: str
) -> TradeIntent | None:
    """本次变更里是否存在完全相同的录入（连按两次回车这类误操作防线）。"""
    from src.python.core.code_symbols import strip_to_digits

    target = strip_to_digits(code)
    for intent in book.drafts:
        if (
            intent.account.strip() == account.strip()
            and strip_to_digits(intent.code) == target
            and intent.side == side
            and abs(intent.shares - shares) <= _DUP_EPS
            and abs(intent.price - price) <= _DUP_EPS
            and intent.trade_date == trade_date
        ):
            return intent
    return None


def _undo_last(session: _Session) -> None:
    """撤销本次最后一笔录入（从文件重放剩余变更，不写文件）。"""
    reverted = session.book.revert_last()
    if reverted is None:
        print(f"  {YELLOW}[!]{RESET} 没有可撤销的录入（本次尚无变更）")
        return
    print(
        f"  {GREEN}[OK]{RESET} 已撤销：{reverted.action_label} {reverted.name}（{reverted.code}）"
        f"份额 {reverted.shares:g}"
    )
    print(f"     剩余 {len(session.book.drafts)} 笔待保存")


def _ask_trade_date() -> str | None:
    """录入交易日（回车 = 今天）。"""
    from datetime import date

    from src.python.fetcher.nav_lookup import normalize_trade_date

    raw = _ask("  回车=今天 · 交易日（如 2026-07-01）· 0 返回: ")
    if raw is None or raw == "0":
        return None
    if not raw.strip():
        return date.today().isoformat()
    try:
        return normalize_trade_date(raw)
    except ValueError as e:
        print(f"  {RED}[ERR]{RESET} {e}")
        return None


def _ask_price(code: str, name: str, kind: str, trade_date: str) -> tuple[float, float] | None:
    """录入成交价，返回 ``(价格, 系统参考价)``。

    场内必填（回车取当前行情），场外可空（按交易日取净值）；参考价用于价格量级校验，
    用户手填时为 0（无系统参照）。
    """
    if kind == PRICE_KIND_EXCHANGE:
        return _ask_exchange_price(code, name)
    return _ask_otc_price(code, trade_date)


def _ask_exchange_price(code: str, name: str) -> tuple[float, float] | None:
    """场内成交价（回车取当前行情，取不到再手输）。"""
    raw = _ask("  回车=取当前行情 · 成交价（如 1.234）· 0 返回: ")
    if raw is None or raw == "0":
        return None
    if raw.strip():
        price = _parse_price(raw)
        return None if price is None else (price, _resolve_quote(code))
    quote = _resolve_quote(code)
    if quote:
        print(f"  {GREEN}[OK]{RESET} 当前行情 {quote:g}（{name}）")
        return quote, quote
    print(f"  {YELLOW}[!]{RESET} 未取到当前行情，请手填成交价")
    typed = _ask("  回车=放弃本笔 · 成交价（如 1.234）· 0 返回: ")
    if typed is None or typed == "0" or not typed.strip():
        return None
    price = _parse_price(typed)
    return None if price is None else (price, 0.0)


def _ask_otc_price(code: str, trade_date: str) -> tuple[float, float] | None:
    """场外价格：可手填；留空则按交易日取官方净值（取不到允许手填或放弃）。"""
    raw = _ask("  回车=按交易日取官方净值 · 价格（可选，如 1.2345）· 0 返回: ")
    if raw is None or raw == "0":
        return None
    reference = _nav_reference(code, trade_date) if raw.strip() else 0.0
    if raw.strip():
        price = _parse_price(raw)
        return None if price is None else (price, reference)
    from src.python.fetcher.nav_lookup import resolve_nav_on_trade_date

    print("  [..] 正在查询净值...")
    result = resolve_nav_on_trade_date(code, trade_date)
    if result is None:
        print(f"  {YELLOW}[!]{RESET} 本笔标失败：取不到 {trade_date} 的官方净值")
        typed = _ask("  回车=放弃本笔 · 手填价格（如 1.2345）· 0 返回: ")
        if typed is None or typed == "0" or not typed.strip():
            return None
        price = _parse_price(typed)
        return None if price is None else (price, 0.0)
    nav_date = result["nav_date"]
    if result["exact_date"]:
        print(f"  {GREEN}[OK]{RESET} {nav_date} 官方净值 {result['nav']:g}")
    else:
        print(f"  {YELLOW}[!]{RESET} {trade_date} 无净值，采用 {nav_date} 净值 {result['nav']:g}")
        if not _confirm("按该净值继续？"):
            return None
    nav = float(result["nav"])
    return nav, nav


def _parse_price(raw: str) -> float | None:
    """价格文本 → 正浮点数（非法给错误提示并返回 None）。"""
    try:
        price = float(raw.strip())
    except ValueError:
        print(f"  {RED}[ERR]{RESET} 价格应为数字: {raw.strip()}")
        return None
    if price <= 0:
        print(f"  {RED}[ERR]{RESET} 价格必须大于 0")
        return None
    return price


def _resolve_quote(code: str) -> float:
    """取当前行情价（失败返回 0，由调用方转手输）。"""
    try:
        return float((_market_data(code) or {}).get("price") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _print_intent_summary(
    account: str,
    name: str,
    code: str,
    side: str,
    shares: float,
    price: float,
    trade_date: str,
    extra_lines: list[str] | None = None,
) -> None:
    """单笔回显（录入确认用）。"""
    columns = terminal_columns()
    print()
    print(style_heading("  ── 本笔内容 ──"))
    rows = [
        f"  账户  : {account}",
        f"  方向  : {SIDE_LABELS[side]}",
        f"  标的  : {name}（{code}）",
        *(extra_lines or []),
        f"  份额  : {shares:g}",
        f"  价格  : {price:g}",
        f"  交易日: {trade_date}",
    ]
    for row in rows:
        print("\n".join(wrap_hanging(row, columns)))


# ── S：回显变更 → 确认 → 写回 ──────────────────────────────


def _save(session: _Session) -> None:
    """回显本次全部变更，确认后原子写回持仓文件。"""
    book = session.book
    if not book.drafts:
        print(f"  {YELLOW}[!]{RESET} 没有待保存的变更，先用 P 买入或 B 卖出录入")
        return
    if not _file_unchanged(session):
        return
    _print_draft_summary(book)
    append_flows = _confirm("是否同时记入「交易流水」页签？")
    if not _confirm("确认写入持仓文件？"):
        print("  [!] 已取消保存，草稿保留")
        return
    backup = _backup_file(book.filepath)
    try:
        book.save(append_flows=append_flows)
    except (ValueError, OSError) as e:
        emit_error(str(e), "config", advice=f"草稿保留，可修正后重试（备份: {backup or '无'}）")
        return
    session.mtime = os.path.getmtime(book.filepath)
    print(f"  {GREEN}[OK]{RESET} 已写入并回读校验通过：{os.path.basename(book.filepath)}")
    if backup:
        print(f"     原文件备份: {os.path.basename(backup)}")


def _print_draft_summary(book: HoldingsBook) -> None:
    """逐笔回显草稿 + 受影响账户的持仓行数变化（用户确认的对象）。"""
    columns = terminal_columns()
    print()
    print(style_heading(f"  ── 本次待保存变更（{len(book.drafts)} 笔）──"))
    for index, intent in enumerate(book.drafts, 1):
        head = f"  {index}. {intent.action_label} {intent.name}（{intent.code}）"
        print("\n".join(wrap_hanging(head, columns)))
        detail = (
            f"     份额 {intent.shares:g} · 价格 {intent.price:g} · 交易日 {intent.trade_date} · 账户 {intent.account}"
        )
        print("\n".join(wrap_hanging(detail, columns, indent="         ")))
    accounts = sorted({intent.account for intent in book.drafts})
    for account in accounts:
        print(f"  账户「{account}」保存后共 {len(book.rows(account))} 条持仓")


def _file_unchanged(session: _Session) -> bool:
    """保存前校验文件自载入以来未被其他程序改动（防覆盖他人的手改）。"""
    try:
        current = os.path.getmtime(session.book.filepath)
    except OSError as e:
        emit_error(f"持仓文件不可访问: {e}", "config")
        return False
    if abs(current - session.mtime) > 1e-6:
        emit_error("持仓文件已被其他程序修改", "config", advice="请返回后重新载入，避免覆盖改动")
        return False
    return True


def _backup_file(filepath: str) -> str:
    """写回前留同目录 ``.bak`` 副本（失败不阻断，返回空串）。"""
    backup = f"{filepath}.bak"
    try:
        shutil.copy2(filepath, backup)
    except OSError:
        logger.warning("[持仓录入] 备份失败: %s", filepath, exc_info=True)
        return ""
    return backup


# ── 通用交互 ──────────────────────────────────────────────


def _ask(prompt: str) -> str | None:
    """单行输入（Esc 取消返回 None）。"""
    try:
        return input_choice(wrap_prompt(prompt))
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _confirm(question: str) -> bool:
    """``(y/N)`` 确认（默认否，安全侧）。"""
    raw = _ask(wrap_prompt(f"  {question} (y/N): "))
    return bool(raw) and raw.strip().lower() in ("y", "yes", "是")


def _exit_guard(session: _Session) -> bool:
    """有未保存变更时的退出守卫（保存后退出 / 丢弃退出 / 继续编辑）。

    Returns:
        True 表示确实退出面板；False 表示留在面板继续编辑。
    """
    count = len(session.book.drafts)
    raw = _ask(f"  回车=继续编辑 · {count} 笔变更未保存：1=保存后退出 / 2=丢弃退出 · 0 返回: ")
    if raw is None:
        return False
    token = raw.strip()
    if not token or token == "0":
        return False
    if token == "1":
        _save(session)
        return not session.book.drafts  # 保存成功（变更清空）才退出
    if token == "2":
        return True
    print(f"  {YELLOW}[!]{RESET} 无效选择")
    return False
