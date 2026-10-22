"""A 股交易时段判断模块。

提供多层判断机制（config → API → fallback）来确定
A 股市场当前是否在交易时段。

用法::

    from src.python.core.market_hours import is_market_open

    if is_market_open():
        # 盘中，使用短 TTL
    else:
        # 盘后，使用长 TTL
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from src.python.core.constants import BEIJING_TZ

logger = logging.getLogger("invest")

# ── 北京时区常量 ──────────────────────────────────────────
_BJ_TZ = BEIJING_TZ  # 项目统一北京时间口径（单一事实来源见 core.constants）

# ── A 股交易时段（内置默认值，用于 fallback） ───────────
# 早盘 09:30 (570min) – 11:30 (690min)
# 午盘 13:00 (780min) – 15:00 (900min)
_MORNING_START = 570  # 09:30
_MORNING_END = 690  # 11:30
_AFTERNOON_START = 780  # 13:00
_AFTERNOON_END = 900  # 15:00

# ── 官方交易状态缓存 ───────────────────────────────────
_CACHE_KEY_MARKET_HOURS = "market_hours"
_PUSH2_BASE = "https://push2.eastmoney.com/api/qt/stock/get"
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.eastmoney.com/",
}

# ── 进程内分钟级结果 memo ────────────────────────────
# 开闭市判定在一个自然分钟内不会变化，而高频调用路径（缓存 TTL 判断、provider
# 策略选择、取价方式）每秒可达数十次。按分钟粒度 memo（threadlocal，每 worker
# 一份、无锁），把三层判断压到每 worker 每分钟一次；DEBUG 日志仅在判定结果
# 变化时输出。去重状态是**进程级**（dict + 锁）而非 threadlocal：判定结果与线程
# 无关，threadlocal 会让每个新增 worker 首判都各记一条，实测同一毫秒重复 36 条。
_memo = threading.local()
_log_state: dict[str, Any] = {}
_log_lock = threading.Lock()
_STATE_UNSET = object()


def reset_memo_state() -> None:
    """清空本线程的分钟级 memo 与日志去重状态（测试与长驻进程手动失效用）。"""
    _memo.minute = -1
    _memo.result = None
    with _log_lock:
        _log_state.clear()


def _debug_on_change(state_key: str, message: str, *args: Any) -> None:
    """仅在判定结果变化时输出 DEBUG（进程级去重，任一 worker 记录即可）。"""
    value = args[-1] if args else None
    with _log_lock:
        changed = _log_state.get(state_key, _STATE_UNSET) != value
        if changed:
            _log_state[state_key] = value
    if changed:
        logger.debug(message, *args)


def _parse_time_to_minutes(time_str: str) -> int | None:
    """将 ``HH:MM`` 字符串转换为当日分钟数。

    Args:
        time_str: 如 ``"09:30"``、``"15:00"``

    Returns:
        当日分钟数（如 570），解析失败返回 None
    """
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return None


def _fetch_trading_status_from_official() -> int | None:
    """从东方财富 push2 API 获取上证指数实时交易状态。

    f100 字段含义：
        - 0 = 未开盘（盘前）
        - 1 = 交易中
        - 2 = 已收盘（盘后）
        - 3 = 午间休市

    Returns:
        交易状态码（0-3），API 失败返回 None
    """
    from src.python.core.http_client import make_http_client

    params = {"secid": "1.000001", "fields": "f100,f169"}
    try:
        with make_http_client(timeout=5.0) as client:
            resp = client.get(_PUSH2_BASE, params=params, headers=_EM_HEADERS)
            data = resp.json()
            inner = data.get("data")
            if inner and isinstance(inner, dict):
                status = inner.get("f100")
                if status is not None:
                    return int(status)
    except Exception as e:
        logger.debug("获取东方财富交易状态失败: %s", e)
    return None


def _is_market_open_config(current_min: int) -> bool | None:
    """第 1 层：从 config.json 手动覆盖判断市场是否开盘。

    Returns:
        True 开市 / False 闭市 / None 未配置，继续下一层
    """
    from src.python.config import get_config

    config = get_config()
    mh_config = config.get("market_hours") or {}
    start_str = mh_config.get("start")
    end_str = mh_config.get("end")
    if not start_str or not end_str:
        return None
    start_min = _parse_time_to_minutes(start_str)
    end_min = _parse_time_to_minutes(end_str)
    if start_min is None or end_min is None:
        return None
    now = datetime.now(_BJ_TZ)
    if now.weekday() >= 5:
        return False
    in_range = start_min <= current_min <= end_min
    lunch = _MORNING_END < current_min < _AFTERNOON_START
    result = in_range and not lunch
    _debug_on_change("config", "市场时段(配置 %s-%s): %s", start_str, end_str, result)
    return result


def _is_market_open_official(current_min: int) -> bool | None:
    """第 2 层：从东方财富 push2 API 实时交易状态判断。

    Returns:
        True 开市 / False 收盘 / None API 不可用
    """
    from src.python.cache import get, set
    from src.python.config import get_config

    config = get_config()
    mh_config = config.get("market_hours") or {}
    use_official = mh_config.get("official_source", True)
    if not use_official:
        return None
    now = datetime.now(_BJ_TZ)
    if now.weekday() >= 5:
        return None  # 周末 return None 让 fallback 处理
    official_ttl = 60 if _MORNING_START <= current_min <= _AFTERNOON_END else 86400 * 7
    cached = get(_CACHE_KEY_MARKET_HOURS, official_ttl)
    if cached is not None and isinstance(cached, dict):
        status = cached.get("status")
        _debug_on_change("api_cache", "市场时段(API缓存): status=%s", status)
        if status == 1:
            return True
        if status == 2:
            return False
    status = _fetch_trading_status_from_official()
    if status is not None:
        set(_CACHE_KEY_MARKET_HOURS, {"status": status})
        _debug_on_change("api_live", "市场时段(API实时): status=%s", status)
        if status == 1:
            return True
        if status == 2:
            return False
    return None


def _is_market_open_fallback(current_min: int) -> bool:
    """第 3 层：根据内置默认值判断市场是否开盘。

    北京时区工作日 09:30–11:30 + 13:00–15:00，自动排除午餐和周末。
    """
    now = datetime.now(_BJ_TZ)
    if now.weekday() >= 5:
        return False
    in_morning = _MORNING_START <= current_min <= _MORNING_END
    in_afternoon = _AFTERNOON_START <= current_min <= _AFTERNOON_END
    return in_morning or in_afternoon


def is_midday_break() -> bool:
    """检查当前是否为 A 股午间休市时段（11:30-13:00，北京时间）。

    午间休市时最新价格来自上午收盘，既非实时价也非全日收盘价。
    用于取价方式标识，区分"午市收盘"和"收盘价"。

    Returns:
        True 表示正处于午间休市时段（11:30-13:00 之间）
    """
    now = datetime.now(_BJ_TZ)
    if now.weekday() >= 5:
        return False
    current_min = now.hour * 60 + now.minute
    return _MORNING_END < current_min < _AFTERNOON_START


def is_market_open() -> bool:
    """多渠道判断 A 股市场当前是否在交易时段。

    优先级：
    1. **config.json** ``market_hours.start`` / ``market_hours.end`` 手动覆盖
    2. **东方财富 push2 API** 实时交易状态（缓存 TTL：盘中 60s，盘后 7 天）
    3. **内置默认值**（北京时区工作日 09:30–11:30 + 13:00–15:00，自动排除午餐）

    非交易时段返回 ``False``，让 price / index 缓存使用长 TTL 保持收盘价。

    进程内按分钟粒度 memo：同一分钟内的重复调用直接复用上次判定（三层判断与
    DEBUG 日志都不重跑）；异常结果不入 memo（下次调用重新判断）。

    Returns:
        是否在交易时段内
    """
    try:
        now = datetime.now(_BJ_TZ)
        minute = int(now.timestamp() // 60)
        if getattr(_memo, "minute", None) == minute:
            return bool(_memo.result)
        current_min = now.hour * 60 + now.minute

        # 第 1 层：config.json 手动覆盖
        result = _is_market_open_config(current_min)
        if result is None:
            # 第 2 层：官方 API 实时状态
            result = _is_market_open_official(current_min)
        if result is None:
            # 第 3 层：内置默认值
            result = _is_market_open_fallback(current_min)
        _memo.minute = minute
        _memo.result = result
        return result

    except Exception:
        logger.warning("is_market_open 异常，保守返回 False", exc_info=True)
        return False  # 异常时保守处理：视为非交易时段（不入 memo，下次重新判断）
