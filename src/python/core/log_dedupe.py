"""日志去重：同一 key 在时间窗内只上屏一次，重复下降到 DEBUG。

报告生成会在多个阶段重复装配同一批数据（行业批量、事件窗契约、新闻关联），
逐次打 INFO 会把日志刷成同一行 N 份，真正的阶段边界被淹没。按 key + 时间窗
折叠后：同一份报告内的重复装配只留一行，下一次报告（窗口外）照常上屏。

用法::

    from src.python.core.log_dedupe import log_throttled

    log_throttled(logger, "industry_batch", "批量行业数据就绪: %d/%d", n, total)
"""

from __future__ import annotations

import logging
import threading
import time

DEFAULT_WINDOW_SECS = 60.0
"""默认折叠窗口（秒）：同一份报告的重复装配通常在秒级，跨报告通常分钟级。"""

_MAX_KEYS = 64
"""key 数量上限（本模块只服务固定几个装配点，超限时整体清空即可）。"""

_last_logged: dict[str, float] = {}
_lock = threading.Lock()


def log_throttled(
    logger: logging.Logger,
    key: str,
    msg: str,
    *args: object,
    level: int = logging.INFO,
    window_secs: float = DEFAULT_WINDOW_SECS,
) -> bool:
    """按 ``key`` 折叠重复日志。

    Args:
        logger: 目标 logger。
        key: 折叠键（同一装配点用同一个常量），不同键互不影响。
        msg: 日志模板（``%`` 风格）。
        args: 模板参数。
        level: 首次上屏的级别，默认 INFO。
        window_secs: 折叠窗口（秒）。

    Returns:
        True 表示本次真正按 ``level`` 上屏；False 表示在窗口内已折叠为 DEBUG。
    """
    now = time.monotonic()
    with _lock:
        last = _last_logged.get(key)
        if last is not None and now - last < window_secs:
            folded = True
        else:
            if len(_last_logged) >= _MAX_KEYS:
                _last_logged.clear()
            _last_logged[key] = now
            folded = False
    if folded:
        # 不在此处二次格式化：模板里出现字面量 % 时 ``msg % args`` 会抛异常/错位。
        logger.log(logging.DEBUG, msg + "（同窗口重复，已折叠）", *args)
        return False
    logger.log(level, msg, *args)
    return True


def reset() -> None:
    """清空折叠窗口（测试与「新一次运行」显式重置用）。"""
    with _lock:
        _last_logged.clear()
