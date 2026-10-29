#!/usr/bin/env python3
"""投资复盘助手 — TUI 主入口。"""

from __future__ import annotations

import atexit
import os
import sys
import time
from collections.abc import Callable

# 确保项目根目录在 sys.path 中（支持直接执行 python src/python/tui/tui.py）
_src_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_src_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.python.config import init_config, get_default
from src.python.llm.pricing import format_costs
from src.python.core.logger import log_app_boundary, setup_logger
from src.python.tui.panel_runtime import NavState
from src.python.tui.text_layout import terminal_columns
from src.python.tui.tui_keys import KEY_CTRL_C, KEY_DOWN, KEY_ENTER, KEY_ESC, KEY_UP, get_key
from src.python.tui.tui_handlers import execute_item
from src.python.tui.tui_menu import (
    MENU_ITEMS,
    _apply_feature_gates,
    exit_app,
    first_run_hint_lines,
    index_by_key,
    match_menu_items,
    next_matching,
    menu_group_lines,
    print_header,
    render_menu,
    show_config,
)

logger = setup_logger()
log_app_boundary("启动", "TUI模式")
atexit.register(log_app_boundary, "关闭", "TUI模式")


def _print_session_usage_on_exit() -> None:
    """程序退出时打印 LLM 会话累计用量。"""
    try:
        from src.python.llm import get_session_usage

        usage = get_session_usage()
        if usage.get("call_count", 0) > 0:
            inp = usage.get("input_tokens", 0)
            out = usage.get("output_tokens", 0)
            cache_hit = usage.get("cache_hit_tokens", 0)
            total_tok = inp + out
            calls = usage.get("call_count", 0)
            cost_display = format_costs(usage.get("costs") or {})
            model = usage.get("model", "")
            print("\n── LLM 会话统计 ──")
            print(f"  模型: {model}")
            per_module = usage.get("per_module", {})
            if per_module:
                from src.python.core.registry import get_llm_module_names

                _MODULE_DISPLAY = get_llm_module_names()
                for key, display_name in _MODULE_DISPLAY.items():
                    if key in per_module:
                        pm = per_module[key]
                        _m = pm.get("model", "-")
                        _tag = " (缓存)" if pm.get("cached") else ""
                        print(f"    {display_name}: {_m}{_tag}")
            print(f"  调用次数: {calls}")
            print(f"  输入 tokens: {inp:,}")
            print(f"  输出 tokens: {out:,}")
            if cache_hit:
                print(f"  缓存命中: {cache_hit:,}")
            print(f"  总 tokens: {total_tok:,}")
            print(f"  累计费用: {cost_display}")
            print("──────────────────")
    except (KeyError, TypeError, AttributeError):
        logger.warning("打印 LLM 会话统计时出错", exc_info=True)
        pass


def _bind_callbacks() -> None:
    """运行时将函数引用填入 MENU_ITEMS。"""
    from src.python.tui.handlers_cache import (
        _cmd_cache_management,
        _cmd_update_basic_cache,
        _cmd_update_position_cache,
    )
    from src.python.tui.handlers_config import (
        _cmd_config_content_options,
        _cmd_config_report_boards,
        _cmd_global_settings,
        _cmd_refresh_config,
    )
    from src.python.tui.handlers_holdings import run_holdings_entry_panel
    from src.python.tui.handlers_log import _cmd_diagnose_menu
    from src.python.tui.handlers_report import (
        _cmd_generate_both,
        _cmd_generate_excel,
        _cmd_generate_full,
    )
    from src.python.tui.handlers_qa import _cmd_report_qa
    from src.python.tui.handlers_whatif import _cmd_whatif

    callbacks: dict[str, Callable] = {
        "E": _cmd_generate_excel,
        "B": _cmd_generate_both,
        "L": _cmd_generate_full,
        "W": _cmd_whatif,
        "Q": _cmd_report_qa,
        "1": _cmd_update_basic_cache,
        "2": _cmd_update_position_cache,
        "3": _cmd_cache_management,
        "C": _cmd_config_report_boards,
        "S": _cmd_config_content_options,
        "G": _cmd_global_settings,
        "U": run_holdings_entry_panel,
        "R": _cmd_refresh_config,
        "D": _cmd_diagnose_menu,
    }
    for i, (key, _label, _cb, is_exit) in enumerate(MENU_ITEMS):
        MENU_ITEMS[i] = (key, _label, callbacks.get(key), is_exit)


class _FrameLineCounter:
    """透明代理：累计 write 的换行数并透传到底层流（原地重绘需知道上一帧占用行数）。"""

    def __init__(self, stream):
        self._stream = stream
        self.lines = 0

    def write(self, text: str):
        self.lines += text.count("\n")
        return self._stream.write(text)

    def flush(self):
        return self._stream.flush()


def _render_menu_frame(sel: int, filter_text: str = "") -> int:
    """渲染一整帧首页（页眉 + 配置摘要 + 菜单），返回本帧占用行数。"""
    counter = _FrameLineCounter(sys.stdout)
    original = sys.stdout
    sys.stdout = counter
    try:
        print_header()
        show_config()
        render_menu(sel, filter_text)
    finally:
        sys.stdout = original
    return counter.lines


def _can_repaint_inplace() -> bool:
    """原地重绘可用性：POSIX + TTY（需 ANSI 光标控制）且未要求纯追加模式。

    管道/测试（非 TTY）、无 ANSI 的旧控制台、以及设了 ``TUI_PLAIN=1`` 的会话一律
    回退整屏追加——每帧都完整落到滚动区，便于日志抓取、屏幕阅读器与录制。
    """
    if os.environ.get("TUI_PLAIN"):
        return False
    try:
        return os.name == "posix" and sys.stdout.isatty()
    except Exception:
        return False


_ESC_EXIT_CONFIRM_WINDOW = 3.0  # 主菜单 Esc 连按两次确认窗口（秒）

#: 方向键别名（vim 手感）：主菜单与列表面板共用的单字母等价键
_NAV_ALIASES = {"j": KEY_DOWN, "k": KEY_UP}

#: 首页 `?` 的一行键位摘要（详细键位在手册，不在这里刷屏）
_HOME_KEYS_LINE = "  键位：字母/数字 直达 · ↑↓ 或 j k 移动 · 回车 执行 · / 筛选 · ? 帮助 · Esc×2 / 0 / X 退出"


def _print_hint(text: str) -> int:
    """主菜单按键反馈单行（按宽度折行，不整屏重绘）。

    Returns:
        int 占用行数（调用方并入原地重绘的清除范围，避免清帧错位）。
    """
    from src.python.tui.text_layout import wrap_with_prefix

    lines = wrap_with_prefix("  ", text, terminal_columns())
    for line in lines:
        print(line)
    return len(lines)


def _clear_last_frame(lines: int) -> None:
    """把光标移回上一帧首行并清空其下内容（ANSI：光标上移 N 行 + 清屏至末尾）。"""
    if lines > 0:
        sys.stdout.write(f"\x1b[{lines}A\x1b[0J")
        sys.stdout.flush()


def _read_filter_keyword(prompt: str) -> str | None:
    """筛选关键词读取入口（单独抽函数：行输入基于 raw 模式，与主循环逐键分离）。

    测试可整体替掉本入口，不必碰 ``tui_keys`` 源头（源头打点会把 feeder 永久绑定到
    惰性导入的处理器模块上）。
    """
    from src.python.tui.tui_keys import input_choice

    return input_choice(prompt)


def _ask_menu_filter(current: str) -> str:
    """读取主菜单筛选关键词（回车提交，空=清除；Esc 保持原筛选不变）。

    Args:
        current: 当前生效的关键词。

    Returns:
        新的关键词（Esc/EOF 时原样返回）。
    """
    from src.python.tui.text_layout import wrap_prompt

    hint = f"当前「{current}」· 回车清除" if current else "空=显示全部"
    try:
        raw = _read_filter_keyword(wrap_prompt(f"  筛选关键词（{hint} · Esc 取消）: "))
    except (EOFError, KeyboardInterrupt):
        return current
    if raw is None:  # Esc：不改筛选
        return current
    keyword = raw.strip()
    if keyword and not match_menu_items(keyword):
        _print_hint(f"「{keyword}」无匹配菜单项，保持原菜单")
        return current
    return keyword


def main() -> None:
    """TUI 主循环。方向键导航 + Enter 确认（全档可用）；窄屏直达并存。

    窄屏档（<64 列）交互主路径仍是「按字母/数字键直达」（未登记键给一行反馈、帧保持不动）；方向键/Enter 同样可用——移动选中态后**原地重绘**（ANSI 光标
    上移+清屏，菜单不滚屏），不支持 ANSI 的环境（管道/测试/旧控制台）回退
    整屏追加。Esc 需连按两次确认（3 秒窗口；防高延迟链路方向键拆包把孤 ESC 误判为退出），0/X 单次即退。
    """
    # ASCII 降级（TUI_ASCII=1）：在写出层做一字符换一字符的符号替换，版面代码不动
    from src.python.tui.symbols import install_ascii_stream

    install_ascii_stream()
    init_config()
    _apply_feature_gates()  # 必须在 _bind_callbacks 之前：裁剪后索引才与渲染一致
    _bind_callbacks()
    atexit.register(_print_session_usage_on_exit)

    # 启动时自动清理过期缓存（静默后台执行，仅日志记录）
    try:
        from src.python.cache import cleanup_expired

        removed = cleanup_expired(dry_run=False)
        if removed > 0:
            logger.info("启动时自动清理了 %d 个过期缓存文件", removed)
    except OSError as e:
        logger.warning("启动时缓存清理失败: %s", e)

    # 首次运行隐私提示
    try:
        from src.python.report.privacy_notice import show_privacy_notice_if_needed

        show_privacy_notice_if_needed()
    except Exception:
        logger.debug("隐私提示显示失败（非关键）", exc_info=True)

    # 首次运行引导（检测缺失资源并交互式提示）
    try:
        from src.python.startup_wizard import show_startup_wizard_if_needed

        show_startup_wizard_if_needed()
    except Exception:
        logger.debug("首次运行引导显示失败（非关键）", exc_info=True)

    # 读取缺省菜单选项（config.json → default_menu_key），仅支持 E/B/L/W/Q/D/1/2/3/P/I/A/S/R/V/H/T/X
    # （Q 报告追问受 report_qa 开关门控；T 系统自检恒上屏：
    # 关闭时对应项被裁剪，index_by_key 自然回落到首项）
    from src.python.config import get_config

    _default_key = get_config().get("default_menu_key", get_default("default_menu_key")).upper()
    _idx = index_by_key(_default_key)
    # 导航态单源（NavState）：首页 Enter 无条件派发、render_menu 自带高亮，故 cursor 即原 sel；
    # engaged 不影响主循环（仅 marker 用），与子菜单 panel_loop 的 engaged 门控语义独立
    nav = NavState(count=len(MENU_ITEMS), cursor=_idx if _idx is not None else 0)

    esc_exit_armed: float | None = None
    menu_filter = ""  # 主菜单关键词筛选（`/` 设定，`0` 清除；空=不筛选）

    while True:
        # 每帧重建门控：功能开关在 [S] 面板改完返回首页即生效（含重新开启被裁剪的项），
        # 无需重启；裁剪后项数变化 → 重新绑定回调并夹紧游标（防越界）
        _apply_feature_gates()
        _bind_callbacks()
        nav.count = len(MENU_ITEMS)
        if nav.cursor >= nav.count:
            nav.sync(0)
        frame_lines = _render_menu_frame(nav.cursor, menu_filter)
        visible = match_menu_items(menu_filter)  # 当前可见项索引（未筛选=全部）
        hint_lines = 0  # 帧下方反馈行数（原地重绘时并入清除范围）

        # 内层按键循环：直达键（快捷键/退出）处理后重绘或退出；方向键/Enter
        # 全档导航——窄屏优先原地重绘（菜单不滚屏），不可用时回退整屏追加
        while True:
            key = get_key()
            key = _NAV_ALIASES.get(key, key)
            if key != KEY_ESC and esc_exit_armed is not None:
                # 任何非 Esc 按键解除退出确认态：拆包孤 ESC 挂起的确认不被后续按键引爆
                esc_exit_armed = None

            if key == KEY_CTRL_C:
                exit_app()
            if key == KEY_ESC:
                # Esc 退出别名：连按两次确认（3 秒窗口）——孤 Esc 可能是方向键拆包
                # 误判（高延迟链路），误判代价从「退出程序」降为「多按一次」
                now = time.monotonic()
                if esc_exit_armed is not None and now - esc_exit_armed <= _ESC_EXIT_CONFIRM_WINDOW:
                    exit_app()
                esc_exit_armed = now
                hint_lines += _print_hint("再按一次 Esc 退出（0 / X 亦可）")
                continue
            if key == "/":
                # 关键词筛选：回车提交（空=清除），Esc 保持原有筛选不变
                menu_filter = _ask_menu_filter(menu_filter)
                break  # 重绘（带/不带筛选）
            if key == "?":
                # 首页速查：只打固定几行（不把菜单顶出可视区），详细键位见手册
                for line in [_HOME_KEYS_LINE, *menu_group_lines()]:
                    print(line)
                hints = first_run_hint_lines()
                if hints:
                    print("  待配置项：")
                    for line in hints:
                        print(line)
                break  # 摘要留在上方，下方重绘一帧菜单
            if key == "0":
                if menu_filter:
                    # 有筛选时 0 先清筛选（退出仍可 X / 再按 0 / Esc）
                    menu_filter = ""
                    hint_lines += _print_hint("已清除筛选")
                    break
                # 0 作退出别名：与子菜单「0 = 返回」的习惯一致（在首页返回即退出程序）
                exit_app()
            if len(key) == 1 and ("A" <= key <= "Z" or "a" <= key <= "z" or "0" <= key <= "9"):
                idx = index_by_key(key.upper())
                if idx is not None:
                    if menu_filter and idx not in visible:
                        # 筛选态下按到被隐藏的项：给可观察反馈，不静默吞键
                        hint_lines += _print_hint(f"「{key.upper()}」不在当前筛选结果中（/ 改关键词 · 0 清除筛选）")
                        continue
                    nav.sync(idx)
                    execute_item(idx)
                    break  # 直达执行后回到重绘点（子菜单关闭 → 刷新首页）
                # 未登记的字母：一行反馈即可（全档同语义——任何按键都有可观察结果；
                # 不为一次按错重绘一整屏，帧保持不动）
                hint_lines += _print_hint(f"「{key.upper()}」未登记（键位见上方菜单）")
                continue
            if key == KEY_ENTER:
                if menu_filter and nav.cursor not in visible:
                    target = next_matching(visible, nav.cursor, 1)
                    if target is not None:
                        nav.sync(target)
                execute_item(nav.cursor)
                break
            if key == KEY_UP or key == KEY_DOWN:
                step = 1 if key == KEY_DOWN else -1
                if menu_filter:
                    # 筛选态：只在匹配项之间移动（回绕），不让选中态落到隐藏项上
                    target = next_matching(visible, nav.cursor, step)
                    if target is not None:
                        nav.sync(target)
                else:
                    nav.move(key)  # 单源回绕（全菜单项可导航）；等价原 (sel±1)%len
                if _can_repaint_inplace():
                    # 导航原地重绘（光标上移+清屏）：窄屏防菜单顶出可视区、宽屏防滚屏
                    # 堆积（宽/窄同一导航手感，仅版式分档不改交互）；
                    # 反馈行（hint_lines）一并清除，避免清帧范围错位
                    _clear_last_frame(frame_lines + hint_lines)
                    frame_lines = _render_menu_frame(nav.cursor, menu_filter)
                    hint_lines = 0
                    continue
                break  # 非 TTY/旧控制台：回退整屏追加
            # 未识别按键：全档一行反馈（帧保持不动），与未登记字母同一口径
            hint_lines += _print_hint("未识别按键")
            continue


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("  感谢使用，再见！")
        sys.exit(0)
