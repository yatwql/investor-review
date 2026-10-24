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


def _usage_delta(current: dict, baseline: dict | None) -> dict:
    """按报告基线裁剪会话累计用量，返回**本次报告**的用量视图。

    ``llm/session.py`` 的累计值是会话级（TUI 退出时仍要打印），报告层若直接读
    累计值，第二份报告就会显示「第一份 + 第二份」的 token 与调用数。基线取自
    ``_run_scope.start_report_run()``；无基线（None/空）时退化为全量，与引入前一致。
    """
    if not baseline:
        return current
    delta: dict = {}
    for key in ("input_tokens", "output_tokens", "cache_hit_tokens", "total_cost", "call_count"):
        if key in current:
            delta[key] = current.get(key, 0) - baseline.get(key, 0)
    base_modules = baseline.get("per_module") or {}
    per_module: dict = {}
    for module_key, entry in (current.get("per_module") or {}).items():
        base = base_modules.get(module_key) or {}
        delta_entry = dict(entry)
        for key in ("input_tokens", "output_tokens", "cache_hit_tokens", "cost", "duration"):
            if key in delta_entry:
                delta_entry[key] = delta_entry.get(key, 0) - base.get(key, 0)
        per_module[module_key] = delta_entry
    delta["per_module"] = per_module
    if current.get("models"):
        delta["models"] = list(current["models"])
    return delta


def _record_llm_context(perf, sink=None, baseline: dict | None = None) -> None:
    """把本次运行的 LLM 上下文写入 perf 记录（provider/等待/缓存/用量/质量）。

    三个来源合并（均为可选，缺失即跳过）：
      - 运行观测汇聚器：重试与节流等待、provider/model 命中、缓存命中、降级次数
      - 会话用量：逐模块 model/tokens/cost/thinking（`llm/session.py` 单源）
      - 质量评级：模块级评级（开关关闭时无评级，不写入）

    ``baseline`` 为本次报告开始时的会话用量基线（见 :func:`_usage_delta`）；
    传入后 token/调用数按 delta 记账，不传则沿用累计值。

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

        usage = _usage_delta(get_session_usage(), baseline)
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
