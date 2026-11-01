"""LLM 会话统计模块 — Token 用量累计、模块级用量记录。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from src.python.llm.pricing import add_cost, compute_cost_value, format_costs, model_currency

logger = logging.getLogger("invest")

__all__ = [
    "_session_usage",
    "_normalize_usage_tokens",
    "reset_session_usage",
    "get_session_usage",
    "format_session_usage",
    "track_session_usage",
    "record_per_module",
]

# ── 会话级 Token 用量累计跟踪 ──

_session_usage: dict[str, Any] = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cache_hit_tokens": 0,
    "costs": {},
    "model": "未指定",
    "models": [],
    "call_count": 0,
    "per_module": {},
}
"""会话期间所有 LLM 调用的累计 Token 用量和费用。
per_module: {module_key: {"model": str, "input_tokens": int, "output_tokens": int,
                           "cached": bool, "thinking": bool, "costs": {币种: 金额}}}

``costs`` 是「币种 → 金额」桶：不同模型可能以不同货币标价（DeepSeek/Kimi 为 CNY，
Claude/GPT/Gemini 为 USD），跨币种**从不相加**，展示时分组并列。
生成报告后可在 TUI/汇总页展示。"""

# 线程锁：_session_usage 被 ThreadPoolExecutor（LLM 并行生成）从多线程写入
_session_lock = threading.Lock()


def reset_session_usage() -> None:
    """重置会话累计用量（新会话开始时调用）。"""
    with _session_lock:
        _session_usage["input_tokens"] = 0
        _session_usage["output_tokens"] = 0
        _session_usage["cache_hit_tokens"] = 0
        _session_usage["costs"] = {}
        _session_usage["call_count"] = 0
        _session_usage["per_module"] = {}
        _session_usage["models"] = []


def get_session_usage() -> dict[str, Any]:
    """返回会话累计用量字典的副本（供 TUI/报告展示）。"""
    with _session_lock:
        return dict(_session_usage)


def format_session_usage(raw: dict[str, Any] | None) -> dict[str, Any]:
    """将 get_session_usage() 的原始 dict 格式化为报告展示用的 dict。

    输出字段：
      has_usage    — bool，是否有实际调用
      call_count   — 调用次数
      model        — 模型名
      input_tokens — 输入 token 数
      output_tokens
      total_tokens — 输入+输出合计数
      cache_hit_tokens
      cost_by_currency — 「币种 → 金额」桶（跨币种不相加）
      cost_display     — 分币种并列展示串（如 "¥0.0456 + $0.0021"）
    """
    if not raw:
        return {"has_usage": False}
    # 即使 call_count 为 0（全缓存场景），只要 per_module 有数据就视为有用量
    if not raw.get("call_count", 0) and not raw.get("per_module"):
        return {"has_usage": False}
    inp = raw.get("input_tokens", 0)
    out = raw.get("output_tokens", 0)
    cache_hit = raw.get("cache_hit_tokens", 0)
    costs = dict(raw.get("costs") or {})
    models = raw.get("models", [])
    models = [m for m in models if m and m != "未指定"]
    model_display = " / ".join(models) if models else raw.get("model", "未指定")
    return {
        "has_usage": True,
        "call_count": raw.get("call_count", 0),
        "model": raw.get("model", "未指定"),
        "models": models,
        "model_display": model_display,
        "per_module": raw.get("per_module", {}),
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cache_hit_tokens": cache_hit,
        "cost_by_currency": costs,
        "cost_display": format_costs(costs),
    }


def _normalize_usage_tokens(provider: str, usage: dict | None) -> tuple[int, int, int]:
    """把 provider 原始 usage 归一为 ``(input, output, cache_hit)``。

    统一契约：``input`` 为**总输入**（含缓存命中部分），``cache_hit`` 是其子集，
    下游 ``cache_miss = input - cache_hit`` 恒非负。

    - ``claude`` 协议（含 DeepSeek/Kimi Anthropic 兼容端点）：``input_tokens``
      仅计缓存未命中部分，补上 ``cache_read_input_tokens`` 归一为总输入；
    - 其余协议（``openai`` 原生；``gemini`` 经 ``usageMetadata`` 归一形）：
      ``prompt_tokens`` / ``completion_tokens`` 本身含命中部分；缓存命中优先读
      DeepSeek 原生端点顶层 ``prompt_cache_hit_tokens``，回退
      ``prompt_tokens_details.cached_tokens``（字段缺失或为空时为 0）。

    ``api_base._log_token_usage`` 与本模块 ``track_session_usage`` 共用本函数
    ——两处计量口径由结构保证一致，而非靠两份分支逐字对齐。
    """
    if not usage:
        return (0, 0, 0)
    if provider == "claude":
        # input_tokens 不含命中 → 归一为 input_tokens + cache_read（总量口径）
        cache_hit = usage.get("cache_read_input_tokens", 0) or 0
        return (
            (usage.get("input_tokens", 0) or 0) + cache_hit,
            usage.get("output_tokens", 0) or 0,
            cache_hit,
        )
    hit = usage.get("prompt_cache_hit_tokens")
    if hit is None:
        hit = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    return (
        usage.get("prompt_tokens", 0) or 0,
        usage.get("completion_tokens", 0) or 0,
        hit or 0,
    )


def track_session_usage(provider: str, usage: dict | None, model_name: str = "") -> None:
    """将一次 LLM 调用的用量累计到会话统计。"""
    global _session_usage
    if not usage:
        return
    inp, out, cache_hit = _normalize_usage_tokens(provider, usage)
    with _session_lock:
        _session_usage["input_tokens"] += inp
        _session_usage["output_tokens"] += out
        _session_usage["cache_hit_tokens"] += cache_hit
        _session_usage["call_count"] += 1
        if model_name:
            _session_usage["model"] = model_name
            if model_name not in _session_usage["models"]:
                _session_usage["models"].append(model_name)

        # 累计费用：按该模型官方币种入桶（跨币种不相加）
        cost_val = compute_cost_value(model_name, inp, out, cache_hit_input_tokens=cache_hit)
        if cost_val:
            add_cost(_session_usage["costs"], model_currency(model_name), cost_val)


def record_per_module(
    module_key: str,
    model_name: str,
    inp: int = 0,
    out: int = 0,
    cached: bool = False,
    thinking: bool = False,
    cost: float = 0.0,
    endpoint: str = "",
    cache_hit_tokens: int = 0,
    duration: float = 0.0,
) -> None:
    """按模块记录本次 LLM 调用的模型、Token 用量、耗时、缓存/Thinking/费用/Endpoint。"""
    with _session_lock:
        pm = _session_usage.setdefault("per_module", {})
        if module_key not in pm:
            pm[module_key] = {
                "model": model_name,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached": cached,
                "thinking": thinking,
                "costs": {},
                "endpoint": endpoint,
                "cache_hit_tokens": 0,
                "duration": 0.0,
            }
        entry = pm[module_key]
        entry["input_tokens"] += inp
        entry["output_tokens"] += out
        if cost:
            add_cost(entry.setdefault("costs", {}), model_currency(model_name), cost)
        entry["cache_hit_tokens"] += cache_hit_tokens
        entry["duration"] += duration
        if model_name:
            entry["model"] = model_name
        if endpoint:
            entry["endpoint"] = endpoint
        if cached:
            entry["cached"] = True
        elif inp or out or cost:
            # 本次真的调用了（有 token/费用）：盖掉会话里先前的命中标记，
            # 否则同一会话的后续报告会把它继续显示成「使用缓存」
            entry["cached"] = False
        if thinking:
            entry["thinking"] = True
        if model_name and model_name not in _session_usage["models"]:
            _session_usage["models"].append(model_name)
