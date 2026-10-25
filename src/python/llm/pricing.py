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
    PRICING_DEFAULT_CURRENCY as _DEFAULT_PRICING_CURRENCY,
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
    "add_cost",
    "currency_symbol",
    "FX_TO_CNY",
    "convert_amount",
    "format_costs",
    "merge_costs",
    "model_currency",
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
PriceEntry = dict[str, float | str | dict[str, float]]
PRICING_MERGED: dict[str, PriceEntry] = {model: dict(prices) for model, prices in MODEL_PRICING.items()}

# 计价与**显示**币种偏好（本地主币种），缺省取 `constants.PRICING_DEFAULT_CURRENCY`
# （CNY）；可由 llm_pricing_ref.json 顶层 currency 覆盖。解析顺序：配置币种（若该模型
# 提供此币种价）→ 模型原生币种。即「厂商同时提供多币种价时以客户配置币种为主」，
# 只提供原生币种时按原生币种显示（不做汇率折算）。
PRICING_CURRENCY: str = _DEFAULT_PRICING_CURRENCY

# 预算换算用的内部汇率表（**只用于日预算比对，绝不用于展示金额**）。
# 依据 2026-10-25 中国外汇交易中心/银行牌价中间价取整；改汇率只影响预算判断。
FX_TO_CNY: dict[str, float] = {
    "CNY": 1.0,
    "USD": 6.67,
    "EUR": 7.47,
    "GBP": 8.92,
    "JPY": 0.0425,
}

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
        from src.python.config import load_pricing_config

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


def _match_pricing(model: str) -> PriceEntry | None:
    """按「精确 → 前缀」匹配定价条目（未知模型返回 None）。"""
    model_lower = str(model or "").lower().strip()
    if not model_lower:
        return None
    pricing = PRICING_MERGED.get(model_lower)
    if pricing:
        return pricing
    for known, price in PRICING_MERGED.items():
        if model_lower.startswith(known):
            return price
    return None


def _entry_currencies(pricing: PriceEntry) -> list[str]:
    """条目可用的币种列表：原生 `currency` + `alt` 里额外提供的币种。"""
    native = str(pricing.get("currency") or _DEFAULT_PRICING_CURRENCY).strip().upper()
    codes = [native]
    alt = pricing.get("alt")
    if isinstance(alt, dict):
        codes.extend(str(code).strip().upper() for code in alt if str(code).strip())
    return list(dict.fromkeys(codes))


def _resolve_entry(model: str) -> tuple[PriceEntry, str]:
    """解析模型生效的价格条目与币种。

    规则（客户配置优先）：配置币种 `PRICING_CURRENCY` 在条目提供的币种里 → 用该币种
    的价（原生或 `alt` 子表）；否则用模型原生币种。**不做任何汇率折算**——折算会让
    显示金额对不上厂商标价。
    """
    pricing = _match_pricing(model)
    if not pricing:
        return ({}, PRICING_CURRENCY)
    # 条目未声明币种时用**常量缺省**（不是配置币种）：配置币种只决定「多币种价选哪套」，
    # 绝不改变条目自身的标价币种，否则改配置会把人民币数字贴上 `$`
    native = str(pricing.get("currency") or _DEFAULT_PRICING_CURRENCY).strip().upper()
    preferred = str(PRICING_CURRENCY).strip().upper()
    alt = pricing.get("alt")
    if preferred != native and isinstance(alt, dict):
        override = alt.get(preferred) or alt.get(preferred.lower())
        if isinstance(override, dict) and override:
            merged: PriceEntry = {k: v for k, v in pricing.items() if k != "alt"}
            merged.update({k: v for k, v in override.items() if k != "currency"})
            merged["currency"] = preferred
            return (merged, preferred)
    return (pricing, native)


def model_currency(model: str) -> str:
    """模型生效的**展示币种**（配置币种优先，其次原生币种）。"""
    _entry, currency = _resolve_entry(model)
    return currency


def currency_symbol(currency: str | None) -> str:
    """币种代码 → 显示符号（未知币种原样返回代码，避免假装成某种货币）。"""
    code = str(currency or PRICING_CURRENCY).strip().upper()
    return CURRENCY_SYMBOLS.get(code, code)


# ── 多币种金额聚合（跨币种**从不相加**，只分组并列） ──────────────


def add_cost(buckets: dict[str, float], currency: str, amount: float) -> None:
    """把一笔金额累加进「币种 → 金额」桶（就地更新）。"""
    if not amount:
        return
    code = str(currency or PRICING_CURRENCY).strip().upper()
    buckets[code] = buckets.get(code, 0.0) + float(amount)


def convert_amount(amount: float, from_currency: str, to_currency: str) -> float | None:
    """按内部汇率表把金额从一种币种换算到另一种——**仅供预算比对**，不用于展示。

    未知币种返回 None（调用方按「无法比对」处理，不猜）。
    """
    src = str(from_currency or PRICING_CURRENCY).strip().upper()
    dst = str(to_currency or PRICING_CURRENCY).strip().upper()
    rate_src = FX_TO_CNY.get(src)
    rate_dst = FX_TO_CNY.get(dst)
    if not rate_src or not rate_dst:
        return None
    return float(amount) * rate_src / rate_dst


def merge_costs(*buckets: dict[str, float]) -> dict[str, float]:
    """合并多个「币种 → 金额」桶（同币种相加，异币种并存）。"""
    merged: dict[str, float] = {}
    for bucket in buckets:
        for code, amount in (bucket or {}).items():
            add_cost(merged, code, float(amount or 0.0))
    return merged


def format_costs(buckets: dict[str, float] | None, digits: int = 4) -> str:
    """把「币种 → 金额」桶格式化为展示串：`¥0.0123 + $0.0045`。

    单币种时与逐笔格式一致（`¥0.0123`）；空桶返回 `"-"`。币种按代码排序，
    保证同一组数字在任何调用顺序下显示一致。
    """
    items = {str(k).upper(): float(v or 0.0) for k, v in (buckets or {}).items()}
    items = {k: v for k, v in items.items() if v}
    if not items:
        return "-"
    return " + ".join(f"{currency_symbol(code)}{items[code]:.{digits}f}" for code in sorted(items))


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
        费用数值（货币单位 = 该模型的官方币种，见 ``model_currency``）；未知模型或无 token 返回 None
    """
    global _PRICING_LOADED
    if not _PRICING_LOADED:
        reload_pricing()
        _PRICING_LOADED = True
    if not input_tokens and not output_tokens:
        return None
    pricing, _currency = _resolve_entry(model)
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
    货币符号由**模型自身币种**决定（`model_currency`）：Claude / GPT / Gemini 显示
    `$`，DeepSeek / Kimi 显示 `¥`；不做汇率折算。
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
    symbol = currency_symbol(model_currency(model))
    if cost < 0.01:
        return f"{symbol}{cost:.4f}"
    return f"{symbol}{cost:.3f}"
