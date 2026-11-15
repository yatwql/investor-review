"""东财 push2 限流的运行期观测状态（akshare 与本仓 provider 共用）。

为什么单独成模块：push2 的限流断连在两条完全不同链路上出现——akshare 的
`stock_sector_fund_flow_rank` 等内部请求，以及本仓 `providers/eastmoney_industry`
的直连请求。两侧都需要「记一次限流」的同一份计数，而 providers 属下层、不能
import `report/`，因此状态收敛到零依赖的 core 层，报告层在渲染矩阵时读取。

口径：只做观测（计数 + 首条原文），不改变任何降级决策；报告侧把计数翻译成
一行可读提示（「东财 push2 限流：本轮 N 次断连（…已走备用通道）」）。
"""

from __future__ import annotations

import threading
from typing import Any

#: 限流/断连的特征词（akshare 内建请求的文案与 httpx 原始异常均可命中）
_LIMITED_HINTS: tuple[str, ...] = (
    "临时限流",
    "push2 行情服务器",
    "断开了连接",
    "RemoteDisconnected",
    "Connection aborted",
)

#: 报告提示的单一文案（HTML/Excel 同源；`{n}` 为本轮断连次数）
NOTICE_TEMPLATE = "东财 push2 限流：本轮 {n} 次断连（行业/估值等少数取数已走备用通道）"

_state_lock = threading.Lock()
_count = 0
_first_message = ""


def is_push2_limited(message: str | None) -> bool:
    """异常/日志文本是否属东财 push2 限流或断连（不需要异常类型，按文案判）。"""
    text = str(message or "")
    return bool(text) and any(hint in text for hint in _LIMITED_HINTS)


def note_failure(message: str | None) -> bool:
    """记录一次疑似 push2 限流；命中返回 True（未命中静默返回 False）。

    Args:
        message: 异常字符串或错误文案（`str(exc)`）。

    Returns:
        是否命中限流特征（调用方可据此决定日志级别，这里不写日志）。
    """
    global _count, _first_message
    if not is_push2_limited(message):
        return False
    with _state_lock:
        _count += 1
        if not _first_message:
            _first_message = str(message or "")[:200]
    return True


def push2_limited() -> dict[str, Any]:
    """本轮限流观测结果：``{count, first}``（无命中时 count=0、first=""）。"""
    with _state_lock:
        return {"count": _count, "first": _first_message}


def notice_line() -> str:
    """报告提示行（无命中返回空串，调用方据此不出行）。"""
    count = int(push2_limited().get("count") or 0)
    return NOTICE_TEMPLATE.format(n=count) if count > 0 else ""


def reset_push2_limit_state() -> None:
    """清空计数（报告边界与测试隔离调用）。"""
    global _count, _first_message
    with _state_lock:
        _count = 0
        _first_message = ""


__all__ = [
    "NOTICE_TEMPLATE",
    "is_push2_limited",
    "note_failure",
    "notice_line",
    "push2_limited",
    "reset_push2_limit_state",
]
