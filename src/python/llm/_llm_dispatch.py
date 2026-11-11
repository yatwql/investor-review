"""LLM 批量生成的 worker 装配与线程池并发分发 —— 进度回调与并发上限调度。

`_build_module_fns` 把 LLM 模块名映射到对应生成函数（**新增 LLM 模块在此登记**，
无需深入分发函数）；`_dispatch_llm_workers` 用 `ThreadPoolExecutor` 并发跑 worker、
按完成顺序回报进度，内含 thinking 模块串行上限与辩论模式组合的调度决策。

对外门面 `generators_orchestrator.py` re-export `_dispatch_llm_workers`（`generate_all_llm`
在门面内消费它，既有 patch 点不变）；`_build_module_fns` / `_LLM_CLIENT_SETTINGS`
仅由本模块持有，测试直接从本模块 import/patch。
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from src.python.core.registry import get_llm_module_names
from src.python.llm._debate_router import install_debate_route
from src.python.llm._worker_runner import make_module_runner, thinking_concurrency_limit
from src.python.llm.generators import (
    generate_expert_review,
    generate_global_macro,
    generate_health_check,
    generate_penetration_deep_analysis,
)

from src.python.config import get_llm_setting_default

logger = logging.getLogger("invest")


# ── HTTP 客户端配置 ──────────────────────────────────────────
# 各工作线程共享同一组连接参数，通过 HTTP/2 + keepalive 减少连接建立开销
_LLM_MAX_CONNECTIONS = 20  # 总连接池上限
_LLM_MAX_KEEPALIVE = 10  # 空闲保持连接数
_LLM_CLIENT_SETTINGS: dict[str, Any] = {
    "http2": True,  # HTTP/2 多路复用
    "limits": httpx.Limits(
        max_connections=_LLM_MAX_CONNECTIONS,
        max_keepalive_connections=_LLM_MAX_KEEPALIVE,
    ),
}

#: thinking 并发槽等待超过该秒数即记一行 INFO（低于此值属正常抖动，不值得占日志）
_THINKING_WAIT_LOG_SECONDS = 5.0

#: thinking 串行等待累计（秒）——进程级，报告层 LLM 阶段结束后汇入 perf counters
#: 并清零；用于跨期量化「把 llm_max_thinking_concurrency 提到 2 能省多少」
_THINKING_WAIT_TOTAL = {"seconds": 0.0}
#: 串行等待累计达到该值才给「提到 2」的可执行提示（更小的等待不值得改配置）
_THINKING_WAIT_HINT_SECONDS = 20.0
_THINKING_WAIT_TOTAL_LOCK = threading.Lock()


def reset_thinking_wait_total() -> None:
    """清零 thinking 串行等待累计（每轮 LLM 阶段开始前调用；测试隔离同源）。"""
    with _THINKING_WAIT_TOTAL_LOCK:
        _THINKING_WAIT_TOTAL["seconds"] = 0.0


def thinking_wait_total_seconds() -> float:
    """本轮 thinking 串行等待累计秒数（快照）。"""
    with _THINKING_WAIT_TOTAL_LOCK:
        return round(_THINKING_WAIT_TOTAL["seconds"], 3)


def run_holding_change_in_worker(
    pipeline_data: dict | None,
    llm_config: dict | None,
    *,
    force: bool = False,
    holdings_details: list[dict] | None = None,
    purchase_constraint_block: str = "",
    http_client: Any = None,
) -> tuple[str | None, bool]:
    """持仓变动复盘归因的**并行工作线程**包装（把 bool 结果转成调度层形态）。

    该模块不进 ``llm/session`` 的四模块统计口径（仍按 registry 登记复用缓存/统计），
    这里只负责调用与失败隔离：任何异常都降级为「无归因」（报告归因块隐藏），
    绝不影响主内容。
    """
    from src.python.llm.holding_change_review import run_holding_change_review

    try:
        ok = run_holding_change_review(
            pipeline_data,
            llm_config,
            force=force,
            holdings_details=holdings_details,
            purchase_constraint_block=purchase_constraint_block,
            http_client=http_client,
        )
    except Exception:  # noqa: BLE001 — 归因失败不得影响主内容
        logger.warning("持仓变动复盘归因并行调度异常（不影响主内容）", exc_info=True)
        return (None, False)
    return ("ok" if ok else None, False)


def _build_module_fns(
    a_indices,
    us_indices,
    total_mv: float,
    total_cost: float,
    total_profit: float,
    total_today_profit: float,
    holdings_count: int,
    categories: dict,
    penetrated_assets: list[dict] | None,
    holdings_details: list[dict] | None,
    sector_flow: list[dict] | None,
    force: bool,
    force_modules: Iterable[str] | None = None,
    pipeline_data: dict | None = None,
    competitive_context: str = "",
    metrics: dict | None = None,
    data_quality_text: str = "",
    history_data: dict | None = None,
    purchase_constraint_block: str = "",
    holding_change_block: str = "",
    event_impact_block: str = "",
    schedule_replay_block: str = "",
) -> dict[str, Callable]:
    """构建 LLM 模块名称 → 生成函数闭包 的映射。

    模块级集中注册，新增 LLM 模块只需在此添加条目。
    每个闭包签名: (http_client, llm_config) → (result_str | None, from_cache)。

    history_data 贯通到三个承接模块，使其写侧指纹与预检指纹同源（见
    ``llm/module_fingerprint.py``）；漏传会让写侧指纹少一项风险信号摘要，
    预检键永不命中。

    ``force_modules`` 为模块级强刷集合：逐模块
    ``force = 全局 force or 模块键 in 集合``，未指定模块照常走缓存。
    """
    _forced = force_modules if force_modules is not None else frozenset()

    def _mod_force(key: str) -> bool:
        return force or key in _forced

    return {
        # 持仓变动复盘归因：只吃持仓变动契约（`pipeline_data["holding_change_data"]`），
        # 不依赖四模块产出，因此并入并行批而非串行后置——实测其单次 4~25s 若串行后置，
        # 会完全叠加在 expert_review 之后的关键路径上。契约缺席/开关关闭时内部直接跳过。
        "holding_change": lambda c, lc: run_holding_change_in_worker(
            pipeline_data,
            lc,
            force=_mod_force("holding_change"),
            holdings_details=holdings_details,
            purchase_constraint_block=purchase_constraint_block,
            http_client=c,
        ),
        "global_macro": lambda c, lc: generate_global_macro(
            a_indices,
            us_indices,
            total_mv,
            total_profit,
            total_cost,
            categories,
            sector_flow=sector_flow,
            force=_mod_force("global_macro"),
            http_client=c,
            llm_config=lc,
            competitive_context=competitive_context,
            holdings_details=holdings_details,
            purchase_constraint_block=purchase_constraint_block,
            holding_change_block=holding_change_block,
            event_impact_block=event_impact_block,
            schedule_replay_block=schedule_replay_block,
        ),
        "expert_review": lambda c, lc: generate_expert_review(
            total_mv,
            total_cost,
            total_profit,
            total_today_profit,
            holdings_count,
            categories,
            penetrated_assets,
            holdings_details=holdings_details,
            purchase_constraint_block=purchase_constraint_block,
            holding_change_block=holding_change_block,
            event_impact_block=event_impact_block,
            schedule_replay_block=schedule_replay_block,
            force=_mod_force("expert_review"),
            http_client=c,
            llm_config=lc,
            pipeline_data=pipeline_data,
            competitive_context=competitive_context,
            metrics=metrics,
            history_data=history_data,
        ),
        "health_check": lambda c, lc: generate_health_check(
            total_mv,
            total_cost,
            total_profit,
            total_today_profit,
            holdings_count,
            categories,
            penetrated_assets,
            holdings_details=holdings_details,
            purchase_constraint_block=purchase_constraint_block,
            holding_change_block=holding_change_block,
            event_impact_block=event_impact_block,
            schedule_replay_block=schedule_replay_block,
            force=_mod_force("health_check"),
            http_client=c,
            llm_config=lc,
            pipeline_data=pipeline_data,
            data_quality_text=data_quality_text,
            history_data=history_data,
        ),
        "penetration_deep": lambda c, lc: generate_penetration_deep_analysis(
            total_mv,
            total_cost,
            total_profit,
            total_today_profit,
            holdings_count,
            categories,
            penetrated_assets,
            holdings_details=holdings_details,
            purchase_constraint_block=purchase_constraint_block,
            holding_change_block=holding_change_block,
            event_impact_block=event_impact_block,
            schedule_replay_block=schedule_replay_block,
            force=_mod_force("penetration_deep"),
            http_client=c,
            llm_config=lc,
            history_data=history_data,
        ),
    }


def _log_module_outcome(
    key: str,
    result: Any,
    label_map: dict[str, str],
    budget_skipped: list[str],
) -> None:
    """模块产出的结果行：成功 / 关掉 / 预算跳过 / **真失败** 分级留痕。

    三者过去都打成 INFO「生成失败（跳过）」：事后无法区分「用户关了开关」「预算到点」与
    「provider 全挂导致内容缺失」。真失败必须是 ERROR（内容不可用是错误级事件），
    原因取 `LLM_MODULE_FAILURE` 的单一事实来源。
    """
    from src.python.llm.failure_reasons import (
        FAIL_REASON_DISABLED,
        LLM_MODULE_FAILURE,
        describe_failure_reason,
    )

    label = label_map.get(key, key)
    if result:
        logger.info("%s生成完成", label)
        return
    if key in budget_skipped:
        logger.info("%s未生成（总时间预算跳过）", label)
        return
    reason = LLM_MODULE_FAILURE.get(key)
    final = reason.get("final_status") if isinstance(reason, dict) else reason
    if final == FAIL_REASON_DISABLED:
        logger.info("%s未生成（开关关闭）", label)
        return
    logger.error(
        "%s生成失败（%s）——该模块本轮无内容，报告对应章节将降级/占位",
        label,
        describe_failure_reason(final) or "原因未记录",
    )


def make_budget_guard(
    budget_sec: float,
    started: float,
    skipped: list[str],
    label_map: dict[str, str],
    clock: Callable[[], float] = time.monotonic,
) -> Callable[[str, Callable[[], Any]], Callable[[], Any]]:
    """构造「总时间预算闸」：每个模块启动前检查已用时，超预算即跳过（不打断在跑的）。

    Args:
        budget_sec: 预算秒数（<=0 表示不启用，恒放行）
        started: 预算起点（`time.monotonic()`）
        skipped: 被跳过的模块键收集器（调用方用于收尾汇总日志）
        label_map: 模块键 → 中文标签（日志可读性）
        clock: 时钟注入（测试用；默认 monotonic）

    Returns:
        guard(key, runner) → 包装后的 runner
    """

    def _guard(key: str, runner: Callable[[], Any]) -> Callable[[], Any]:
        def _wrapped() -> Any:
            elapsed = clock() - started
            if budget_sec > 0 and elapsed > budget_sec:
                skipped.append(key)
                logger.warning(
                    "LLM 总时间预算已用尽（已用 %.0fs ≥ 预算 %.0fs），跳过模块 %s"
                    "（可在 llm_settings.json 调整 llm_total_time_budget_sec）",
                    elapsed,
                    budget_sec,
                    label_map.get(key, key),
                )
                return (None, False)
            return runner()

        return _wrapped

    return _guard


def _run_workers(
    module_fns: dict[str, Callable],
    needs: dict[str, bool],
    runner_kwargs: dict,
    label_map: dict[str, str],
    thinking_limit: int,
) -> dict[str, dict]:
    """提交并归集：只提交 `needs=True` 的模块，结果键集合与提交集合相等。

    单个模块线程异常不外抛（记 WARNING 且不写该键）：一份报告不该因一个模块挂掉而
    整体失败，但缺失必须留痕，否则「模块静默缺失」无人知晓。

    总时间预算在此构造：每个模块**启动前**检查已用时长，超预算不再提交新模块；
    已提交的模块不打断（强杀线程会留下半截内容与未释放连接）。预算 0/缺省 = 不启用。
    """
    results_dict: dict[str, dict] = {}
    cfg = runner_kwargs.get("llm_config") or {}
    max_workers = cfg.get("llm_max_concurrency", get_llm_setting_default("llm_max_concurrency"))
    budget_skipped: list[str] = []
    budget_guard = make_budget_guard(
        float(cfg.get("llm_total_time_budget_sec") or 0),
        time.monotonic(),
        budget_skipped,
        label_map,
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict[Future, str] = {
            executor.submit(budget_guard(key, make_module_runner(label=key, fn=fn, **runner_kwargs))): key
            for key, fn in module_fns.items()
            if needs.get(key)
        }
        for future in as_completed(futures):
            try:
                result, from_cache = future.result()
                key = futures[future]
                results_dict[key] = {"result": result, "cached": from_cache}
                _log_module_outcome(key, result, label_map, budget_skipped)
            except Exception:  # noqa: PERF203
                logger.warning("LLM 生成线程异常", exc_info=True)

    _log_dispatch_tail(budget_skipped, label_map, thinking_limit)
    return results_dict


def _log_dispatch_tail(budget_skipped: list[str], label_map: dict[str, str], thinking_limit: int) -> None:
    """收尾两条汇总：预算跳过清单 + thinking 串行等待量化（把上限提到 2 能省多少）。"""
    if budget_skipped:
        logger.warning(
            "本次 LLM 生成因总时间预算跳过 %d 个模块：%s（报告按已生成内容呈现）",
            len(budget_skipped),
            "、".join(label_map.get(k, k) for k in budget_skipped),
        )
    wait_total = thinking_wait_total_seconds()
    if wait_total >= _THINKING_WAIT_HINT_SECONDS and thinking_limit < 2:
        logger.info(
            "[llm/thinking] 本轮 thinking 模块串行等待合计 %.1fs（上限 %d）：提到 2 约可省该时长，"
            "前提是端点并发两个 thinking 请求不出现空响应（改 llm_settings.json 的 llm_max_thinking_concurrency）",
            wait_total,
            thinking_limit,
        )


def _dispatch_llm_workers(
    needs: dict[str, bool],
    llm_config: dict | None,
    force: bool,
    a_indices,
    us_indices,
    total_mv: float,
    total_cost: float,
    total_profit: float,
    total_today_profit: float,
    holdings_count: int,
    categories: dict,
    penetrated_assets: list[dict] | None,
    holdings_details: list[dict] | None,
    sector_flow: list[dict] | None,
    pipeline_data: dict | None = None,
    *,
    metrics: dict | None = None,
    force_modules: Iterable[str] | None = None,
    data_quality_text: str = "",
    comparison_indices: dict[str, str] | None = None,
    history_data: dict | None = None,
    _debate_info_container: list | None = None,
    competitive_context: str = "",
    purchase_constraint_block: str = "",
    holding_change_block: str = "",
    event_impact_block: str = "",
    schedule_replay_block: str = "",
    span_recorder=None,
) -> dict[str, dict]:
    """对缓存未命中的模块提交线程池任务，返回结果字典。

    Args:
        span_recorder: 逐模块耗时记录器（`LLM+新闻` 父阶段绑定）；
            None 时零行为变化。记录的是模块**自身耗时**，四模块并发故之和不
            等于父阶段墙钟。
        _debate_info_container: 辩论模式信息捕获容器（list[dict|None]），
            启用辩论模式时闭包写入 debate_info dict，调用方事后读取。
        competitive_context: 由调用方（``generate_all_llm``）渲染一次的竞争语境
            文本块，与其交给预检侧的**同一实例**——本函数不再自行渲染，
            否则进提示词的文本可能与进指纹的文本不同（缓存键与内容脱钩）。
        data_quality_text: 同理由调用方渲染一次的数据质量详细状态块，同样与
            预检侧共享同一实例（仅 health_check 提示词含该段）。
    """
    if not any(needs.values()):
        return {}

    _label_map: dict[str, str] = get_llm_module_names()

    # thinking 并发闸门：开启 Extended Thinking 的模块并发涌向端点时偶发返回空 content
    # （HTTP 200 + 空响应）。信号量把这类请求限制在 llm_max_thinking_concurrency 个；
    # 非 thinking 模块不受限，保持原有并发。等待时长累加到总账供收尾判断。
    _thinking_limit = thinking_concurrency_limit(llm_config)
    _thinking_sem = threading.BoundedSemaphore(_thinking_limit)

    def _record_thinking_wait(seconds: float) -> None:
        with _THINKING_WAIT_TOTAL_LOCK:
            _THINKING_WAIT_TOTAL["seconds"] += seconds

    _MODULE_FNS = _build_module_fns(
        a_indices=a_indices,
        us_indices=us_indices,
        total_mv=total_mv,
        total_cost=total_cost,
        total_profit=total_profit,
        total_today_profit=total_today_profit,
        holdings_count=holdings_count,
        categories=categories,
        penetrated_assets=penetrated_assets,
        holdings_details=holdings_details,
        sector_flow=sector_flow,
        force=force,
        force_modules=force_modules,
        pipeline_data=pipeline_data,
        competitive_context=competitive_context,
        metrics=metrics,
        data_quality_text=data_quality_text,
        history_data=history_data,
        purchase_constraint_block=purchase_constraint_block,
        holding_change_block=holding_change_block,
        event_impact_block=event_impact_block,
        schedule_replay_block=schedule_replay_block,
    )

    # 辩论模式：槽位替换 expert_review（键名不变，失败回退普通生成）
    install_debate_route(
        _MODULE_FNS,
        needs=needs,
        total_mv=total_mv,
        total_cost=total_cost,
        total_profit=total_profit,
        total_today_profit=total_today_profit,
        holdings_count=holdings_count,
        categories=categories,
        penetrated_assets=penetrated_assets,
        holdings_details=holdings_details,
        force=force,
        force_modules=force_modules,
        pipeline_data=pipeline_data,
        competitive_context=competitive_context,
        metrics=metrics,
        purchase_constraint_block=purchase_constraint_block,
        holding_change_block=holding_change_block,
        event_impact_block=event_impact_block,
        schedule_replay_block=schedule_replay_block,
        debate_info_container=_debate_info_container,
    )

    _runner_kwargs = {
        "llm_config": llm_config,
        "label_map": _label_map,
        "thinking_sem": _thinking_sem,
        "thinking_limit": _thinking_limit,
        "span_recorder": span_recorder,
        "record_thinking_wait": _record_thinking_wait,
        "wait_log_seconds": _THINKING_WAIT_LOG_SECONDS,
    }

    return _run_workers(_MODULE_FNS, needs, _runner_kwargs, _label_map, _thinking_limit)
