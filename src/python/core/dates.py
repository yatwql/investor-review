"""日期解析统一口径。

全仓日期解析失败语义此前按调用点各写一份 try/except（返回 None / ``""`` / 原串 /
抛错 / 带默认值），口径分散且难以核对。本模块只收拢**同一格式集合 + 同一失败语义
+ 同一返回类型**的重复组，函数名即语义，docstring 即失败口径；语义确实不同的调用点
仍各自保留（差异清单见 ``docs/managements/technical.md``「日期解析口径」）。

本模块不做任何格式猜测：解析失败一律返回 ``None``，由调用方决定降级动作。
"""

from __future__ import annotations

from datetime import date, datetime


def parse_datetime_ymd(text: str) -> datetime | None:
    """按 ``%Y-%m-%d`` 严格解析为 datetime。

    失败口径：格式非法或入参非字符串（ValueError / TypeError）返回 ``None``。
    """
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def parse_iso_date(text: str) -> date | None:
    """按 ISO 8601 纯日期（``YYYY-MM-DD``）解析为 date。

    失败口径：格式非法或入参非字符串（ValueError / TypeError）返回 ``None``。
    """
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def parse_datetime_iso(text: str) -> datetime | None:
    """按 ISO 8601 日期时间解析为 datetime（可带时分秒/时区偏移）。

    失败口径：格式非法（ValueError）返回 ``None``；入参非字符串仍抛 TypeError
    ——与原 ``datetime.fromisoformat`` 直接调用一致，调用点均已在类型上收口为 str。
    """
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
