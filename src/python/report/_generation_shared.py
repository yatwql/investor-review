"""报告生成共享步骤（both / full 两条路径共用）。"""

from __future__ import annotations

import logging


from src.python.report._report_output import (  # noqa: F401  # 产物落盘子模块（消费方在本门面，patch 点不变）
    _generate_full_excel_report,
    _generate_full_html_report,
)

# ── 子模块 re-export ────────────────────────────────────
from src.python.report._chart_dataset_factory import _build_chart_datasets_for_report  # noqa: F401
from src.python.report._full_risk_metrics import _prepare_full_risk_metrics  # noqa: F401
from src.python.report._report_health import _collect_health_checks, _spawn_health_checks  # noqa: F401
from src.python.report._report_helpers import (  # noqa: F401
    _action_holdings_details,
    _compute_details,
    _inject_evolution_data,
    _inject_snapshot_diff_data,
    _validate_pipeline_snapshot,
    _validate_prep_completeness,
)

logger = logging.getLogger("invest")


def _record_llm_context(perf, sink=None) -> None:
    """把本次运行的 LLM 上下文写入 perf 记录（provider/等待/缓存/用量/质量）。

    三个来源合并（均为可选，缺失即跳过）：
      - 运行观测汇聚器：重试与节流等待、provider/model 命中、缓存命中、降级次数
      - 会话用量：逐模块 model/tokens/cost/thinking（`llm/session.py` 单源）
      - 质量评级：模块级评级（开关关闭时无评级，不写入）

    ``sink`` 必须由调用方传入本次绑定的汇聚器：管线在 LLM 阶段结束的 ``finally``
    中已将全局 sink 解绑（防跨运行串味），此时 ``current_llm_observation()`` 已为
    None，再取全局会丢失整段观测。

    任何异常静默降级——观测不得影响报告生成。
    """
    try:
        from src.python.llm.session import get_session_usage

        context: dict = {}
        if sink is None:
            from src.python.llm.observation import current_llm_observation

            sink = current_llm_observation()
        if sink is not None:
            context.update(sink.snapshot())

        usage = get_session_usage()
        per_module = usage.get("per_module") or {}
        if per_module:
            context["modules"] = {
                key: {
                    "model": entry.get("model", ""),
                    "thinking": bool(entry.get("thinking")),
                    "cached": bool(entry.get("cached")),
                    "input_tokens": int(entry.get("input_tokens", 0)),
                    "output_tokens": int(entry.get("output_tokens", 0)),
                    "cost": round(float(entry.get("cost", 0.0)), 6),
                }
                for key, entry in sorted(per_module.items())
            }
        if usage.get("call_count"):
            context["call_count"] = int(usage["call_count"])
            context["total_cost"] = round(float(usage.get("total_cost", 0.0)), 6)

        perf.set_llm_context(context)
    except Exception:
        logger.debug("[perf] LLM 上下文登记失败，已忽略", exc_info=True)
