"""ANSI 终端颜色常量 — 共享模块，避免 report 层依赖 UI 层。

使用方：
  - tui_menu.py（UI 层）
  - report/progress.py（报告层）
  - handlers_report.py、handlers_config.py、handlers_cache.py（处理层）
  - logger.py（日志层）
"""

from __future__ import annotations

import os
import sys

try:
    import colorama

    colorama.init()  # 包装 stdout，ANSI → Win32 API，不依赖终端原生 ANSI 支持
except ImportError:
    pass  # 无 colorama 时 Windows 控制台可能无法正确显示颜色，但功能不受影响

#: 原始转义码表（**不做 TTY 降级**）—— 全仓转义码字面量的唯一定义处。
#: `codes_for` 按调用方自己那条流判定；模块级 GREEN/RED/... 常量按 **stdout** 判定一次。
RAW_CODES: dict[str, str] = {
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "YELLOW": "\033[93m",
    "CYAN": "\033[96m",
    "DIM": "\033[2m",
    "BLUE": "\033[94m",
    "ORANGE": "\033[38;5;208m",
    "MAGENTA": "\033[95m",
    "BOLD": "\033[1m",
    "RESET": "\033[0m",
}

# ANSI 颜色：非 TTY 或设置了 NO_COLOR 环境变量时禁用颜色输出（导入时按 stdout 快照一次）
_STDOUT_COLORED = "NO_COLOR" not in os.environ and sys.stdout.isatty()


def _stdout_code(name: str) -> str:
    """取原始转义码；stdout 不可着色时空串（直接拼进字符串即无副作用）。"""
    return RAW_CODES[name] if _STDOUT_COLORED else ""


GREEN = _stdout_code("GREEN")
RED = _stdout_code("RED")
YELLOW = _stdout_code("YELLOW")
CYAN = _stdout_code("CYAN")
DIM = _stdout_code("DIM")  # 次要信息降权（键名/费用/图例），让主列先被看到
BLUE = _stdout_code("BLUE")  # 结构色：分组标题与面板横幅（不承载状态语义）
ORANGE = _stdout_code("ORANGE")  # 品牌色：应用名与版本号（256 色橙；不识别的终端落回默认色）
MAGENTA = _stdout_code("MAGENTA")  # 事件色：LLM 实际调用行（报告运行时「花钱的调用发生了」的唯一视觉信号）
BOLD = _stdout_code("BOLD")
RESET = _stdout_code("RESET")


def supports_color(stream: object | None = None) -> bool:
    """给定流（默认 stdout）是否支持着色：``NO_COLOR`` 或非 TTY → False。

    着色能力判定**单源在此**——写 stderr 的渠道（CLI verbose 进度、自检报告）与
    写 stdout 的渠道共用同一判据，只换传参，不再各自复制 ``NO_COLOR``/``isatty`` 逻辑。

    Args:
        stream: 目标输出流（如 ``sys.stderr``）；None 时取 stdout。
    """
    target = sys.stdout if stream is None else stream
    if "NO_COLOR" in os.environ:
        return False
    return bool(getattr(target, "isatty", lambda: False)())


def codes_for(stream: object | None = None) -> dict[str, str]:
    """按给定流的着色能力返回转义码表；不支持时各项均为空串。

    Args:
        stream: 目标输出流（如 ``sys.stderr``）；None 时取 stdout。

    Returns:
        ``{"GREEN": "\033[92m", ...}``（不支持着色时全部为空串，直接拼进字符串即无副作用）。
    """
    return dict(RAW_CODES) if supports_color(stream) else dict.fromkeys(RAW_CODES, "")
