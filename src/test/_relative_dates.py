"""测试用相对日期 — 单一来源。

写死绝对日期会随墙上时钟腐化：账本按保留期（730 天）在**写侧即裁剪**、行情/去重等
链路也按 `now()` 判窗口，样本日期一旦滑出窗口，用例会静默退化成「空账本 / 数据缺失」，
失败信息完全看不出是日期过期。因此测试里的样本
日期一律从当天回推派生，本模块是这套派生的唯一实现，禁止各测试文件各自再写一份。

三种口径：

- :func:`anchor` — 锚点日期（当天回推 ``shift_days`` 天）。
- :func:`day` — 相对锚点的日期串 ``YYYY-MM-DD``（``offset`` 单位：天，负数为更早）。
- :func:`recent_ts` — 相对当天的 ``YYYY-MM-DD HH:MM`` 时间戳（带小时，锚点文件等场景用）。

示例::

    from src.test._relative_dates import day

    _REPORT_DATE = day(0)        # 30 天前那天
    _NEXT_DATE = day(1)          # 次日
    old = day(-2, shift_days=60) # 60 天前的锚点再往前 2 天
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

#: 默认锚点回推天数（落在常见保留期/窗口内，又留有「近期」余量）
DEFAULT_SHIFT_DAYS = 30


def anchor(shift_days: int = DEFAULT_SHIFT_DAYS) -> date:
    """相对当天的锚点日期（``shift_days`` 天前）。"""
    return date.today() - timedelta(days=shift_days)


def day(offset: int = 0, *, shift_days: int = DEFAULT_SHIFT_DAYS) -> str:
    """相对锚点的日期串 ``YYYY-MM-DD``（``offset`` 单位：天，负数为更早）。"""
    return (anchor(shift_days) + timedelta(days=offset)).isoformat()


def recent_ts(days_ago: int = 1, hour: int = 10, *, shift_days: int | None = None) -> str:
    """相对当天的 ``YYYY-MM-DD HH:MM`` 时间戳。

    Args:
        days_ago: 相对当天回推的天数（1 = 昨天）。
        hour: 时间戳的小时（分钟/秒归零）。
        shift_days: 若给出则改以 ``day(shift_days=...)`` 为锚点再回推（一般不用）。

    """
    base = anchor(shift_days) if shift_days is not None else date.today()
    return datetime.combine(base - timedelta(days=days_ago), time(hour=hour)).strftime("%Y-%m-%d %H:%M")
