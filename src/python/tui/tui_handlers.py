"""TUI 命令处理器模块 — 实用工具 + 菜单调度。

对应关系：报告生成 → handlers_report.py，缓存管理 → handlers_cache.py，
配置管理 → handlers_config.py。本文件保留：
  - 菜单执行调度（execute_item）
  - 通用辅助函数（_print_*、_check_*、prepare_holdings、select_holdings_file 等）
  - 持仓变更检测与缓存预热（委托 cache.operations.warm_new_asset_caches）
"""

from __future__ import annotations

import os
import threading
from datetime import datetime

from src.python.core.num_utils import format_size
from src.python.llm.pricing import CURRENCY_SYMBOLS
from src.python.core.logger import setup_logger
from src.python.core.reader import get_xlsx_info, list_xlsx_files, read_holdings_with_flows, require_holdings
from src.python.report.progress import TuiProgressReporter
from src.python.tui.tui_keys import PromptCancelledError, input_choice
from src.python.tui.tui_menu import MENU_ITEMS, get_config_cache, refresh_config

logger = setup_logger()

_busy: bool = False  # 防连续按键保护
_busy_lock = threading.Lock()  # _busy 标志位锁保护


# ── LLM 用量 / 耗时 / 错误提示 ──────────────────────────────


def print_llm_session_usage(usage: dict | None = None) -> None:
    """输出会话累计 LLM 用量（TUI 终端一行）。"""
    if usage is None:
        try:
            from src.python.llm import get_session_usage

            usage = get_session_usage()
        except (ImportError, TypeError, AttributeError):
            logger.debug("获取 LLM 会话用量失败（非关键）")
            return
    if not usage or usage.get("call_count", 0) == 0:
        return
    calls = usage["call_count"]
    total_tok = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    cost = usage.get("total_cost", 0.0)
    symbol = CURRENCY_SYMBOLS.get(usage.get("currency", "CNY"), "¥")
    print(f"  [OK] 本会话 LLM 累计：{calls} 次调用，{total_tok:,} tokens，费用 {symbol}{cost:.4f}")


def print_timing_summary() -> None:
    """输出本次运行时各模块耗时排行（委托至 TuiProgressReporter）。"""
    from src.python.report.progress import timing_records

    reporter = TuiProgressReporter()
    reporter._timing_records.extend(timing_records)
    reporter.print_timing_summary()
    timing_records.clear()


def print_error_with_hint(e: Exception, prefix: str = "操作失败") -> None:
    """输出带友好提示的错误信息（映射单源于 `core.error_hints`，Web/CLI 取同一句）。"""
    from src.python.core.error_hints import hint_for

    hint = hint_for(e)
    msg = str(e)
    if hint.log_detail:
        logger.warning("%s: %s", prefix, msg, exc_info=True)
    print(f"  [ERR] {prefix}: {hint.message}")
    if hint.advice:
        print(f"        {hint.advice}")
    elif "网络" in hint.message and msg:
        # 网络类保留详情行，便于用户核对具体超时/断连；其余不暴露原始异常串
        print(f"        详情: {msg}")


# ── 持仓准备 / 收尾 ────────────────────────────────────────


def prepare_holdings() -> "tuple[list, list, list] | None":
    """选择持仓文件并读取持仓记录（含可选交易/分红流水页签）。失败时返回 None。

    Returns:
        (holdings, transactions, dividends) 三元组；无流水页签时流水列表为空。
    """
    refresh_config()
    filepath = select_holdings_file()
    if not filepath:
        return None
    try:
        print("  [..] 正在读取持仓数据...")
        parsed = read_holdings_with_flows(filepath)
        holdings = parsed.holdings
        try:
            require_holdings(holdings, filepath)
        except ValueError as e:
            print(f"  [ERR] {e}")
            return None
        print(f"  [OK] 成功读取 {len(holdings)} 条持仓记录")
        if parsed.transactions or parsed.dividends:
            print(f"     含交易流水 {len(parsed.transactions)} 条，分红流水 {len(parsed.dividends)} 条")
        from src.python.cache.operations import warm_new_asset_caches

        warm_new_asset_caches(holdings, TuiProgressReporter())
        return holdings, parsed.transactions, parsed.dividends
    except Exception as e:
        print_error_with_hint(e, "读取持仓失败")
        return None


def finish_report(reporter: TuiProgressReporter) -> None:
    """报告生成收尾：错误摘要 → 耗时排行 → 产物清单 + 是否打开（默认 N）。

    单键作答即返回菜单：长输出仍停在一屏（先读完再重绘），用户看完顺手按 y 打开、
    直接回车或按其它键则跳过——只按一次，不多一步。
    """
    reporter.print_error_summary()
    reporter.print_timing_summary()
    from src.python.tui.report_artifacts import collect_artifacts, prompt_open_artifacts

    prompt_open_artifacts(collect_artifacts(get_config_cache() or {}))


# ── 文件选择 ──────────────────────────────────────────────


def select_holdings_file() -> str | None:
    """让用户选择持仓文件，返回绝对路径；未找到时返回 None。"""
    from src.python.config import get_default, resolve_holdings_path

    refresh_config()
    config = get_config_cache() or {}
    specific_path = resolve_holdings_path(config)
    if os.path.exists(specific_path):
        return os.path.abspath(specific_path)
    dir_path = config.get("holdings_dir") or get_default("holdings_dir")
    files = list_xlsx_files(dir_path)
    if not files:
        print(f"  [ERR] 目录 '{dir_path}' 下未找到 xlsx 文件")
        print("     请先配置正确的持仓目录（菜单选项 C）")
        return None
    if len(files) == 1:
        print(f"  使用唯一找到的文件: {os.path.basename(files[0])}")
        return files[0]
    print("  找到多个持仓文件，请选择:")
    print(f"  {'':8s}{'文件名':40s}{'大小':>10s}{'修改日期':>22s}{'账户数':>8s}")
    print(f"  {'':-^8s}{'':-^40s}{'':->10s}{'':->22s}{'':->8s}")
    for i, f in enumerate(files, 1):
        basename = os.path.basename(f)
        name_disp = basename if len(basename) <= 38 else basename[:35] + "..."
        size_str = format_size(os.path.getsize(f))
        mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        info = get_xlsx_info(f)
        acct_str = f"{info.get('accounts', '?')}" if "error" not in info else "err"
        print(f"  [{i}]  {name_disp:38s} {size_str:>10s} {mtime:>22s} {acct_str:>8s}")
    try:
        choice = input_choice("  请输入编号: ")
        if choice is None:  # Esc：取消选择
            print()
            print("  [!] 已取消选择")
            return None
        choice = choice.strip()
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            return files[idx]
        print("  [ERR] 无效编号")
    except (ValueError, EOFError, KeyboardInterrupt):
        print()
        print("  [ERR] 无效输入")
    return None


# ── 菜单执行调度 ────────────────────────────────────────────


def execute_item(sel: int) -> None:
    """执行第 sel 项菜单的回调或退出。"""
    global _busy
    _, _label, callback, is_exit = MENU_ITEMS[sel]
    if is_exit:
        from src.python.tui.tui_menu import exit_app

        exit_app()
    if callback is not None:
        with _busy_lock:
            if _busy:
                return
            _busy = True
        try:
            callback()
        except PromptCancelledError:
            # Esc 取消：单点反馈后即时返回主菜单
            print("  [!] 已取消，返回主菜单")
        except KeyboardInterrupt:
            print()
            print("  操作已取消")
        except Exception as e:
            logger.exception("菜单项执行异常")
            print_error_with_hint(e, "操作执行异常")
        finally:
            with _busy_lock:
                _busy = False
