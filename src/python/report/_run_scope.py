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
from typing import Any

logger = logging.getLogger("invest")

__all__ = ["start_report_run"]


def start_report_run() -> dict[str, Any]:
    """开启一次报告运行边界，返回 LLM 会话用量基线（供收尾算 delta）。

    任何一步失败都只记 DEBUG：观测隔离不得阻断报告生成。

    Returns:
        ``get_session_usage()`` 的深拷贝基线；取不到时返回空 dict（delta 退化为
        全量，与引入前行为一致）。
    """
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
