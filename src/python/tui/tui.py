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

from src.python.config import init_config
from src.python.llm.pricing import CURRENCY_SYMBOLS
from src.python.core.logger import log_app_boundary, setup_logger
from src.python.tui.switch_panel import layout_tier
from src.python.tui.text_layout import terminal_columns
from src.python.tui.tui_keys import KEY_CTRL_C, KEY_DOWN, KEY_ENTER, KEY_ESC, KEY_UP, get_key
from src.python.tui.tui_handlers import execute_item
from src.python.tui.tui_menu import (
    MENU_ITEMS,
    _apply_feature_gates,
    exit_app,
    index_by_key,
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
            cost = usage.get("total_cost", 0.0)
            currency = usage.get("currency", "CNY")
            symbol = CURRENCY_SYMBOLS.get(currency, "¥")
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
            print(f"  累计费用: {symbol}{cost:.4f}")
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
        _cmd_config_anonymization_mode,
        _cmd_config_comparison_indices,
        _cmd_config_dir_info,
        _cmd_config_llm_modules,
        _cmd_config_llm_providers,
        _cmd_config_report_boards,
        _cmd_refresh_config,
    )
    from src.python.tui.handlers_log import (
        _cmd_run_doctor,
        _cmd_view_health_history,
        _cmd_view_logs,
    )
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
        "D": _cmd_config_dir_info,
        "1": _cmd_update_basic_cache,
        "2": _cmd_update_position_cache,
        "4": _cmd_cache_management,
        "I": _cmd_config_comparison_indices,
        "A": _cmd_config_anonymization_mode,
        "P": _cmd_config_report_boards,
        "S": _cmd_config_llm_modules,
        "M": _cmd_config_llm_providers,
        "R": _cmd_refresh_config,
        "V": _cmd_view_logs,
        "H": _cmd_view_health_history,
        "T": _cmd_run_doctor,
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


def _render_menu_frame(sel: int) -> int:
    """渲染一整帧首页（页眉 + 配置摘要 + 菜单），返回本帧占用行数。"""
    counter = _FrameLineCounter(sys.stdout)
    original = sys.stdout
    sys.stdout = counter
    try:
        print_header()
        show_config()
        render_menu(sel)
    finally:
        sys.stdout = original
    return counter.lines


def _can_repaint_inplace() -> bool:
    """窄屏原地重绘可用性：POSIX + TTY（需 ANSI 光标控制）。

    管道/测试（非 TTY）与旧控制台（无 ANSI）回退整屏追加重绘。
    """
    try:
        return os.name == "posix" and sys.stdout.isatty()
    except Exception:
        return False


_ESC_EXIT_CONFIRM_WINDOW = 3.0  # 主菜单 Esc 连按两次确认窗口（秒）


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


def main() -> None:
    """TUI 主循环。方向键导航 + Enter 确认（全档可用）；窄屏直达并存。

    窄屏档（<64 列）交互主路径仍是「按字母/数字键直达」（未登记键静默忽略
    且不重绘）；方向键/Enter 同样可用——移动选中态后**原地重绘**（ANSI 光标
    上移+清屏，菜单不滚屏），不支持 ANSI 的环境（管道/测试/旧控制台）回退
    整屏追加。Esc 需连按两次确认（3 秒窗口；防高延迟链路方向键拆包把孤 ESC 误判为退出），0/X 单次即退。
    """
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

    # 读取缺省菜单选项（config.json → default_menu_key），仅支持 E/B/L/W/Q/D/1/2/3/4/P/I/A/S/R/V/H/T/X
    # （T 系统自检受 doctor_check 开关门控、Q 报告追问受 report_qa 开关门控：
    # 关闭时对应项被裁剪，index_by_key 自然回落到首项）
    from src.python.config import get_config

    _default_key = get_config().get("default_menu_key", "L").upper()
    _idx = index_by_key(_default_key)
    sel: int = _idx if _idx is not None else 0

    esc_exit_armed: float | None = None

    while True:
        frame_lines = _render_menu_frame(sel)
        hint_lines = 0  # 帧下方反馈行数（原地重绘时并入清除范围）

        # 内层按键循环：直达键（快捷键/退出）处理后重绘或退出；方向键/Enter
        # 全档导航——窄屏优先原地重绘（菜单不滚屏），不可用时回退整屏追加
        while True:
            key = get_key()
            narrow = layout_tier(terminal_columns()) == "narrow"

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
            if key == "0":
                # 0 作退出别名：与子菜单「0 = 返回」的习惯一致（在首页返回即退出程序）
                exit_app()
            if len(key) == 1 and ("A" <= key <= "Z" or "a" <= key <= "z" or "0" <= key <= "9"):
                idx = index_by_key(key.upper())
                if idx is not None:
                    sel = idx
                    execute_item(idx)
                    break  # 直达执行后回到重绘点（子菜单关闭 → 刷新首页）
                if narrow:
                    # 窄屏直达模式：未登记字母给单行反馈（不整屏重绘）——与宽档「重绘即
                    # 反馈」同语义：任何按键都有可观察结果（分档只改版式不改语义）
                    hint_lines += _print_hint(f"「{key.upper()}」未登记（键位见上方菜单）")
                    continue
                break
            if key == KEY_ENTER:
                execute_item(sel)
                break
            if key == KEY_UP or key == KEY_DOWN:
                sel = (sel - 1) % len(MENU_ITEMS) if key == KEY_UP else (sel + 1) % len(MENU_ITEMS)
                if narrow and _can_repaint_inplace():
                    # 窄屏导航：原地重绘（光标上移+清屏），手机短屏菜单不被顶出可视区；
                    # 反馈行（hint_lines）一并清除，避免清帧范围错位
                    _clear_last_frame(frame_lines + hint_lines)
                    frame_lines = _render_menu_frame(sel)
                    hint_lines = 0
                    continue
                break  # 宽/中档整屏重绘；窄屏不支持 ANSI 时同样回退追加
            if narrow:
                # 窄屏未知键：单行反馈（不整屏重绘），与宽档「重绘一屏」同语义
                hint_lines += _print_hint("未识别按键")
                continue
            # 宽/中档未知键：重绘一屏给出反馈
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("  感谢使用，再见！")
        sys.exit(0)
