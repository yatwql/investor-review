"""LLM 定价模块 — 模型费用估算与定价配置管理。

支持峰谷定价（DeepSeek 官方方案）：含 ``peak`` 高峰价子段的模型，在高峰日
（周一至周五，不含中国法定节假日）的高峰时段（默认北京时间 9:00–12:00、
14:00–18:00）按高峰价计费，其余时段（闲时）按 base 价计费；周末（周六/周日）
与法定节假日全天一律按闲时价计费，不区分峰谷（官方 2026-09-10 定价页口径）。
时段、时区、周末与法定节假日规则由独立参考文件 ``llm_pricing_ref.json`` 覆盖。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.python.core.constants import (
    MODEL_PRICING,
    PRICING_HOLIDAY_ALWAYS_IDLE as _DEFAULT_HOLIDAY_ALWAYS_IDLE,
    PRICING_IDLE_PERIODS as _DEFAULT_IDLE_PERIODS,
    PRICING_PEAK_PERIODS as _DEFAULT_PEAK_PERIODS,
    PRICING_TIMEZONE as _DEFAULT_TIMEZONE,
    PRICING_WEEKEND_ALWAYS_IDLE as _DEFAULT_WEEKEND_ALWAYS_IDLE,
)

logger = logging.getLogger("invest")

__all__ = [
    "PRICING_MERGED",
    "PRICING_CURRENCY",
    "CURRENCY_SYMBOLS",
    "PRICING_PEAK_PERIODS",
    "PRICING_IDLE_PERIODS",
    "PRICING_TIMEZONE_NAME",
    "PRICING_WEEKEND_ALWAYS_IDLE",
    "PRICING_HOLIDAY_ALWAYS_IDLE",
    "reload_pricing",
    "compute_cost_value",
    "estimate_cost",
]


def _load_timezone(name: str) -> Any:
    """编译 IANA 时区；失败返回 None（回落系统本地时间）。

    zoneinfo 依赖系统 tzdata（Linux 一般自带）；缺失或名称非法时不影响计价，
    仅退化为按本地时间判定峰谷。
    """
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 — 时区加载失败属非致命降级，任意异常均可接受
        return None


def _parse_clock(text: str) -> int | None:
    """解析 "HH:MM"（24 小时制）为当日分钟数 [0, 1440)；失败返回 None。"""
    text = text.strip()
    try:
        hh, mm = text.split(":", 1)
        hh_i, mm_i = int(hh), int(mm)
    except (ValueError, IndexError):
        return None
    if 0 <= hh_i <= 23 and 0 <= mm_i <= 59:
        return hh_i * 60 + mm_i
    return None


def _parse_periods(value: Any) -> list[tuple[int, int]] | None:
    """解析 "HH:MM-HH:MM" 时段列表为 (start, end) 分钟闭区间。

    任意一项格式非法返回 None（调用方保留既有时段）；空列表合法返回 []。
    """
    if not isinstance(value, list):
        return None
    periods: list[tuple[int, int]] = []
    for item in value:
        if not isinstance(item, str):
            return None
        parts = item.split("-")
        if len(parts) != 2:
            return None
        start = _parse_clock(parts[0])
        end = _parse_clock(parts[1])
        if start is None or end is None:
            return None
        periods.append((start, end))
    return periods


# ── 运行时合并定价表：硬编码 + llm_settings.json 覆盖
# 定价条目结构：base 价（input/output/input_cache_hit，float）+ 可选高峰价子段
# "peak"（dict[str, float]）。无 "peak" 的模型始终按 base 价计费。
PriceEntry = dict[str, float | dict[str, float]]
PRICING_MERGED: dict[str, PriceEntry] = {model: dict(prices) for model, prices in MODEL_PRICING.items()}

# 定价货币标识，默认 CNY；可通过 llm_settings.json → pricing.currency 覆盖
PRICING_CURRENCY: str = "CNY"

# 货币符号映射
CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "CNY": "¥",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}

# 峰谷时段（分钟起算闭区间）——默认取 constants.py；可通过 llm_settings.json →
# pricing.peak_periods / idle_periods 覆盖
PRICING_PEAK_PERIODS: list[tuple[int, int]] = list(_DEFAULT_PEAK_PERIODS)
PRICING_IDLE_PERIODS: list[tuple[int, int]] = list(_DEFAULT_IDLE_PERIODS)

# 周末全天按闲时价计费（周六/周日不再区分峰谷）——默认取 constants.py，可通过
# llm_settings.json → pricing.weekend_always_idle 覆盖
PRICING_WEEKEND_ALWAYS_IDLE: bool = bool(_DEFAULT_WEEKEND_ALWAYS_IDLE)

# 法定节假日全天按闲时价计费（工作日但非 A 股交易日）——默认取 constants.py，
# 可通过 llm_settings.json → pricing.holiday_always_idle 覆盖
PRICING_HOLIDAY_ALWAYS_IDLE: bool = bool(_DEFAULT_HOLIDAY_ALWAYS_IDLE)

# 峰谷判定时区（IANA 名称）与编译后的 ZoneInfo 对象；加载失败回落本地时间
PRICING_TIMEZONE_NAME: str = _DEFAULT_TIMEZONE
PRICING_TZ: Any = _load_timezone(PRICING_TIMEZONE_NAME)

# 非模型键：pricing 段中不作模型合并的元字段
_NON_MODEL_PRICING_KEYS: frozenset[str] = frozenset(
    {"currency", "timezone", "peak_periods", "idle_periods", "weekend_always_idle", "holiday_always_idle"}
)

# 延迟加载标记 — reload_pricing() 首次调用 estimate_cost() 时执行
_PRICING_LOADED: bool = False


def _effective_minute(at_time: datetime | None) -> int:
    """换算待判定时刻为「定价时区」下的当日分钟数。

    at_time 缺省取当前时间；aware datetime 先换算到定价时区，naive datetime
    视为已在定价时区（便于测试传入固定时刻）。
    """
    tz = PRICING_TZ
    if at_time is None:
        now = datetime.now(tz) if tz else datetime.now()
        return now.hour * 60 + now.minute
    if at_time.tzinfo is not None and tz is not None:
        at_time = at_time.astimezone(tz)
    return at_time.hour * 60 + at_time.minute


def _is_weekend(at_time: datetime | None) -> bool:
    """待判定时刻（定价时区）是否周末（周六/周日）。

    naive datetime 视为已在定价时区（与 _effective_minute 一致，便于测试）。
    """
    tz = PRICING_TZ
    if at_time is None:
        now = datetime.now(tz) if tz else datetime.now()
        return now.weekday() >= 5
    if at_time.tzinfo is not None and tz is not None:
        at_time = at_time.astimezone(tz)
    return at_time.weekday() >= 5


def _is_holiday(at_time: datetime | None) -> bool:
    """待判定时刻（定价时区）是否为法定节假日（工作日但非 A 股交易日）。

    复用 core.trading_calendar._is_trading_day：交易日历（akshare / 同花顺兜底）
    可用时精确判定法定节假日（端午/中秋/国庆等）；日历不可用时回退为「非周末即
    交易日」，与周末闲时规则叠加后等价于仅周末闲时，降级可用不报错。仅工作日
    （周一至周五）才可能命中法定节假日——周末由 weekend_always_idle 单独处理。
    """
    tz = PRICING_TZ
    if at_time is None:
        date = datetime.now(tz) if tz else datetime.now()
    else:
        date = at_time
        if at_time.tzinfo is not None and tz is not None:
            date = at_time.astimezone(tz)
    if date.weekday() >= 5:
        return False
    try:
        from src.python.core.trading_calendar import _is_trading_day

        return not _is_trading_day(date)
    except Exception:  # noqa: BLE001 — 交易日历不可用时降级为不认定节假日，不影响计价
        return False


def _is_idle_day(at_time: datetime | None) -> bool:
    """是否「全天闲时日」——周末或法定节假日（各自受对应开关控制）。

    DeepSeek 官方 2026-09-10 定价页：高峰时段为北京时间周一至周五（不含中国法定
    节假日）9:00–12:00、14:00–18:00；其余时段，包括周末及法定节假日全天均为空闲
    时段。weekend_always_idle / holiday_always_idle 可分别经 llm_settings.json →
    pricing 段关闭（恢复按钟点区分峰谷），默认均开启。
    """
    weekend = _is_weekend(at_time)
    if PRICING_WEEKEND_ALWAYS_IDLE and weekend:
        return True
    if PRICING_HOLIDAY_ALWAYS_IDLE and not weekend and _is_holiday(at_time):
        return True
    return False


def _is_peak_minute(minute: int, idle_day: bool = False) -> bool:
    """分钟是否属于高峰时段（仅高峰日；闲时日恒为闲时）。

    高峰时段仅在高峰日（周一至周五、且非法定节假日）生效：peak_periods 非空时，
    高峰 = 这些时段，闲时 = 其余时间（官方方案「其余为空闲时段」）；peak_periods
    为空、仅 idle_periods 非空时，闲时 = 这些时段，高峰 = 其余时间；两者均空 →
    无峰谷定价，始终按 base 价。idle_day 为真（周末/法定节假日，受对应开关控制）
    时，无论时段一律返回 False（闲时价）。
    """
    if idle_day:
        return False
    if not PRICING_PEAK_PERIODS and not PRICING_IDLE_PERIODS:
        return False
    if PRICING_PEAK_PERIODS:
        return any(start <= minute <= end for start, end in PRICING_PEAK_PERIODS)
    return not any(start <= minute <= end for start, end in PRICING_IDLE_PERIODS)


def reload_pricing() -> None:
    """从计价参考文件 ``llm_pricing_ref.json`` 重新加载定价配置。

    参考数据结构：顶层策略（currency / timezone / peak_periods / idle_periods /
    weekend_always_idle / holiday_always_idle）+ ``models`` 逐模型单价覆盖。
    合并口径：内置 ``MODEL_PRICING`` 为基础价，文件只覆盖出现的模型与字段。
    文件缺失 → 仅用内置价；``version`` 不符 → 记录错误并回退内置价（报告仍可生成）；
    单个模型条目非法 → 告警并跳过该条。
    """
    global PRICING_CURRENCY
    global PRICING_PEAK_PERIODS, PRICING_IDLE_PERIODS
    global PRICING_TIMEZONE_NAME, PRICING_TZ
    global PRICING_WEEKEND_ALWAYS_IDLE, PRICING_HOLIDAY_ALWAYS_IDLE
    try:
        from src.python.config._llm_pricing import load_pricing_config

        config = load_pricing_config()
        PRICING_MERGED.clear()
        PRICING_MERGED.update(config["models"])
        PRICING_CURRENCY = str(config["currency"]).upper().strip()
        PRICING_TIMEZONE_NAME = str(config["timezone"]).strip()
        PRICING_TZ = _load_timezone(PRICING_TIMEZONE_NAME)
        PRICING_PEAK_PERIODS[:] = config["peak_periods"]
        PRICING_IDLE_PERIODS[:] = config["idle_periods"]
        PRICING_WEEKEND_ALWAYS_IDLE = bool(config["weekend_always_idle"])
        PRICING_HOLIDAY_ALWAYS_IDLE = bool(config["holiday_always_idle"])
    except Exception:
        logger.debug("加载计价参考失败，使用内置定价", exc_info=True)
    finally:
        # 显式重载即「已加载」：否则下一次计费的懒加载会再读一次文件，把调用方
        # 刚刚装载的定价（如测试注入的自定义价）静默覆盖掉——表现为先 reload 后计费
        # 的调用顺序里定价「自己变回去」，且只在进程内首次计费时发生（顺序依赖）。
        global _PRICING_LOADED
        _PRICING_LOADED = True


def compute_cost_value(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit_input_tokens: int = 0,
    at_time: datetime | None = None,
) -> float | None:
    """估算 LLM API 调用的费用**数值**——`estimate_cost` 的格式化前单源。

    计费规则与 `estimate_cost` 完全同源（峰谷价、缓存命中按 input_cache_hit 费率、
    命中数不得超过总输入的下限防御）；本函数只负责算数，不做货币符号格式化。
    事前费用预估（cost_forecast）与事后统计共享本函数，避免两处计费口径漂移。

    Args:
        model: 模型名称
        input_tokens: 总输入 token 数（含缓存命中+缓存未命中）
        output_tokens: 输出 token 数
        cache_hit_input_tokens: 其中属于缓存命中的 token 数（默认 0）
        at_time: 计费时刻（默认当前时间；naive 视为已在定价时区，便于测试固定时刻）

    Returns:
        费用数值（货币单位同 PRICING_CURRENCY）；未知模型或无 token 时返回 None
    """
    global _PRICING_LOADED
    if not _PRICING_LOADED:
        reload_pricing()
        _PRICING_LOADED = True
    if not input_tokens and not output_tokens:
        return None
    model_lower = model.lower().strip()
    pricing = PRICING_MERGED.get(model_lower)
    if not pricing:
        for known, price in PRICING_MERGED.items():
            if model_lower.startswith(known):
                pricing = price
                break
    if not pricing:
        return None
    # 峰谷定价：高峰日（工作日且非法定节假日）命中高峰时段时切换到高峰价子段；
    # 周末/法定节假日全天恒为闲时（受对应开关控制）
    effective: dict[str, float | dict[str, float]] = pricing
    peak = pricing.get("peak")
    if isinstance(peak, dict) and _is_peak_minute(_effective_minute(at_time), _is_idle_day(at_time)):
        effective = peak
    # 下限 0：防御非归一调用方传入"命中 > 总输入"（如把仅未命中的
    # input_tokens 与 cache_read 直接相减）导致费用出现负数
    cache_miss = max(input_tokens - cache_hit_input_tokens, 0)
    cost = cache_miss / 1_000_000 * float(effective["input"]) + output_tokens / 1_000_000 * float(effective["output"])
    if cache_hit_input_tokens > 0:
        cache_rate = effective.get("input_cache_hit", effective["input"])
        cost += cache_hit_input_tokens / 1_000_000 * float(cache_rate)
    return cost


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit_input_tokens: int = 0,
    at_time: datetime | None = None,
) -> str:
    """估算 LLM API 调用的费用（格式化字符串）。

    基于已知模型定价（每百万 token 价格），计费数学单源于 `compute_cost_value`。
    未知模型返回 "-"。
    货币符号由 PRICING_CURRENCY 决定（自 llm_settings.json → pricing.currency）。
    若存在缓存命中 token，按 input_cache_hit 费率计算（通常为 input 的 10%）。
    含 "peak" 高峰价子段的模型，在高峰日（工作日且非法定节假日）高峰时段按 peak
    价计费，其余时段按 base（闲时）价；周末与法定节假日全天一律按 base（闲时）价
    （PRICING_WEEKEND_ALWAYS_IDLE / PRICING_HOLIDAY_ALWAYS_IDLE）。

    Args:
        model: 模型名称
        input_tokens: 总输入 token 数（含缓存命中+缓存未命中）
        output_tokens: 输出 token 数
        cache_hit_input_tokens: 其中属于缓存命中的 token 数（默认 0）
        at_time: 计费时刻（默认当前时间；naive 视为已在定价时区，便于测试固定时刻）

    Returns:
        格式化费用字符串，如 "$0.008"、"¥0.06" 或 "-"
    """
    cost = compute_cost_value(model, input_tokens, output_tokens, cache_hit_input_tokens, at_time)
    if cost is None:
        return "-"
    symbol = CURRENCY_SYMBOLS.get(PRICING_CURRENCY, "$")
    if cost < 0.01:
        return f"{symbol}{cost:.4f}"
    return f"{symbol}{cost:.3f}"
