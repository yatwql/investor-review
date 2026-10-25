"""llm_pricing_ref.json — 计价参考数据（策略 + 模型单价覆盖）。

参考数据不是用户开关：不进 TUI/Web 配置面板；改价直接编辑文件。
合并口径：内置 `constants.MODEL_PRICING` 为基础价，本文件逐模型覆盖**出现的字段**
（`input_price` / `output_price` / `input_cache_hit` / `peak.*`），未出现的字段继承内置值。

缺失 → 仅用内置价；单个模型条目非法 → 告警并跳过；`version` 不符 → 拒绝加载并提示重新生成。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from src.python.core.constants import (
    MODEL_PRICING,
    PRICING_HOLIDAY_ALWAYS_IDLE,
    PRICING_IDLE_PERIODS,
    PRICING_PEAK_PERIODS,
    PRICING_TIMEZONE,
    PRICING_WEEKEND_ALWAYS_IDLE,
    PROJECT_ROOT,
)
from src.python.core.json_comments import loads

logger = logging.getLogger("invest")

PRICING_SCHEMA_VERSION = 1
PRICING_FILE = os.path.join(PROJECT_ROOT, "data/config/llm_pricing_ref.json")

#: 缓存：(path, mtime, size) → (models, policy)
_cache: tuple[tuple[str, float, int], dict[str, Any]] | None = None


class LLMPricingError(ValueError):
    """计价参考文件结构/版本不可用（附文件名与重新生成指引）。"""


def get_llm_pricing_path() -> str:
    """返回计价参考文件路径（绝对路径，项目根基准）。"""
    return PRICING_FILE


def invalidate_pricing_cache() -> None:
    global _cache
    _cache = None


# ── 默认策略与生成器 ──────────────────────────────────────────


def _default_policy() -> dict[str, Any]:
    return {
        "currency": "CNY",
        "timezone": PRICING_TIMEZONE,
        "peak_periods": list(PRICING_PEAK_PERIODS),
        "idle_periods": list(PRICING_IDLE_PERIODS),
        "weekend_always_idle": bool(PRICING_WEEKEND_ALWAYS_IDLE),
        "holiday_always_idle": bool(PRICING_HOLIDAY_ALWAYS_IDLE),
    }


def _minutes_to_clock(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _periods_as_text(periods: list[tuple[int, int]]) -> str:
    return "[" + ", ".join(f'"{_minutes_to_clock(a)}-{_minutes_to_clock(b)}"' for a, b in periods) + "]"


def render_default_pricing_ref() -> str:
    """生成带中文注释的默认计价参考文件（策略 + 空 models 覆盖表）。"""
    policy = _default_policy()
    return f"""// 计价参考数据（llm_pricing_ref.json）
// 参考数据不是用户开关：不进 TUI/Web 配置面板；改价直接编辑本文件。
// 合并口径：constants.py 的 MODEL_PRICING 为基础价，本文件 models 逐模型覆盖
// 出现的字段，未出现的字段继承内置值。文件缺失时仅用内置价。
// 单位：元 / 百万 token（CNY）。外币厂商（Anthropic/OpenAI/Google）的官方 USD 价
// 已在 constants.py 内经 USD_CNY_RATE 折算，本文件覆盖时同样填人民币值。
{{
  "version": {PRICING_SCHEMA_VERSION},   // 结构版本；不符即拒绝加载并提示重新生成
  "currency": "{policy["currency"]}",   // 货币标识（影响费用符号）
  "timezone": "{policy["timezone"]}",   // 峰谷判定时区（IANA 名称）
  "peak_periods": {_periods_as_text(policy["peak_periods"])},   // 高峰时段（HH:MM-HH:MM，闭区间）
  "idle_periods": {_periods_as_text(policy["idle_periods"])},   // 闲时时段（空 = 高峰之外均闲时）
  "weekend_always_idle": {str(policy["weekend_always_idle"]).lower()},   // 周末全天按闲时价
  "holiday_always_idle": {str(policy["holiday_always_idle"]).lower()},   // 法定节假日全天按闲时价
  "models": {{
    // 逐模型覆盖示例（单位：元 / 百万 token；未写字段继承内置价）：
    // "deepseek-flash": {{"input_price": 1.0, "output_price": 4.0,
    //                     "peak": {{"input_price": 2.0, "output_price": 8.0}}}},
    // "claude-sonnet-5-5": {{"input_price": 13.44, "output_price": 67.2}}
  }}
}}
"""


def ensure_llm_pricing_file(path: str | None = None) -> bool:
    """文件缺失时原子写入默认模板（已存在则不动）。返回是否新建。"""
    target = path or get_llm_pricing_path()
    if os.path.exists(target):
        return False
    from src.python.core.atomic_write import write_text_atomic

    os.makedirs(os.path.dirname(target), exist_ok=True)
    return write_text_atomic(
        target, render_default_pricing_ref(), prefix=".pricing_", log_tag="pricing", noun="计价参考"
    )


# ── 读取 / 校验 / 合并 ────────────────────────────────────────


def _coerce_price(value: Any) -> float | None:
    """价格字段：非负数才合法；bool/str/负数/NaN 一律非法。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number < 0 or number != number:  # NaN
        return None
    return number


_REF_PRICE_KEYS = {
    "input_price": "input",
    "output_price": "output",
    "input_cache_hit": "input_cache_hit",
}


def _merge_model(entry: Any, model: str) -> dict[str, float] | None:
    """合并单个模型条目；非法返回 None（调用方告警跳过）。"""
    if not isinstance(entry, dict):
        logger.warning("[pricing] %s 的条目不是 JSON 对象，已跳过", model)
        return None
    base = dict(MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0, "input_cache_hit": 0.0}))
    merged: dict[str, Any] = dict(base)

    for ref_key, runtime_key in _REF_PRICE_KEYS.items():
        if ref_key not in entry:
            continue
        price = _coerce_price(entry[ref_key])
        if price is None:
            logger.warning("[pricing] %s.%s 不是合法非负数值（%r），已跳过该字段", model, ref_key, entry[ref_key])
            continue
        merged[runtime_key] = price

    peak = entry.get("peak")
    if peak is not None:
        if not isinstance(peak, dict):
            logger.warning("[pricing] %s.peak 不是 JSON 对象，已忽略", model)
        else:
            existing_peak = dict(merged.get("peak") or {})
            for ref_key, runtime_key in _REF_PRICE_KEYS.items():
                if ref_key not in peak:
                    continue
                price = _coerce_price(peak[ref_key])
                if price is None:
                    logger.warning("[pricing] %s.peak.%s 不是合法非负数值，已跳过", model, ref_key)
                    continue
                existing_peak[runtime_key] = price
            if existing_peak:
                existing_peak.setdefault("input", merged["input"])
                existing_peak.setdefault("output", merged["output"])
                existing_peak.setdefault("input_cache_hit", merged.get("input_cache_hit", existing_peak["input"]))
                merged["peak"] = existing_peak
    return merged


def _merged_models(ref: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    merged = {model: dict(prices) for model, prices in MODEL_PRICING.items()}
    models = (ref or {}).get("models") or {}
    if not isinstance(models, dict):
        logger.warning("[pricing] models 段应为 JSON 对象，已忽略")
        return merged
    for model, entry in models.items():
        result = _merge_model(entry, model)
        if result is not None:
            merged[model] = result
    return merged


def _parse_periods(value: Any) -> list[tuple[int, int]] | None:
    """把 "HH:MM-HH:MM" 列表解析为分钟闭区间；非法返回 None。"""
    if not isinstance(value, list):
        return None
    periods: list[tuple[int, int]] = []
    for item in value:
        if not isinstance(item, str) or "-" not in item:
            return None
        try:
            start_text, end_text = item.split("-", 1)
            sh, sm = (int(part) for part in start_text.split(":", 1))
            eh, em = (int(part) for part in end_text.split(":", 1))
        except (ValueError, TypeError):
            return None
        if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
            return None
        periods.append((sh * 60 + sm, eh * 60 + em))
    return periods


def _policy_from_ref(ref: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    merged = dict(policy)
    if isinstance(ref.get("currency"), str) and ref["currency"].strip():
        merged["currency"] = ref["currency"].strip().upper()
    if isinstance(ref.get("timezone"), str) and ref["timezone"].strip():
        merged["timezone"] = ref["timezone"].strip()
    parsed = _parse_periods(ref.get("peak_periods"))
    if parsed is not None:
        merged["peak_periods"] = parsed
    elif ref.get("peak_periods") is not None:
        logger.warning("[pricing] peak_periods 格式非法，沿用默认时段")
    parsed_idle = _parse_periods(ref.get("idle_periods"))
    if parsed_idle is not None:
        merged["idle_periods"] = parsed_idle
    elif ref.get("idle_periods") is not None:
        logger.warning("[pricing] idle_periods 格式非法，沿用默认时段")
    for flag in ("weekend_always_idle", "holiday_always_idle"):
        if isinstance(ref.get(flag), bool):
            merged[flag] = ref[flag]
        elif ref.get(flag) is not None:
            logger.warning("[pricing] %s 应为布尔值，沿用默认", flag)
    return merged


def load_pricing_config() -> dict[str, Any]:
    """读取计价参考并返回 ``{models, currency, timezone, peak_periods, idle_periods, ...}``。

    文件缺失 → 仅内置价；版本不符 → 记录错误并回退内置价（不阻断报告生成）。
    mtime+size 命中时复用缓存。
    """
    global _cache
    path = get_llm_pricing_path()
    policy = _default_policy()
    try:
        stat = os.stat(path)
    except OSError:
        return {"models": {m: dict(p) for m, p in MODEL_PRICING.items()}, **policy}
    key = (path, stat.st_mtime, stat.st_size)
    if _cache is not None and _cache[0] == key:
        return _cache[1]

    try:
        with open(path, encoding="utf-8-sig") as f:
            ref = loads(f.read())
        if not isinstance(ref, dict):
            raise LLMPricingError("llm_pricing_ref.json 根元素不是 JSON 对象")
        version = ref.get("version")
        if version != PRICING_SCHEMA_VERSION:
            raise LLMPricingError(
                f"llm_pricing_ref.json 的 version={version!r}，本版本只接受 {PRICING_SCHEMA_VERSION}；"
                "请删除该文件后重新生成（程序会按模板重建）"
            )
        config = {"models": _merged_models(ref), **_policy_from_ref(ref, policy)}
    except LLMPricingError as e:
        logger.error("[pricing] [ERR] %s；已回退内置价", e)
        config = {"models": {m: dict(p) for m, p in MODEL_PRICING.items()}, **policy}
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("[pricing] 计价参考读取失败: %s；已回退内置价", e)
        config = {"models": {m: dict(p) for m, p in MODEL_PRICING.items()}, **policy}

    _cache = (key, config)
    return config
