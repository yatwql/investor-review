"""LLM 批量编排门面 — 缓存预检查、线程池分发与 LLM 全量生成。

本文件为聚合门面：
  - 新闻关联安全直调入口 → `_llm_news_correlation.py`（该模块不经本门面的线程池，
    运行路径见其模块文档）
  - worker 装配与线程池并发分发 → `_llm_dispatch.py`（`_build_module_fns` /
    `_dispatch_llm_workers` / `_LLM_CLIENT_SETTINGS`；本门面 re-export
    `_dispatch_llm_workers`，`generate_all_llm` 在门面内消费它）
门面保留缓存预检（`_compute_module_cache_info`/`_precheck_*`）与主编排入口
（`generate_all_llm`）——其内部经门面命名空间解析被 mock patch 的辅助符号
（`cache_get`、`run_fact_check`、`get_llm_config` 等），并 re-export 子模块符号。

新增 LLM 模块需在 ``_llm_dispatch._build_module_fns`` 中添加条目，无需深入分发函数。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any


from src.python.cache import get as cache_get
from src.python.config import get_llm_config, get_llm_setting_default
from src.python.llm.api_base import (
    _build_cache_hint_and_record,
)
from src.python.llm.fingerprint import get_cache_ttl_llm
from src.python.llm.module_fingerprint import (
    ModuleFingerprintInputs,
    expert_review_fingerprint,
    global_macro_fingerprint,
    health_check_fingerprint,
    penetration_deep_fingerprint,
)
from src.python.llm.prompts import (
    CACHE_PREFIX_LLM,
    FAIL_REASON_DISABLED,
    LLM_MODULE_FAILURE,
)
from src.python.llm.skeleton import _build_provider_cache_key, is_llm_module_enabled
from src.python.core.registry import get_llm_module_name, get_llm_module_names

logger = logging.getLogger("invest")
_MN = get_llm_module_name

#: 上一次报告的指纹组件哈希（仅排障：连续两次报告对比变化来源；空=首次运行）
_LAST_FP_COMPONENTS: dict[str, str] | None = None


def reset_fingerprint_audit() -> None:
    """清空指纹组件审计基线（进程内新会话/测试隔离用）。"""
    global _LAST_FP_COMPONENTS
    _LAST_FP_COMPONENTS = None


# ── 子模块 re-export ──────────────────────────────────────
# news_correlation 安全直调入口在 `_llm_news_correlation.py` 中实现，此处 re-export。
from src.python.llm._llm_context_blocks import (  # noqa: F401  # 上下文块装配子模块（本门面 re-export 提取器）
    LlmContextBlocks,
    build_context_blocks,
    extract_event_impact_block,
    extract_historical_codes,
    extract_holding_change_block,
    extract_purchase_constraint_block,
    extract_schedule_replay_block,
)
from src.python.llm._llm_post_pass import (  # noqa: F401  # 生成后一遍（锚定/自检/跨模块核对）
    BASE_MODULES,
    anchor_fact_checks,
    apply_generation_post_pass,
    contents_from_results,
)
from src.python.llm._llm_dispatch import (  # noqa: F401  # 并发分发子模块（消费方在本门面）
    _dispatch_llm_workers,
    reset_thinking_wait_total,
    thinking_wait_total_seconds,
)
from src.python.llm._llm_news_correlation import (  # noqa: F401
    run_news_correlation_safe,
)


__all__ = [
    "_compute_module_cache_info",
    "_precheck_one_cache",
    "_precheck_all_modules",
    "_dispatch_llm_workers",
    "extract_holding_change_block",
    "extract_event_impact_block",
    "extract_schedule_replay_block",
    "generate_all_llm",
    "run_news_correlation_safe",
]


def _compute_module_cache_info(
    llm_config: dict,
    a_indices,
    us_indices,
    total_mv: float,
    total_cost: float,
    total_profit: float,
    total_today_profit: float,
    _holdings_count: int,
    categories: dict,
    penetrated_assets: list[dict] | None,
    holdings_details: list[dict] | None,
    force: bool,
    force_modules: Iterable[str] | None = None,
    *,
    history_data: dict | None = None,
    pipeline_data: dict | None = None,
    competitive_context: str = "",
    metrics: dict | None = None,
    data_quality_text: str = "",
    purchase_constraint_block: str = "",
    holding_change_block: str = "",
    event_impact_block: str = "",
    schedule_replay_block: str = "",
) -> dict[str, dict]:
    """预计算各模块指纹/缓存键/TTL/可缓存性，返回数据结构。

    指纹一律取自 ``llm/module_fingerprint.py``（读写同源的唯一事实来源），
    本函数**不再自行拼接**模块指纹——预检键与写侧键同源由结构保证，
    而非靠两侧逐字对齐的注释纪律（历史偏差见该模块 docstring）。

    ``competitive_context`` / ``metrics`` / ``data_quality_text`` 是提示词正文段的
    输入（详见 ``llm/module_fingerprint.py``）：本函数只对**调用方已渲染好**的
    同一实例取哈希，不自行渲染——两次渲染会让「进键的文本」与「进提示词的文本」
    脱钩。
    """
    _inputs = ModuleFingerprintInputs(
        total_mv=total_mv,
        total_cost=total_cost,
        total_profit=total_profit,
        total_today_profit=total_today_profit,
        holdings_details=holdings_details,
        penetrated_assets=penetrated_assets,
        categories=categories,
        history_data=history_data,
        pipeline_data=pipeline_data,
        a_indices=a_indices,
        us_indices=us_indices,
        competitive_context=competitive_context,
        metrics=metrics,
        data_quality_text=data_quality_text,
        purchase_block=purchase_constraint_block or "",
        holding_change_block=holding_change_block or "",
        event_impact_block=event_impact_block or "",
        schedule_replay_block=schedule_replay_block or "",
    )
    # 组件级指纹审计：**变化定位恒开**（每份报告一行 INFO，默认配置就能回答「为什么又 miss」），
    # 逐组件哈希快照只在 DEBUG 下打（纯排障，正式路径零额外开销）。
    global _LAST_FP_COMPONENTS
    from src.python.llm.module_fingerprint import (
        diff_fingerprint_components,
        fingerprint_components,
    )

    _components = fingerprint_components(_inputs)
    # 基线优先取进程内上轮快照；同进程多份报告（TUI 连续生成）走这条路。
    # 进程重启后回落读上次进程落盘的基线——否则键变了也只能归因成 ttl_expired，
    # 「哪一段输入变了」无从回答（诊断输入，缺基线即冷启动，不做任何推断）。
    from src.python.llm.fingerprint_baseline import baseline_components

    _prev_components = _LAST_FP_COMPONENTS or baseline_components()
    _baseline_source = "上次报告" if _LAST_FP_COMPONENTS else "上次进程"
    if _prev_components:
        _changed = diff_fingerprint_components(_prev_components, _components)
        if _changed:
            logger.info("[fingerprint] 指纹组件变化（相对%s）: %s", _baseline_source, _changed)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("[fingerprint] 组件哈希: %s", _components)
    _LAST_FP_COMPONENTS = _components

    fp_global_macro = global_macro_fingerprint(_inputs)
    fp_expert_review = expert_review_fingerprint(_inputs)
    fp_health_check = health_check_fingerprint(_inputs)
    fp_penetration_deep = penetration_deep_fingerprint(_inputs)

    # 缓存键必须与**写侧**逐字节相同：chain 模式下写侧（``skeleton`` 的
    # ``_build_provider_cache_key``）会在裸键后追加 ``_{provider_name}``。预检
    # 不追加时读的是「短键」——文件永远不存在，于是每份报告四模块全判 miss、
    # 全量派发进线程池（真正命中发生在 skeleton 的第二次预检），并虚报
    # ``cache_misses``。同源由本函数的统一追加保证，不靠两侧各自拼。
    def _key(module_key: str, fingerprint: str) -> str:
        return _build_provider_cache_key(CACHE_PREFIX_LLM + f"{module_key}_{fingerprint}", llm_config, module_key)

    force_flag = force
    _forced = force_modules if force_modules is not None else frozenset()
    info: dict[str, dict] = {
        "global_macro": {
            "key": _key("global_macro", fp_global_macro),
            "ttl": get_cache_ttl_llm("global_macro"),
            "can_cache": not (force_flag or "global_macro" in _forced)
            and llm_config.get("cache_enabled_global_macro", get_llm_setting_default("cache_enabled_global_macro")),
            "thinking_key": "thinking_enabled_global_macro",
        },
        "expert_review": {
            "key": _key("expert_review", fp_expert_review),
            "ttl": get_cache_ttl_llm("expert_review"),
            "can_cache": not (force_flag or "expert_review" in _forced)
            and llm_config.get("cache_enabled_expert_review", get_llm_setting_default("cache_enabled_expert_review")),
            "thinking_key": "thinking_enabled_expert_review",
        },
        "health_check": {
            "key": _key("health_check", fp_health_check),
            "ttl": get_cache_ttl_llm("health_check"),
            "can_cache": not (force_flag or "health_check" in _forced)
            and llm_config.get("cache_enabled_health_check", get_llm_setting_default("cache_enabled_health_check")),
            "thinking_key": "thinking_enabled_health_check",
        },
        "penetration_deep": {
            "key": _key("penetration_deep", fp_penetration_deep),
            "ttl": get_cache_ttl_llm("penetration_deep"),
            "can_cache": not (force_flag or "penetration_deep" in _forced)
            and llm_config.get(
                "cache_enabled_penetration_deep", get_llm_setting_default("cache_enabled_penetration_deep")
            ),
            "thinking_key": "thinking_enabled_penetration_deep",
        },
    }
    return info


def _key_changed_from_baseline(current_key: str, module_key: str) -> bool | None:
    """该模块当前的缓存键相对**上轮键**是否变化（进程内优先，其次跨进程快照）。

    Returns:
        ``True`` 键变了（输入变）；``False`` 键未变（只是内容读不到 ⇒ 老化）；
        ``None`` 无任何上轮基线（冷启动，不臆测原因）。
    """
    from src.python.llm.fingerprint_baseline import baseline_module_key
    from src.python.llm.skeleton import module_cache_key

    prev = module_cache_key(module_key) or baseline_module_key(module_key)
    if not prev:
        return None
    return prev != current_key


def _recompute_reason(cache_info: dict, fingerprint_changed: bool | None) -> str:
    """未命中原因：强制刷新 / 指纹变化 / 纯 TTL 到点 / 冷启动（取值来自 ``RECOMPUTE_REASONS``）。"""
    from src.python.llm.observation import (
        RECOMPUTE_CACHE_MISS,
        RECOMPUTE_FINGERPRINT_CHANGED,
        RECOMPUTE_FORCED,
        RECOMPUTE_TTL_EXPIRED,
    )

    if not cache_info.get("can_cache", True):
        return RECOMPUTE_FORCED
    if fingerprint_changed is None:
        return RECOMPUTE_CACHE_MISS
    return RECOMPUTE_FINGERPRINT_CHANGED if fingerprint_changed else RECOMPUTE_TTL_EXPIRED


def _note_recompute_reason(sink, module_key: str, reason: str) -> None:
    """把重算原因记入观测汇聚器（无汇聚器时静默跳过，不增加任何调用）。"""
    if sink is None or not hasattr(sink, "note_recompute_reason"):
        return
    sink.note_recompute_reason(module_key, reason)


def _precheck_one_cache(
    cache_info: dict,
    llm_config: dict,
    module_key: str = "",
) -> tuple[str | None, bool]:
    """预检单个模块的缓存，返回 (result, from_cached)。

    缓存命中时同时记录模块用量（_record_per_module），
    确保 LLM API 用量页签能正确显示"缓存"状态。
    """
    if not cache_info["can_cache"]:
        # 重新生成/强制刷新路径不读缓存，且不参与命中率统计——此处必须留一条 INFO：
        # 否则用户看到的是「全部模块又调了一次 LLM」，无法区分「缓存没命中」与「自己选了重新生成」。
        logger.info(
            "[LLM 预检] %s 跳过缓存读（重新生成/强制刷新范围内）",
            module_key or cache_info["key"],
        )
        return (None, False)
    from src.python.llm.cache_policy import intraday_reuse_blocked
    from src.python.llm.observation import current_llm_observation

    _sink = current_llm_observation()
    if intraday_reuse_blocked(module_key or cache_info["key"], _sink):
        return (None, False)

    cached = cache_get(cache_info["key"], cache_info["ttl"])
    if _sink is not None:
        _sink.note_cache(bool(cached))
    if not cached:
        # 重算原因归因（**观测**，不改变控制流）：知道「为什么没命中」才能回答
        # 「4h 的 TTL 到底卡掉了多少本该复用的调用」——内容真变了还是只是到点重算，
        # 直接决定 TTL 该不该放宽。
        # **判据以「键是否变化」为准**：键=生成输入的内容地址，键变即输入变；组件映射
        # 表只是解释用的细分（可能滞后于指纹函数的实际入参），单看它会把换键误报成 ttl_expired。
        # 基线先取进程内上轮键，再取上次进程落盘的键；两者皆无 ⇒ 冷启动（不臆测）。
        _module_key = module_key or cache_info["key"]
        _note_recompute_reason(
            _sink,
            _module_key,
            _recompute_reason(cache_info, _key_changed_from_baseline(cache_info["key"], _module_key)),
        )
        return (None, False)
    thinking_enabled = llm_config.get(cache_info["thinking_key"], False)
    # 当 endpoint 为空时有 provider chain 则尝试解析
    endpoint = llm_config.get("endpoint", "") or ""
    if not endpoint and llm_config.get("_provider_list") and module_key:
        from src.python.llm.api import _resolve_first_provider_model_endpoint

        _, endpoint = _resolve_first_provider_model_endpoint(llm_config, module_key)
    augmented_html = _build_cache_hint_and_record(
        cached,
        module_key,
        llm_config,
        thinking_enabled,
        endpoint=endpoint,
    )
    return (augmented_html, True)


def _precheck_all_modules(
    llm_config: dict,
    cache_info: dict[str, dict],
    _force: bool,
) -> dict[str, dict]:
    """检查所有模块的状态（已禁用/缓存命中/缓存未命中）。"""
    results: dict[str, dict] = {}
    for module_key, info in cache_info.items():
        enabled = is_llm_module_enabled(llm_config, module_key)
        if not enabled:
            logger.info("%s LLM 分析已禁用（enabled_llm.%s = false）", _MN(module_key), module_key)
            LLM_MODULE_FAILURE[module_key] = FAIL_REASON_DISABLED
            results[module_key] = {"result": None, "cached": False}
            continue
        result, from_cache = _precheck_one_cache(info, llm_config, module_key)
        results[module_key] = {"result": result, "cached": from_cache}
    _log_precheck_summary(results, llm_config, cache_info)
    return results


def _plan_module_needs(llm_config: dict, precheck_results: dict) -> dict[str, bool]:
    """逐模块是否需要生成：缓存未命中 + 开关开启 + 深度档位收窄，再叠加两条路由规则。

    深度档位在逐模块开关之上**收窄**参与集合（brief ⊂ standard），不放大已关闭的模块。

    Args:
        llm_config: LLM 配置。
        precheck_results: 预检结果（`{module: {result, cached}}`）。

    Returns:
        `{module: 是否需要生成}`。
    """
    from src.python.config.features import is_feature_enabled
    from src.python.llm.depth_profile import depth_gate, resolve_depth_profile

    _depth = resolve_depth_profile()
    needs = {
        key: (value["result"] is None and depth_gate(is_llm_module_enabled(llm_config, key), key, _depth))
        for key, value in precheck_results.items()
    }

    # 辩论模式：强制不走标准 expert_review 缓存预检（辩论路由用独立的 pro/con/synthesis 键，
    # 与标准 expert_review 键不同，必须绕过标准预检）
    if is_feature_enabled("llm_debate_procon"):
        needs["expert_review"] = depth_gate(is_llm_module_enabled(llm_config, "expert_review"), "expert_review", _depth)

    # 持仓变动复盘归因并入并行批：只吃持仓变动契约、不依赖四模块产出，无串行后置必要；
    # 其单次 4~25s 若串行会完全叠加在 expert_review 之后的关键路径上。
    needs.setdefault("holding_change", True)
    return needs


def _log_precheck_summary(
    results: dict[str, dict],
    llm_config: dict,
    cache_info: dict[str, dict],
) -> None:
    """每份报告打一行缓存命中概况：命中/未命中分别哪些模块，未命中的是否因重新生成。

    为何需要：单人看报告时只能看到「这次又调了几次 LLM」，分不清是缓存真 miss
    还是自己选了重新生成；逐模条日志在别的模块里，一屏信息里拼不起来。
    """
    hits = [k for k, v in results.items() if v.get("cached")]
    misses = [k for k, v in results.items() if v.get("result") is None and k not in hits]
    bypassed = [k for k in misses if not (cache_info.get(k) or {}).get("can_cache", True)]
    real_misses = [k for k in misses if k not in bypassed]
    from src.python.llm.observation import current_llm_observation

    _sink = current_llm_observation()
    reasons = getattr(_sink, "recompute_reasons", lambda: {})() if _sink is not None else {}
    # 口径说明：本行只统计**四个基础模块**的预检结果。`self_review` /
    # `holding_change` 的键要等上游产出才确定，其命中与归因由骨架路径记录，
    # 汇总在 perf 的 `cache_hits/cache_misses` 里——故此处标注「基础模块」，
    # 避免把「4/4」误读为「本次运行没有任何 LLM 调用」。
    # 口径行：本轮按哪个行情快照判定复用（收盘档可复用、盘中档一律不复用）
    from src.python.core.market_hours import market_snapshot_bucket

    _bucket = market_snapshot_bucket()
    logger.info(
        "[LLM 预检] 行情口径：%s（桶 %s，%s）",
        _bucket.label,
        _bucket.key,
        "盘中不复用" if _bucket.intraday else "已完成时点可复用",
    )
    logger.info(
        "[LLM 预检] 基础模块命中 %d/%d：%s；未命中：%s；重新生成（跳过缓存）：%s；未命中原因：%s",
        len(hits),
        len(results),
        ", ".join(hits) or "无",
        ", ".join(real_misses) or "无",
        ", ".join(bypassed) or "无",
        ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())) or "无",
    )


def _plan_generation(
    llm_config: dict,
    *,
    force: bool,
    force_scope: frozenset[str],
    blocks: LlmContextBlocks,
    indices: tuple[dict, dict],
    totals: tuple[float, float, float, float],
    holdings_count: int,
    categories: dict,
    penetrated_assets: list[dict] | None,
    holdings_details: list[dict] | None,
    history_data: dict | None,
    pipeline_data: dict | None,
    metrics: dict | None,
) -> tuple[dict, dict, dict[str, bool]]:
    """缓存指纹 → 预检 → 逐模块 needs（缓存/开关/深度档位 + 辩论与持仓变动路由）。

    指纹侧与提示词侧传的是**同一批块实例**（`blocks.fingerprint_kwargs()`），
    这是「进提示词必进指纹」的机械保障。

    Returns:
        `(cache_info, precheck_results, needs)`。
    """
    a_indices, us_indices = indices
    total_mv, total_cost, total_profit, total_today_profit = totals
    cache_info = _compute_module_cache_info(
        llm_config,
        a_indices,
        us_indices,
        total_mv,
        total_cost,
        total_profit,
        total_today_profit,
        holdings_count,
        categories,
        penetrated_assets,
        holdings_details,
        force,
        force_modules=force_scope,
        history_data=history_data,
        pipeline_data=pipeline_data,
        metrics=metrics,
        **blocks.fingerprint_kwargs(),
    )
    precheck_results = _precheck_all_modules(llm_config, cache_info, force)
    return cache_info, precheck_results, _plan_module_needs(llm_config, precheck_results)


def _finalize_llm_run(
    contents: dict[str, str | None],
    cached: dict[str, bool],
    *,
    cache_info: dict,
    debate_info: dict | None,
    has_debate: bool,
) -> tuple:
    """收尾：打一行四模块完成情况、落盘跨进程指纹基线、按模式返回 8/9 元组。"""
    gm_r, er_r, hc_r, pd_r = (contents.get(key) for key in BASE_MODULES)
    gm_c, er_c, hc_c, pd_c = (cached.get(key, False) for key in BASE_MODULES)

    # 持仓变动复盘归因已并入并行批（`_MODULE_FNS["holding_change"]`）：它只吃持仓变动
    # 契约、不依赖四模块产出，串行后置只会把 4~25s 白加到关键路径上。契约缺席（开关关闭/
    # 准入未过）时内部直接跳过：不进 LLM、不写载体，报告归因块隐藏（双端同构）。
    logger.info(
        "LLM 生成完成: %s=%s, %s=%s, %s=%s, %s=%s",
        _MN("global_macro"),
        "OK" if gm_r else "跳过",
        _MN("expert_review"),
        "OK" if er_r else "跳过",
        _MN("health_check"),
        "OK" if hc_r else "跳过",
        _MN("penetration_deep"),
        "OK" if pd_r else "跳过",
    )
    # 落盘跨进程基线（组件哈希 + 各模块本轮缓存键）：下个进程据此判定「键变了还是只是老化」
    from src.python.llm.fingerprint_baseline import save_baseline

    save_baseline(
        _LAST_FP_COMPONENTS or {},
        {mk: str((info.get("key") or "")) for mk, info in (cache_info or {}).items() if isinstance(info, dict)},
    )
    if has_debate:
        return (gm_r, er_r, hc_r, pd_r, gm_c, er_c, hc_c, pd_c, debate_info)
    return (gm_r, er_r, hc_r, pd_r, gm_c, er_c, hc_c, pd_c)


def generate_all_llm(
    a_indices: dict[str, dict[str, Any]],
    us_indices: dict[str, dict[str, Any]],
    total_mv: float,
    total_cost: float,
    total_profit: float,
    total_today_profit: float,
    holdings_count: int,
    categories: dict,
    penetrated_assets: list[dict] | None = None,
    holdings_details: list[dict] | None = None,
    sector_flow: list[dict] | None = None,
    force: bool = False,
    force_modules: Iterable[str] | None = None,
    pipeline_data: dict | None = None,
    history_data: dict | None = None,
    metrics: dict | None = None,
    degradation_events: list[dict] | None = None,
    comparison_indices: dict[str, str] | None = None,
    span_recorder=None,
) -> (
    tuple[str | None, str | None, str | None, str | None, bool, bool, bool, bool]
    | tuple[str | None, str | None, str | None, str | None, bool, bool, bool, bool, dict | None]
):
    """并行生成全球政经局势 + 智囊团深度复盘 + 持仓体检报告 + 穿透深度分析。

    优化：
      - 调用 get_llm_config() 仅一次，避免各生成函数内部重复文件 I/O
      - 预计算指纹 + 缓存键，仅对缓存未命中的模块提交线程池任务
      - 缓存命中的模块直接读取内容，节省线程开销

    使用 ThreadPoolExecutor(max_workers=llm_config.llm_max_concurrency, 默认 3) 并发调用四个 LLM 生成任务。
    每个工作线程创建独立的 httpx.Client，避免全局共享连接池的线程安全问题。

    Args:
        pipeline_data: 组合历史走势时间维度上下文（含 diff 差异摘要），传递给 expert_review 和 health_check。
        history_data: 组合历史走势数据字典（含风险指标）。
        metrics: 量化指标字典，compute_all_metrics() 的输出。
        degradation_events: DegradationTracker.get_log() 输出。本函数将其渲染成数据质量
            详细状态块**一次**，同一实例既进 health_check 指纹又进其提示词——否则
            数据源恢复后仍会复用故障期间缓存的健康结论。
        comparison_indices: {代码: 名称} 对比指数池，用于竞争语境多指数对比。
        span_recorder: 逐模块耗时记录器（`LLM+新闻` 父阶段绑定）；
            只用于观测，None 时行为零变化。

    Returns:
        (global_macro_html, expert_review_html, health_check_html, penetration_deep_html,
         global_macro_cached, expert_review_cached, health_check_cached, penetration_deep_cached) 八元组
    """
    llm_config = get_llm_config()
    if llm_config is None:
        return (None, None, None, None, False, False, False, False)

    # 强刷范围归一：全局 force 与模块级 force_modules → 模块键集合（后续所有 force 判定
    # 均按「模块 ∈ 强刷集合」逐模块取值，未指定模块照常命中缓存）。
    from src.python.llm.force_scope import resolve_force_scope

    _force_scope = resolve_force_scope(force, force_modules)

    # 上下文块：渲染/提取一次，同一实例分别交「预检指纹」与「提示词分发」
    blocks = build_context_blocks(
        a_indices=a_indices,
        total_mv=total_mv,
        total_today_profit=total_today_profit,
        comparison_indices=comparison_indices,
        history_data=history_data,
        metrics=metrics,
        degradation_events=degradation_events,
        pipeline_data=pipeline_data,
    )

    cache_info, precheck_results, needs = _plan_generation(
        llm_config,
        force=force,
        force_scope=_force_scope,
        blocks=blocks,
        indices=(a_indices, us_indices),
        totals=(total_mv, total_cost, total_profit, total_today_profit),
        holdings_count=holdings_count,
        categories=categories,
        penetrated_assets=penetrated_assets,
        holdings_details=holdings_details,
        history_data=history_data,
        pipeline_data=pipeline_data,
        metrics=metrics,
    )

    # 辩论模式容器（用于闭包捕获 debate_info）
    _debate_info_container: list[dict | None] = [None]
    from src.python.config.features import is_feature_enabled

    _has_debate = is_feature_enabled("llm_debate_procon")

    worker_results = _dispatch_llm_workers(
        needs,
        llm_config,
        force,
        a_indices,
        us_indices,
        total_mv,
        total_cost,
        total_profit,
        total_today_profit,
        holdings_count,
        categories,
        penetrated_assets,
        holdings_details,
        sector_flow,
        pipeline_data=pipeline_data,
        force_modules=_force_scope,
        metrics=metrics,
        comparison_indices=comparison_indices,
        history_data=history_data,
        _debate_info_container=_debate_info_container,
        span_recorder=span_recorder,
        **blocks.prompt_kwargs(),
    )

    contents, cached = contents_from_results(precheck_results, worker_results)
    _module_labels = get_llm_module_names()

    # 生成后一遍：逐模块事实锚定 → 自检 → 跨模块一致性核对（顺序是契约）
    contents = anchor_fact_checks(
        contents,
        cached,
        holdings_details=holdings_details,
        penetrated_assets=penetrated_assets,
        pipeline_data=pipeline_data,
        history_data=history_data,
        llm_config=llm_config,
        cache_info=cache_info,
        module_labels=_module_labels,
    )
    apply_generation_post_pass(
        contents,
        holdings_details=holdings_details,
        penetrated_assets=penetrated_assets,
        llm_config=llm_config,
        force_self_review="self_review" in _force_scope,
        blocks=blocks,
        module_labels=_module_labels,
    )

    return _finalize_llm_run(
        contents,
        cached,
        cache_info=cache_info,
        debate_info=_debate_info_container[0] if _has_debate else None,
        has_debate=_has_debate,
    )
