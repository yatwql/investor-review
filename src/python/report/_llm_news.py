"""LLM/新闻并行获取 — 线程池提交/收集/报告。

统一管理 LLM 内容和新闻数据的并行获取。

观测：`LLM+新闻` 阶段内各子项自身耗时经 `span_recorder` 记入
`perf_history.jsonl` 的 `breakdown`（子项自身耗时，LLM 与新闻并行，故之和不参与
`total_seconds`）。recorder 为 None 时行为零变化。
"""

from __future__ import annotations

from collections.abc import Collection
from concurrent.futures import Future

import time

from src.python.report.progress import ProgressReporter

logger = __import__("logging").getLogger("invest")


def _report_llm_module_results(
    results: tuple,
    cached_flags: tuple[bool, bool, bool, bool],
    reporter: ProgressReporter,
) -> None:
    """统一的 LLM 模块结果报告逻辑。"""
    from src.python.llm import FAIL_REASON_DISABLED
    from src.python.llm.prompts import LLM_MODULE_FAILURE
    from src.python.core.registry import get_llm_module_name
    from src.python.report.llm_module_info import get_llm_module_failure_reason

    _MODULE_KEYS = ("global_macro", "expert_review", "health_check", "penetration_deep")
    ok_count = 0
    disabled: list[str] = []
    failed: list[str] = []

    for mk, r in zip(_MODULE_KEYS, results):
        if r is not None:
            ok_count += 1
        elif get_llm_module_failure_reason(LLM_MODULE_FAILURE, mk) == FAIL_REASON_DISABLED:
            disabled.append(get_llm_module_name(mk))
        else:
            failed.append(get_llm_module_name(mk))

    for name in disabled:
        reporter.info(f"{name}：已跳过（菜单 S 可切换）")
    for name in failed:
        reporter.add_error(f"{name}：内容生成失败（已降级使用占位文本）")
        reporter.warn(f"{name}：内容生成失败（已降级使用占位文本）")

    if ok_count > 0 and not failed:
        tag = "缓存" if all(cached_flags) else "LLM"
        reporter.ok(f"{tag} 内容生成完成")
    elif ok_count == 0 and not failed and not disabled:
        reporter.warn("LLM 均未生成（请检查 LLM 配置）")
    elif ok_count == 0 and not failed:
        reporter.info("所有 LLM 内容已跳过，未调用 LLM")


def _timed_news_fetch(recorder, build_fn, *args, **kwargs) -> tuple:
    """执行新闻获取并记入子项耗时（`recorder` 为 None 时零行为变化）。"""
    started = time.perf_counter()
    try:
        return build_fn(*args, **kwargs)
    finally:
        if recorder is not None:
            recorder.record("新闻获取", time.perf_counter() - started)


def _submit_llm_future(
    pool,
    holdings: list,
    prep_data: dict,
    sector_flow: list | None,
    force_llm: bool,
    pipeline_data: dict | None,
    enable_llm: bool,
    *,
    force_modules: Collection[str] | None = None,
    history_data: dict | None = None,
    comparison_indices: dict[str, str] | None = None,
    metrics: dict | None = None,
    span_recorder=None,
) -> Future | None:
    """向线程池提交 LLM 生成任务，返回 Future 或 None。

    ``span_recorder``：四模块耗时记录器（由调用方按 `LLM+新闻` 父阶段建立），
    下传 `generate_all_llm` 逐模块记时；None 时行为零变化。
    """
    if not enable_llm:
        return None
    from src.python.llm import generate_all_llm
    from src.python.report.data_status import get_tracker

    # 数据降级事件快照：行情/基金等数据获取阶段已结束，此处读取一次即定稿，
    # 随参数送入持仓体检提示词的【数据质量降级】详情段。必须在主线程读取
    # （get_log 线程安全），不在工作线程内取，避免与并发写入交错。
    _degradation_events = get_tracker().get_log()

    return pool.submit(
        generate_all_llm,
        prep_data["a_indices"],
        prep_data["us_indices"],
        prep_data["total_mv"],
        prep_data["total_cost"],
        prep_data["total_profit"],
        prep_data["total_today_profit"],
        len(holdings),
        prep_data["categories"],
        penetrated_assets=prep_data["penetrated_assets"],
        holdings_details=prep_data["holdings_details"],
        sector_flow=sector_flow,
        force=force_llm,
        force_modules=force_modules,
        pipeline_data=pipeline_data,
        history_data=history_data,
        comparison_indices=comparison_indices,
        metrics=metrics,
        degradation_events=_degradation_events,
        span_recorder=span_recorder,
    )


def _submit_news_future(
    pool,
    holdings: list,
    prep_data: dict,
    enable_news: bool,
    purchase_constraint_block: str = "",
    force_news: bool = False,
    span_recorder=None,
) -> Future | None:
    """向线程池提交新闻获取任务，返回 Future 或 None。

    ``force_news``：新闻关联 LLM 增强的模块级强刷（
    ``news_correlation`` ∈ 强刷集合时置 True）。
    ``span_recorder``：新闻获取耗时记录器（None 时零行为变化）。
    """
    if not enable_news:
        return None
    from src.python.report.news_correlation import build_news_data

    return pool.submit(
        _timed_news_fetch,
        span_recorder,
        build_news_data,
        holdings,
        prep_data["news_top_count"],
        prep_data["penetrated_assets"],
        purchase_constraint_block,
        force_news,
        span_recorder=span_recorder,
    )


def _collect_llm_future_result(fut, reporter) -> tuple:
    """收集 LLM 生成结果，返回 (llm_content, debate_info)。"""
    try:
        _result = fut.result()
        llm_content = _result[:4]
        _cached = _result[4:8]
        _report_llm_module_results(llm_content, _cached, reporter)
        debate_info = _result[8] if len(_result) > 8 else None
        return llm_content, debate_info
    except Exception:
        reporter.add_error("LLM 内容生成异常（详情请查看日志文件 logs/app.log）")
        reporter.error("LLM 内容生成异常（详情请查看日志）")
        return (None, None, None, None), None


def _collect_news_future_result(fut, reporter) -> tuple:
    """收集新闻获取结果，返回 (news_data, news_llm_meta, news_ok)。"""
    try:
        news_data, news_llm_meta = fut.result()
        news_ok = bool(news_data)
        reporter.ok(f"新闻获取完成，共 {len(news_data)} 条")
        return news_data, news_llm_meta, news_ok
    except Exception:
        reporter.add_error("新闻获取异常（详情请查看日志文件 logs/app.log）")
        reporter.warn("新闻获取异常（详情请查看日志）")
        return [], {}, False


def _fetch_llm_and_news(
    holdings: list,
    prep_data: dict,
    sector_flow: list | None,
    force_llm: bool,
    pipeline_data: dict | None,
    enable_news: bool,
    enable_llm: bool,
    reporter: ProgressReporter,
    *,
    force_llm_modules: Collection[str] | None = None,
    history_data: dict | None = None,
    comparison_indices: dict[str, str] | None = None,
    metrics: dict | None = None,
    span_recorder=None,
) -> tuple[tuple, list, dict, bool, dict | None]:
    """并行获取 LLM 内容 + 新闻数据，统一处理 4 分支。

    内部管理线程池（max_workers=2）。
    LLM 和新闻的 ok/disabled/failed 计数统一归入此函数。

    ``span_recorder``：`LLM+新闻` 父阶段的子项记录器（上层按父阶段建立），
    逐模块与新闻获取各自记时；None 时零行为变化。

    ``force_llm_modules``：模块级强刷范围（集合/列表均可，只做成员判定）——并行四模块经
    ``generate_all_llm`` 同源消费，新闻 LLM 增强按 ``news_correlation``
    是否在集合内单独置 force。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    _forced = force_llm_modules if force_llm_modules is not None else frozenset()
    _force_news = "news_correlation" in _forced

    llm_content: tuple = (None, None, None, None)
    news_data: list = []
    news_llm_meta: dict = {}
    news_ok: bool = False
    debate_info: dict | None = None

    # 分支 ④：均关闭
    if not enable_llm and not enable_news:
        reporter.info("[章节配置] 新闻和 LLM 均未开启，跳过内容生成")
        return llm_content, news_data, news_llm_meta, news_ok, debate_info

    if not enable_news:
        reporter.info("[章节配置] 市场新闻已关闭，跳过新闻获取")
    if not enable_llm:
        reporter.info("[章节配置] LLM 分析章节已关闭，跳过 LLM 内容生成")

    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="orch_llm_news")
    try:
        # 申购限购约束块：与 generate_all_llm 共用同一提取单源（供新闻关联批量
        # 判定与缓存指纹）；缺席（降级/未产出）→ ""（回退原样）。
        from src.python.llm import extract_purchase_constraint_block

        purchase_constraint_block = extract_purchase_constraint_block(pipeline_data)

        # ── 事件窗对照（报告章节与增强开关 event_window_impact，默认关）：开启时新闻先行 ──
        # 事件表须以本次新闻（含逐条 LLM 判定极性）装配，装配完成再提交 LLM 生成，
        # 分歧例块才进分析章提示词与指纹（news 与 LLM 并行会引入装配竞态，故此处
        # 走串行）；开关关闭 → 走下方并行原路径，行为逐字节不变。
        from src.python.config.features import is_feature_enabled

        if is_feature_enabled("event_window_impact") and enable_news:
            _news_fut = _submit_news_future(
                pool,
                holdings,
                prep_data,
                enable_news,
                purchase_constraint_block,
                _force_news,
                span_recorder=span_recorder,
            )
            news_data, news_llm_meta, news_ok = _collect_news_future_result(_news_fut, reporter)
            from src.python.report._experimental_seams import inject_event_impact_data

            _t0 = time.perf_counter()
            inject_event_impact_data(
                pipeline_data,
                reporter,
                news_data=news_data,
                holdings=holdings,
                penetrated_assets=prep_data.get("penetrated_assets"),
                comparison_indices=comparison_indices,
            )
            if span_recorder is not None:
                span_recorder.record("事件窗装配", time.perf_counter() - _t0)
            if enable_llm:
                _llm_fut = _submit_llm_future(
                    pool,
                    holdings,
                    prep_data,
                    sector_flow,
                    force_llm,
                    pipeline_data,
                    enable_llm,
                    force_modules=_forced,
                    history_data=history_data,
                    comparison_indices=comparison_indices,
                    metrics=metrics,
                    span_recorder=span_recorder,
                )
                if _llm_fut is not None:
                    llm_content, debate_info = _collect_llm_future_result(_llm_fut, reporter)
            return llm_content, news_data, news_llm_meta, news_ok, debate_info

        _news_fut = _submit_news_future(
            pool,
            holdings,
            prep_data,
            enable_news,
            purchase_constraint_block,
            _force_news,
            span_recorder=span_recorder,
        )
        _llm_fut = _submit_llm_future(
            pool,
            holdings,
            prep_data,
            sector_flow,
            force_llm,
            pipeline_data,
            enable_llm,
            force_modules=_forced,
            history_data=history_data,
            comparison_indices=comparison_indices,
            metrics=metrics,
            span_recorder=span_recorder,
        )

        if _llm_fut is not None and _news_fut is not None:
            # 分支 ①：LLM + 新闻均开启（并行等待）
            _waiting: list[Future] = [_news_fut, _llm_fut]
            for fut in as_completed(_waiting):
                if fut is _llm_fut:
                    llm_content, debate_info = _collect_llm_future_result(fut, reporter)
                else:
                    news_data, news_llm_meta, news_ok = _collect_news_future_result(fut, reporter)
        elif _news_fut is not None:
            # 分支 ②：仅新闻
            news_data, news_llm_meta, news_ok = _collect_news_future_result(_news_fut, reporter)
        elif _llm_fut is not None:
            # 分支 ③：仅 LLM
            llm_content, debate_info = _collect_llm_future_result(_llm_fut, reporter)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    return llm_content, news_data, news_llm_meta, news_ok, debate_info
