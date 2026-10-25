"""LLM 费用「币种 → 金额」桶的读取与合并（core 层，供 core/perf 与 llm/report 共用）。

为什么放在 core：`core/perf.py` 汇总历史费用时需要读同一份桶结构，而 core 不得反向
import 上层（`llm.pricing`）。把该读写规则下沉到这里，两层共用同一实现，避免两处
各写一份「标量 → 桶」的兼容规则。

桶结构约定（perf 记录、session per_module、报告上下文一致）：

- 新记录：``{"costs": {"CNY": 0.02, "USD": 0.005}}``（跨币种不相加）
- 旧记录：``{"cost": 0.02, "currency": "CNY"}``（标量 + 币种，读时折算成单币种桶）
"""

from __future__ import annotations

from src.python.core.constants import PRICING_DEFAULT_CURRENCY


def costs_of(entry: dict | None) -> dict[str, float]:
    """从一条用量/历史条目读出「币种 → 金额」桶（零值桶丢弃）。"""
    data = entry or {}
    buckets = data.get("costs")
    if isinstance(buckets, dict):
        return {str(code).upper(): float(amount or 0.0) for code, amount in buckets.items() if float(amount or 0.0)}
    legacy = float(data.get("cost") or 0.0)
    if not legacy:
        return {}
    code = str(data.get("currency") or PRICING_DEFAULT_CURRENCY).upper()
    return {code: legacy}


def add_cost_bucket(target: dict[str, float], source: dict[str, float]) -> dict[str, float]:
    """把来源桶累加进目标桶（就地更新，同币种相加、异币种并存）。"""
    for code, amount in (source or {}).items():
        code = str(code).upper()
        target[code] = target.get(code, 0.0) + float(amount or 0.0)
    return target
