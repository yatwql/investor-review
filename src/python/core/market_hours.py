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
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.python.core.constants import BEIJING_TZ, CACHE_WEEKLY

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


def is_intraday_timestamp(ts: float | str | None) -> bool:
    """给定时间戳是否落在 A 股交易时段内（当日 09:30~11:30 或 13:00~15:00，北京时间）。

    用途：判定一个缓存文件是「盘中快照」还是「收盘后数据」。盘中写入的行情值只是
    当时的价格，盘后不得当作收盘价长期复用，因此盘后回收时以**写入时刻**而非
    当前时刻判定（见 `cache/_ttl.get_cleanup_ttl`）。

    Args:
        ts: Unix 时间戳；容忍脏值（`None`/非数字字符串）——它们来自未经校验的缓存载荷

    Returns:
        写入时刻处于交易时段返回 True；否则 False（含无法解析的情形）
    """
    if ts is None:
        return False
    try:
        moment = datetime.fromtimestamp(float(ts), _BJ_TZ)
    except (TypeError, ValueError, OSError, OverflowError):
        return False
    minutes = moment.hour * 60 + moment.minute
    return (_MORNING_START <= minutes <= _MORNING_END) or (_AFTERNOON_START <= minutes <= _AFTERNOON_END)


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
    from src.python.config import get_config, get_default

    config = get_config()
    mh_config = config.get("market_hours") or {}
    use_official = mh_config.get("official_source", get_default("market_hours.official_source"))
    if not use_official:
        return None
    now = datetime.now(_BJ_TZ)
    if now.weekday() >= 5:
        return None  # 周末 return None 让 fallback 处理
    # 盘中 60s 刷新官方状态；盘后沿用上次结论一周（周末再打源无意义）
    official_ttl = 60 if _MORNING_START <= current_min <= _AFTERNOON_END else CACHE_WEEKLY
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


# ── 行情口径桶（LLM 缓存复用判定的时间口径） ──────────────
# 行情类输入在盘中逐分钟变、收盘后冻结。把「本次运行看到的是哪个已完成时点的
# 行情」抽象成一个桶：非盘中档（上一交易日收盘 / 上午收盘 / 当日收盘）内的多次
# 运行读到的是同一份快照，结论可复用；盘中档（09:30–11:30、13:00–15:00）行情在
# 变，结论一律不复用（宁可多花一次调用，也不让读者拿到十分钟前的盘中结论）。
# 场外产品只有官方净值（T+1 晚间更新），不参与盘中判定，口径由净值日自然覆盖。


@dataclass(frozen=True)
class MarketSnapshot:
    """一次运行所依据的行情口径桶。

    Attributes:
        key: 桶标识（进缓存键/指纹，如 ``close:2026-11-07`` / ``noon:2026-11-08`` /
            ``intraday:2026-11-08``）
        label: 人读口径（上屏日志与提示词，如「上一交易日收盘（2026-11-07）」）
        as_of: 行情基准日（YYYY-MM-DD）
        intraday: 是否盘中档（True ⇒ 该档结论不得复用）
    """

    key: str
    label: str
    as_of: str
    intraday: bool


#: 桶的进程内 memo：一次运行只判定一次（长驻 TUI 进程按轮重置，见 reset_market_snapshot）
_snapshot_memo: dict[str, MarketSnapshot | None] = {"bucket": None}
_snapshot_lock = threading.Lock()


def reset_market_snapshot() -> None:
    """清空桶 memo（每轮报告开始前调用；测试亦用）。"""
    with _snapshot_lock:
        _snapshot_memo["bucket"] = None


def market_snapshot_bucket(now: datetime | None = None) -> MarketSnapshot:
    """解析本次运行的行情口径桶（进程内只判定一次）。

    判定规则（北京时间）：
      - 交易日 09:30–11:30 / 13:00–15:00 → 盘中档（``intraday``，结论不复用）
      - 交易日 11:30–13:00 → 上午收盘档（当日 11:30 快照）
      - 交易日 ≥ 15:00 → 当日收盘档
      - 交易日 09:30 前、非交易日 → 上一交易日收盘档

    Args:
        now: 判定时点（默认当前北京时间；显式传入时**不写 memo**，供测试与回放）

    Returns:
        :class:`MarketSnapshot`
    """
    explicit = now is not None
    if not explicit:
        with _snapshot_lock:
            if _snapshot_memo["bucket"] is not None:
                return _snapshot_memo["bucket"]

    moment = now or datetime.now(_BJ_TZ)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_BJ_TZ)

    today = moment.strftime("%Y-%m-%d")
    minute = moment.hour * 60 + moment.minute
    # 交易日判定复用交易日历单源（盘前/节假日回溯到最近交易日），但只读**已缓存**日历：
    # 桶只是一个口径标签，不该为它触发取数，也不能因源不可用而中断。
    # 函数内导入是**必需**的：cache._ttl → market_hours → trading_calendar → cache 已成链，
    # 提到模块顶层即循环导入。
    from src.python.core.trading_calendar import trading_day_as_of_cached

    as_of_trading_day = trading_day_as_of_cached(moment)
    is_trading_today = as_of_trading_day == today

    if is_trading_today and (_MORNING_START <= minute < _MORNING_END or _AFTERNOON_START <= minute < _AFTERNOON_END):
        bucket = MarketSnapshot(
            key=f"intraday:{today}",
            label=f"盘中（{today} {moment:%H:%M}）",
            as_of=today,
            intraday=True,
        )
    elif is_trading_today and _MORNING_END <= minute < _AFTERNOON_START:
        bucket = MarketSnapshot(
            key=f"noon:{today}",
            label=f"上午收盘（{today} 11:30）",
            as_of=today,
            intraday=False,
        )
    elif is_trading_today and minute >= _AFTERNOON_END:
        bucket = MarketSnapshot(
            key=f"close:{today}",
            label=f"当日收盘（{today}）",
            as_of=today,
            intraday=False,
        )
    else:
        bucket = MarketSnapshot(
            key=f"close:{as_of_trading_day}",
            label=f"上一交易日收盘（{as_of_trading_day}）",
            as_of=as_of_trading_day,
            intraday=False,
        )

    if not explicit:
        with _snapshot_lock:
            _snapshot_memo["bucket"] = bucket
    return bucket


def market_snapshot_note() -> str:
    """提示词用的一行口径说明（让模型知道手里的行情是哪个时点的）。"""
    bucket = market_snapshot_bucket()
    return f"【数据口径】行情为 {bucket.label} 口径；净值类数据以官方最近公布日为准，不随盘中变化。"


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
