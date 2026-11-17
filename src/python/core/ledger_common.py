"""账本级共用原语 —— 特性开关收敛判定与时间戳口径。

两个账本（`core/decision_ledger.py` 决策账本、`core/signal_ledger.py` 确定性信号账本）
过去各自复制了同一份 `is_active()` 与 `_now_iso()`：同名同体，改判定口径（开关收敛方式、
时间戳精度/时区）要动两处，漏一处就出现「一个账本按秒、另一个按微秒」这类静默漂移。
本模块收这两条口径，账本单向引用并**保留各自原名导出**（既有导入面与测试 patch 点不变）。
"""

from __future__ import annotations

from datetime import datetime

__all__ = ["feature_active", "now_iso"]


def feature_active(flag: str) -> bool:
    """特性开关是否开启（账本收敛判定的唯一实现）。

    开关关闭时账本全链路无感：调用方据此跳过登记/结算，不产生任何副作用。

    Args:
        flag: 功能开关名（账本模块各自以 ``FEATURE_FLAG`` 声明）。

    Returns:
        开关开启为 True。
    """
    from src.python.config.features import is_feature_enabled

    return is_feature_enabled(flag)


def now_iso() -> str:
    """账本时间戳口径：本地时间 ISO8601，**秒级精度**（无微秒）。

    秒级是有意选择：账本按 (日期, 视界) 折叠与去重，微秒精度只会让同一次运行的
    两条记录看起来不同源；同时秒级形态与既有账本行的比对口径一致。
    """
    return datetime.now().isoformat(timespec="seconds")
