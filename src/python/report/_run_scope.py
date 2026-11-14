"""报告运行边界 — 每份报告开始时重置**仅属于本轮**的观测状态。

设计目的：LLM 缓存键是内容寻址的，若把上一轮的状态带进下一轮，
同持仓/同行情/同新闻的连续报告也会「因为上一轮自己造出的数据」而全部 miss。
本模块只清理**轮次语义**明确的状态，不动任何跨报告持久事实：

- ``DegradationTracker`` 事件日志：数据质量块与数据源矩阵只应看**本次报告**的
  告警；失败计数与 ``last_success`` 是跨会话事实，必须保留（降级判定依赖它们）。
- ``self_review`` 全局载体：上一轮自检区块不得残留到本轮（本轮未产出即为空）。
- LLM 会话用量：**只取基线不重置**——TUI 的「本会话累计」仍要跨报告累计，
  报告层写 perf 时按基线算 delta，避免第二份报告的 token/调用数看起来翻倍。
- 历史 chain 单轮状态（窗口复用 memo 与空结果连续计数）：报告边界清空，
  避免上一轮取到的数据遮蔽本轮真实的增量/修正。

**指纹组件审计基线不在此重置**：它的语义是「相对上一份报告哪些输入变了」，
基线必须跨报告保留；每份报告清空会让审计恒输出「无变化」。

调用方：``_generate_report_full`` / ``_generate_report_both`` 入口取一次基线，
收尾时把基线交给 ``_record_llm_context`` 计算 delta。
"""

from __future__ import annotations

import copy
import logging
import threading
from typing import Any

logger = logging.getLogger("invest")

__all__ = ["start_report_run", "finish_report_run", "run_memo", "clear_run_memo"]


#: 单轮内复用重计算结果（穿透 / 基金业绩 / 基金风格）：同一份输入只算一次，跨轮清空。
#: 键含输入指纹——同一轮里输入变了（如峰值就绪后重装配）仍会重算，不返回陈旧结果。
_RUN_MEMO: dict[Any, Any] = {}
#: per-key 锁：并发调用同一 key 时只让一个线程算，其余等结果（否则最坏重复算一次）
_RUN_MEMO_LOCKS: dict[Any, threading.Lock] = {}
_RUN_MEMO_GUARD = threading.Lock()


def clear_run_memo() -> None:
    """清空单轮复用缓存与配套锁（报告边界与测试隔离调用）。"""
    with _RUN_MEMO_GUARD:
        _RUN_MEMO.clear()
        _RUN_MEMO_LOCKS.clear()


def run_memo(key: Any, factory: Any) -> Any:
    """单轮复用：同一 ``key`` 在**本轮**只执行一次 ``factory()``，返回同一结果。

    用途：穿透 TOP10 与基金业绩/风格这类「纯读 + 重 IO」的装配在同一次报告里被
    HTML 端与 Excel 端各调一遍（实测同轮重复 2 次），冷缓存时两遍都要等网络。

    Args:
        key: 结果指纹（须包含全部影响结果的输入）。
        factory: 未命中时的计算函数（无参闭包）。

    Returns:
        ``factory()`` 的返回值（命中时直接复用上轮同键结果）。
    """
    with _RUN_MEMO_GUARD:
        if key in _RUN_MEMO:
            return _RUN_MEMO[key]
        lock = _RUN_MEMO_LOCKS.setdefault(key, threading.Lock())
    with lock:
        with _RUN_MEMO_GUARD:
            if key in _RUN_MEMO:  # 等锁期间别的线程已算完
                return _RUN_MEMO[key]
        value = factory()
        with _RUN_MEMO_GUARD:
            _RUN_MEMO[key] = value
        return value


def start_report_run() -> dict[str, Any]:
    """开启一次报告运行边界，返回 LLM 会话用量基线（供收尾算 delta）。

    任何一步失败都只记 DEBUG：观测隔离不得阻断报告生成。

    Returns:
        ``get_session_usage()`` 的深拷贝基线；取不到时返回空 dict（delta 退化为
        全量，与引入前行为一致）。
    """
    clear_run_memo()
    # 缓存未命中归因的「上一轮键」随报告边界复位：跨报告比对才成立，
    # 把上一次进程遗留的键当"上一轮"会误判内容变化。
    try:
        from src.python.llm.skeleton import reset_prev_module_cache_keys

        reset_prev_module_cache_keys()
    except Exception:  # 观测隔离失败不阻断主链路
        logger.debug("[run_scope] 缓存键归因基线重置失败，已忽略", exc_info=True)
    baseline: dict[str, Any] = {}
    try:
        from src.python.report.data_status import get_tracker

        get_tracker().begin_report()
    except Exception:  # 观测隔离失败不阻断主链路
        logger.debug("[run_scope] 降级事件日志重置失败，已忽略", exc_info=True)
    # 缓存命中率是**按轮**口径：运行收尾的 `[cache] 本次命中 …` 汇总与「同前缀未命中
    # ≥N 次」告警都读这份计数，长驻进程（Web/TUI）连跑多份报告时不清零会累计成
    # 「本次」累计值（实测 5→10→15 递进），汇总与告警随之失真。
    # 版本盐（提示词文本版本 / 事实校验规则版本）进 LLM 缓存键：本轮首尾各打一行，
    # 「四个模块为何整批重算」才不用翻代码比对指纹。
    try:
        from src.python.llm.fingerprint import log_cache_key_salts

        log_cache_key_salts("本轮开始")
    except Exception:  # 观测隔离失败不阻断主链路
        logger.debug("[run_scope] 版本盐日志失败，已忽略", exc_info=True)
    try:
        from src.python.cache import reset_cache_stats

        reset_cache_stats()
    except Exception:  # 观测隔离失败不阻断主链路
        logger.debug("[run_scope] 缓存命中率计数重置失败，已忽略", exc_info=True)
    try:
        from src.python.llm.research_contract import reset_contract_state

        reset_contract_state()
    except Exception:
        logger.debug("[run_scope] 结构化契约作用域重置失败，已忽略", exc_info=True)
    try:
        from src.python.llm.self_review import reset_self_review

        reset_self_review()
    except Exception:
        logger.debug("[run_scope] 自检载体重置失败，已忽略", exc_info=True)
    try:
        from src.python.llm.session import get_session_usage

        baseline = copy.deepcopy(get_session_usage())
    except Exception:
        logger.debug("[run_scope] 会话用量基线读取失败，已忽略", exc_info=True)
    try:
        from src.python.fetcher.chain_incremental import reset_run_history_state

        reset_run_history_state()
    except Exception:
        logger.debug("[run_scope] 历史取数单轮状态重置失败，已忽略", exc_info=True)
    return baseline


def finish_report_run(perf: Any | None = None) -> None:
    """收尾一次报告运行：落耗时台账 + 打本轮结束日志（版本盐 + 缓存命中汇总）。

    **为什么收口在这里**：这两个信息一个属 `llm`、一个属 `cache`，而 `cache` 是基础层，
    不得反向 import `llm` 取版本号（分层纪律：只能依赖下层与贯穿层）。本模块属报告层，
    同时依赖二者，是唯一能合法把两者组合到同一行日志的位置。

    为什么要在收尾也打一次版本盐：模块整批重算的归因只有「键变了」这一信号，末行能
    与首行直接对拍「这轮前后版本盐是否变过」，不必回翻首行或比对指纹。

    Args:
        perf: 本次运行的耗时记录器（`core.perf.PerfRun`）；None 时只打日志不落盘。
    """
    if perf is not None:
        try:
            perf.save()
        except Exception:  # 台账落盘失败不阻断收尾日志
            logger.debug("[run_scope] 耗时台账落盘失败，已忽略", exc_info=True)
    _salts_note = ""
    try:
        from src.python.llm.fingerprint import cache_key_salts

        _salts = cache_key_salts()
        _salts_note = f"缓存键版本盐：提示词={_salts['prompt_schema']} 校验规则={_salts['fact_rules']}"
    except Exception:
        logger.debug("[run_scope] 版本盐读取失败，已忽略", exc_info=True)
    try:
        from src.python.cache import log_cache_summary

        log_cache_summary(salts_note=_salts_note)
    except Exception:
        logger.debug("[run_scope] 缓存命中汇总失败，已忽略", exc_info=True)
