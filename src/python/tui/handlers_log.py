"""TUI 运行状态诊断命令处理器。

菜单 [V] 查看最近运行日志（可按级别筛选）、[H] 查看数据源健康历史、
[T] 系统自检（默认开启，features.json 中 doctor_check 为 false 时该菜单项不出现）。
三者同属只读诊断面，故归于一模块。

所有解析/聚合逻辑委托核心层（core/log_reader.py、core/perf.py、core/doctor.py），
本模块仅保留 TUI 外壳（级别提示、彩色渲染、traceback 折叠、翻页等待）。
"""

from __future__ import annotations

from src.python.core.logger import setup_logger
from src.python.tui.text_layout import terminal_columns, wrap_hanging, wrap_prompt
from src.python.tui.tui_keys import PromptCancelledError, input_choice
from src.python.tui.tui_menu import GREEN, RED, RESET, YELLOW, press_any_key

logger = setup_logger()

# 单屏最多展示的日志条数（防止长日志刷屏）
_DISPLAY_LINES = 200

# 级别筛选提示文案
_LEVEL_PROMPT_TEXT = "（留空=全部，可选: DEBUG/INFO/WARNING/ERROR/CRITICAL）"


def _level_prompt() -> str | None:
    """交互式级别筛选提示；空回车返回 None（全部），无效级别提示后按全部处理。"""
    raw = input_choice(wrap_prompt(f"  按级别筛选 {_LEVEL_PROMPT_TEXT}（回车=全部级别 · Esc 取消）: "))
    if raw is None:  # Esc：取消查看返回主菜单
        raise PromptCancelledError
    raw = raw.strip().upper()
    if not raw:
        return None
    if raw in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return raw
    print(f"  {YELLOW}[!]{RESET} 无效级别「{raw}」，将显示全部日志")
    return None


def _level_color(level: str) -> str:
    """日志级别对应的终端颜色（ERROR/CRITICAL 红、WARNING 黄、其余无色）。"""
    if level in ("ERROR", "CRITICAL"):
        return RED
    if level == "WARNING":
        return YELLOW
    return ""


def _cmd_view_logs() -> None:
    """查看最近运行日志（可按级别筛选，traceback 折叠为提示行）。"""
    from src.python.core.log_reader import read_log

    level = _level_prompt()
    try:
        entries = read_log(limit=_DISPLAY_LINES, level=level)
    except (ValueError, OSError):
        logger.exception("读取运行日志失败")
        print(f"  {RED}[ERR]{RESET} 读取运行日志失败")
        return

    if not entries:
        print(f"  {YELLOW}[!]{RESET} 无匹配日志条目")
        return

    from src.python.tui.switch_panel import inner_width, use_panel_box

    columns = terminal_columns()
    inner = inner_width(columns)
    narrow = not use_panel_box(columns)
    rule = "  " + "=" * max(10, min(40, inner - 2))

    level_label = level or "全部"
    print()
    print(rule)
    print(f"  最近日志（级别: {level_label}）")
    print(rule)
    for entry in entries:
        color = _level_color(entry.level)
        line = f"  {entry.time} [{entry.level}] {entry.message}"
        if narrow:
            # 窄档：先按内宽悬挂折行，再逐行上色（着色放在折行之后，ANSI 不被截断）
            for piece in wrap_hanging(line, inner):
                print(f"{color}{piece}{RESET}" if color else piece)
        else:
            print(f"{color}{line}{RESET}" if color else line)
        # traceback 等续行折叠为一行提示，避免刷屏
        body_lines = entry.body.splitlines()[1:]
        if body_lines:
            print(f"    ⤷ 堆栈详情 +{len(body_lines)} 行")
    press_any_key()


def _cmd_view_health_history() -> None:
    """查看数据源健康历史（最近 10 次检查记录）。"""
    from src.python.core.perf import summarize_health_history

    try:
        summaries = summarize_health_history(limit=10)
    except OSError:
        logger.exception("读取数据源健康历史失败")
        print(f"  {RED}[ERR]{RESET} 读取数据源健康历史失败")
        return

    if not summaries:
        print(f"  {YELLOW}[!]{RESET} 暂无数据源健康历史记录")
        return

    from src.python.tui.switch_panel import inner_width, use_panel_box

    columns = terminal_columns()
    inner = inner_width(columns)
    narrow = not use_panel_box(columns)
    rule = "  " + "=" * max(10, min(40, inner - 2))

    print()
    print(rule)
    print("  数据源健康历史（最近 10 次检查）")
    print(rule)
    for summary in summaries:
        ts = summary["timestamp"].replace("T", " ")
        ok_count = summary["ok_count"]
        total = summary["total"]
        fail_count = summary["fail_count"]
        status = GREEN if fail_count == 0 else RED
        extra = f"  |  {summary['report_type']}" if summary.get("report_type") else ""
        head = f"  {ts}  {status}{ok_count}/{total} 正常{RESET}{extra}  |  失败 {fail_count}"
        if narrow:
            # 窄档：一条记录压成「时间 + 结果」行，失败源悬挂折行，不留列错位
            print(ts)
            print(f"  {status}{ok_count}/{total} 正常{RESET} · 失败 {fail_count}{extra}")
        else:
            print(head)
        if summary["failed_sources"]:
            for line in wrap_hanging(f"      失败源: {', '.join(summary['failed_sources'])}", inner, indent="      "):
                print(line)
    press_any_key()


# ── 系统自检（doctor_check 开关门控）────────────────────────

# TUI 内网络检查的整体耗时预算（短于 CLI——交互场景不能让用户干等）
_DOCTOR_NETWORK_TIMEOUT = 6.0


def _cmd_run_doctor() -> None:
    """系统自检（环境/配置/目录/功能开关/数据源），失败项附修复建议。

    交互场景下先问是否联网——离线自检瞬时返回，联网自检受预算约束。
    """
    from src.python.core.doctor import format_doctor_report, run_doctor_checks, summarize_doctor_results

    raw = input_choice(wrap_prompt("  是否包含数据源网络检查？(y=联网 / 空回车=仅本地): "))
    if raw is None:  # Esc：中止自检返回主菜单
        raise PromptCancelledError
    raw = raw.strip().lower()
    include_network = raw in ("y", "yes", "是")

    scope = f"（含数据源联网检查，最多约 {_DOCTOR_NETWORK_TIMEOUT:g}s）" if include_network else "（仅本地）"
    print(f"  {YELLOW}[..]{RESET} 正在自检{scope}...")
    try:
        results = run_doctor_checks(include_network=include_network, max_timeout=_DOCTOR_NETWORK_TIMEOUT)
    except Exception:
        logger.exception("系统自检执行失败")
        print(f"  {RED}[ERR]{RESET} 系统自检执行失败（详见日志）")
        return

    print()
    print(format_doctor_report(results))

    _ok_count, bad_count = summarize_doctor_results(results)
    if bad_count:
        print(f"  {RED}[!]{RESET} 有 {bad_count} 项未通过——按上方 → 建议逐项处理")
    else:
        print(f"  {GREEN}[OK]{RESET} 全部通过")
    press_any_key()
