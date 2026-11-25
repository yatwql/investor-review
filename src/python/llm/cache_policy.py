"""LLM 缓存复用策略 —— 「这次能不能复用」的唯一判定点。

指纹回答「输入变了吗」、TTL 回答「缓存还能用多久」，本模块回答**能不能用**：
行情口径桶为盘中档时（交易日 09:30–11:30 / 13:00–15:00），行情还在逐分钟变，
复用上一轮的盘中结论会让读者拿到十分钟前的判断，故一律跳过缓存读（照常写）。

为什么要单独成模块：预检（四个基础模块）与骨架（预检之后才确定键的
`self_review` / `holding_change` 等）两条路径都要同一套判定与归因——各写一份时
「拦一处漏一处」会让基础模块重算、后置模块却复用旧盘中结论，且日志/归因口径分离。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.core import market_hours
from src.python.llm.observation import RECOMPUTE_INTRADAY_NO_REUSE

logger = logging.getLogger("invest")

__all__ = [
    "PRICE_INDEPENDENT_MODULES",
    "is_price_sensitive_module",
    "intraday_reuse_blocked",
    "previous_module_key",
    "key_changed_from_baseline",
]

#: 指纹与持仓产品**价格无关**的模块 —— LLM 指纹分两类的唯一事实来源。
#:
#: 判据是「结论是否随标的价格变化」：
#:   - 价格无关：`global_macro`（全球政经局势，看宏观与组合构成）、`news_correlation`
#:     （财经热点关联，看新闻涉不涉及持有的品种/行业）。它们的键里只留结构（品种/代码/
#:     成本/分类/申购限购约束），既不带行情口径桶后缀，也不受盘中「价格还在变」影响。
#:   - 其余（`expert_review` / `health_check` / `penetration_deep` / 生成后自检 /
#:     持仓变动复盘 / 辩论三键）一律按**价格相关**对待：键含价格派生块（风险信号、
#:     市值/盈亏差、穿透占比），故带行情口径桶后缀，盘中档不复用。
#:
#: 保守方向：新模块默认归入价格相关——误判成相关的代价只是多算一次，误判成无关
#: 会复用按旧价格生成的结论。
PRICE_INDEPENDENT_MODULES: frozenset[str] = frozenset({"global_macro", "news_correlation"})


def is_price_sensitive_module(module_key: str) -> bool:
    """该模块的结论是否随持仓产品价格变化（即其指纹里是否含价格派生块）。"""
    return module_key not in PRICE_INDEPENDENT_MODULES


def intraday_reuse_blocked(module_key: str, sink: Any = None) -> bool:
    """该模块本次是否因「盘中档」而不复用缓存。

    命中时一并留日志与归因（`intraday_no_reuse`），调用方只需据此跳读缓存。

    Args:
        module_key: 模块标识（日志/归因用；空串时回落到调用方键名由调用方传入）
        sink: 观测汇聚器（可 None）。提供 `note_cache` / `note_recompute_reason` 即记录。

    Returns:
        True 表示本轮不复用该模块缓存。
    """
    # 经模块属性取值：单测按需替换判定源（直接 from-import 会把绑定固定在此处）
    if not is_price_sensitive_module(module_key):
        # 价格无关模块：结论不随报价变化，盘中复用是安全的（也就不用为它白算一次）
        return False
    bucket = market_hours.market_snapshot_bucket()
    if not bucket.intraday:
        return False
    logger.info("[LLM] %s 盘中档不复用缓存（%s）", module_key or "未指定", bucket.label)
    if sink is not None:
        if hasattr(sink, "note_cache"):
            sink.note_cache(False)
        if hasattr(sink, "note_recompute_reason"):
            sink.note_recompute_reason(module_key or "未指定", RECOMPUTE_INTRADAY_NO_REUSE)
    return True


def previous_module_key(module_key: str, in_process_key: str = "") -> str:
    """上一轮该模块的缓存键（跨报告基线优先，无基线时回落本进程记录；两者皆无返回空串）。

    这是「与上一轮比对」的唯一取数点，预检（四个基础模块）与生成骨架（`self_review` /
    `holding_change` 等在上游产出后才定键的后置模块）共用：报告边界会清空进程内记录，
    只有跨报告基线能回答「这一轮相对上一份报告换键了吗」；各写一份必然出现
    「预检判 ttl_expired、骨架判 cache_miss」的口径分裂。

    Args:
        module_key: 模块标识。
        in_process_key: 调用方手里的本进程记录（可为空串）；骨架侧须传**赋值前**的值。

    Returns:
        上一轮键；无任何基线时为空串（调用方据此判冷启动）。
    """
    from src.python.llm.fingerprint_baseline import baseline_module_key

    return baseline_module_key(module_key) or str(in_process_key or "")


def key_changed_from_baseline(current_key: str, module_key: str, in_process_key: str = "") -> bool | None:
    """该模块当前的缓存键相对上一轮是否变化。

    Returns:
        ``True`` 键变了（输入变）；``False`` 键未变（内容没变，只是老化）；
        ``None`` 无任何上轮基线（冷启动，不臆测原因）。
    """
    prev_key = previous_module_key(module_key, in_process_key)
    if not prev_key:
        return None
    return prev_key != current_key
