"""LLM 运行事前成本预估与日预算上限 — 生成前给区间预估、超限给处置依据。

定位（事前视角，与事后统计分工）：
  - **区间预估**：按「计划参与模块（`enabled_llm` 开关 ∩ 深度档位收窄）× 生效模型
    单价」给出本次生成的费用区间。优先用 `perf_history.jsonl` 的逐模块历史实际
    费用（自校准，含缓存命中效应）；无历史样本的模块回落静态 token 包络 × 模型
    单价（量级兜底）。全部模块既无历史又无法定价时 `ok=False`——**预估失败永不
    阻塞生成**，由渠道层降级为「跳过确认继续」。
  - **日预算**：`llm_settings.json → daily_cost_limit`（0/缺省 = 不启用）。今日已
    花费从 `perf_history.jsonl` 当日记录的 `llm.total_cost` 求和——与事后统计
    （session usage / perf 汇总）同源，避免两处数字打架。预算是**硬闸**：交互
    渠道询问「用已有结果继续 / 中止」，非交互渠道直接中止。

计费数学单源于 `llm.pricing.compute_cost_value`（与事后 `estimate_cost` 同一实现）。
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from src.python.llm.pricing import (
    CURRENCY_SYMBOLS,
    PRICING_CURRENCY,
    compute_cost_value,
)

logger = logging.getLogger("invest")

_HISTORY_WINDOW_RUNS = 30
"""历史回看窗口：最近 N 次运行的逐模块费用样本。"""

_STATIC_IN_LOW = 8_000
_STATIC_IN_HIGH = 48_000
"""静态兜底的单模块输入 token 包络（低/高）——无历史样本时的量级假设。"""

_STATIC_OUT_LOW = 1_000
_STATIC_OUT_FALLBACK = 8_192
"""静态兜底的输出 token 包络：低值固定；高值优先取 max_tokens_<模块> 配置。"""

_DEBATE_CALL_MULT = 3
"""辩论模式下 expert_review 的静态调用倍数（正/反/综述三次调用）。"""

_DEBATE_KEYS = ("debate_pro", "debate_con", "debate_synthesis")
"""辩论三段缓存键（缓存域登记；费用并入 expert_review 口径，与其计划参与口径对齐）。"""


def _currency_symbol() -> str:
    return CURRENCY_SYMBOLS.get(PRICING_CURRENCY, "$")


def _get_llm_config() -> dict[str, Any]:
    try:
        from src.python.config import get_llm_config

        return get_llm_config() or {}
    except Exception:  # noqa: BLE001 — 配置不可读属降级路径：按空配置继续
        logger.debug("[cost_forecast] LLM 配置读取失败，按空配置处理", exc_info=True)
        return {}


def _load_perf_history() -> list[dict[str, Any]]:
    try:
        from src.python.core.perf import load_history

        return load_history()
    except Exception:  # noqa: BLE001 — 历史不可读 → 退回静态兜底，不阻塞预估
        logger.debug("[cost_forecast] perf 历史读取失败，按无历史处理", exc_info=True)
        return []


def resolve_planned_modules(
    llm_config: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> list[str]:
    """解析本次生成计划参与的 LLM 模块（settings_suffix 升序稳定顺序）。

    口径 = 面板可见标准模块 ∩（`enabled_llm` 开启）∩（深度档位收窄上界），
    与 `generate_all_llm` 的 `depth_gate` 参与判定同源。口径是**参与上界**：
    章本体开关未开时相关模块实际不会被调用，只会让实际费用低于预估（安全方向）。

    Args:
        llm_config: LLM 配置字典；None 时读取 `get_llm_config()`。
        config: 报告配置字典（供深度档位解析）；None 时 `resolve_depth_profile` 自读。

    Returns:
        计划参与的模块后缀列表；配置不可读时为空列表。
    """
    from src.python.core.registry import get_llm_module_names
    from src.python.llm.depth_profile import depth_gate, resolve_depth_profile
    from src.python.llm.skeleton import is_llm_module_enabled

    cfg = llm_config if llm_config is not None else _get_llm_config()
    if not cfg:
        return []
    profile = resolve_depth_profile(config)
    return sorted(
        sfx for sfx in get_llm_module_names() if is_llm_module_enabled(cfg, sfx) and depth_gate(True, sfx, profile)
    )


def _module_model(llm_config: dict[str, Any], module_key: str) -> str:
    """解析模块生效模型：`model_<模块>` 覆写 → 多链首链 → 配置顶层默认。"""
    model = str(llm_config.get(f"model_{module_key}") or "").strip()
    if model:
        return model
    try:
        from src.python.llm.api import _resolve_first_provider_model_endpoint

        chain_model, _ = _resolve_first_provider_model_endpoint(llm_config, module_key)
        if chain_model:
            return str(chain_model)
    except Exception:  # noqa: BLE001 — 链路解析失败回退顶层默认，不阻塞预估
        logger.debug("[cost_forecast] 多链模型解析失败，回退顶层默认", exc_info=True)
    return str(llm_config.get("model") or "")


def _static_module_cost_range(
    llm_config: dict[str, Any],
    module_key: str,
    debate_active: bool,
) -> tuple[float, float] | None:
    """静态兜底区间：输入/输出 token 包络 × 生效模型单价。

    Returns:
        (low, high) 费用数值；模型无法定价时返回 None。
    """
    out_high = int(llm_config.get(f"max_tokens_{module_key}") or _STATIC_OUT_FALLBACK)
    out_low = min(_STATIC_OUT_LOW, out_high)
    model = _module_model(llm_config, module_key)
    low = compute_cost_value(model, _STATIC_IN_LOW, out_low)
    high = compute_cost_value(model, _STATIC_IN_HIGH, out_high)
    if low is None or high is None:
        return None
    if debate_active and module_key == "expert_review":
        # 辩论模式：正/反/综述三次调用（历史缺失时的静态上界口径）
        low *= _DEBATE_CALL_MULT
        high *= _DEBATE_CALL_MULT
    return (low, high)


def _history_module_costs(
    records: list[dict[str, Any]],
    debate_active: bool,
) -> tuple[dict[str, list[float]], int]:
    """从 perf 历史提取逐模块**单次运行**费用样本。

    expert_review 口径与计划参与口径对齐：辩论特征开启时，同一次运行内
    `expert_review`（若发生）与辩论三键之和视为该模块的一次费用样本——
    仅含标准调用的历史样本乘以静态辩论倍数（推断该运行未走辩论）。

    Returns:
        (模块 → 费用样本列表, 贡献样本的运行数)。
    """
    window = records[-_HISTORY_WINDOW_RUNS:]
    per_module: dict[str, list[float]] = {}
    runs_used = 0
    for rec in window:
        llm = rec.get("llm")
        if not isinstance(llm, dict):
            continue
        modules = llm.get("modules")
        if not isinstance(modules, dict) or not modules:
            continue
        runs_used += 1
        for key, entry in modules.items():
            if not isinstance(entry, dict):
                continue
            cost = float(entry.get("cost") or 0.0)
            if key == "expert_review" and debate_active:
                debate_sum = sum(float((modules.get(k) or {}).get("cost") or 0.0) for k in _DEBATE_KEYS)
                if debate_sum > 0:
                    per_module.setdefault(key, []).append(cost + debate_sum)
                else:
                    per_module.setdefault(key, []).append(cost * _DEBATE_CALL_MULT)
                continue
            if debate_active and key in _DEBATE_KEYS:
                # 已并入 expert_review 口径，避免重复计数
                continue
            per_module.setdefault(key, []).append(cost)
    return per_module, runs_used


def forecast_run_cost(
    llm_config: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    *,
    history: list[dict[str, Any]] | None = None,
    force_llm: bool = False,
    force_modules: list[str] | None = None,
) -> dict[str, Any]:
    """给本次生成的 LLM 费用**区间预估**（预估失败返回 ok=False，不抛异常）。

    Args:
        llm_config: LLM 配置字典；None 时读取。
        config: 报告配置字典（深度档位）；None 时自动读取。
        history: perf 历史记录注入（测试用）；None 时读取 perf_history.jsonl。
        force_llm: 全量重新生成（跳过全部已有结果）；与 ``force_modules`` 经
            ``resolve_force_scope`` 归一（与创建运行同源，非法模块键抛 ValueError）。
        force_modules: 模块级重新生成范围（粒度优先于 ``force_llm``）。

    Returns:
        dict：``ok`` 预估是否可用（False → 渠道层跳过确认继续，不阻塞）；
        ``reason`` 失败原因；``modules`` 计划模块；``module_count``；
        ``low``/``high`` 区间（费用数值）；``currency``/``symbol``；
        ``basis`` 依据（``history:<n>``/``static``/``mixed``/``no-modules``）；
        ``history_runs`` 参与样本的运行数；``unpriced`` 无法定价的模块（有历史
        时可缺席）；``detail`` 逐模块 {low, high, samples, basis}；
        ``force_scope`` 重新生成范围（排序模块键，空=默认路径）；范围内模块保证
        重新调用（无缓存折扣），按静态单价口径计价并给出 ``forced_count`` /
        ``forced_low`` / ``forced_high`` 拆分区间（摘要行单独拆行）。
    """
    return _forecast_run_cost_impl(
        llm_config,
        config,
        history=history,
        force_llm=force_llm,
        force_modules=force_modules,
    )


def is_feature_enabled_for_debate() -> bool:
    """辩论模式开关（expert_review 走正/反/综述三调用）。"""
    from src.python.config.features import is_feature_enabled

    try:
        return bool(is_feature_enabled("llm_debate_procon"))
    except Exception:  # noqa: BLE001 — 特性读取失败按关闭处理（预估安全方向由历史兜底）
        return False


def _forecast_run_cost_impl(
    llm_config: dict[str, Any] | None,
    config: dict[str, Any] | None,
    *,
    history: list[dict[str, Any]] | None,
    force_llm: bool = False,
    force_modules: list[str] | None = None,
) -> dict[str, Any]:
    from src.python.llm.force_scope import resolve_force_scope

    cfg = llm_config if llm_config is not None else _get_llm_config()
    planned = resolve_planned_modules(cfg, config)
    # 重新生成范围（与创建运行 resolve_force_scope 同源）；空 = 默认路径（历史口径）
    scope = resolve_force_scope(force_llm, force_modules) if (force_llm or force_modules) else frozenset()
    base: dict[str, Any] = {
        "ok": True,
        "reason": None,
        "modules": planned,
        "module_count": len(planned),
        "force_scope": sorted(scope),
        "forced_count": 0,
        "forced_low": 0.0,
        "forced_high": 0.0,
        "low": 0.0,
        "high": 0.0,
        "currency": PRICING_CURRENCY,
        "symbol": _currency_symbol(),
        "basis": "no-modules",
        "history_runs": 0,
        "unpriced": [],
        "detail": {},
    }
    if not planned:
        return base

    records = history if history is not None else _load_perf_history()
    debate_active = is_feature_enabled_for_debate()
    hist_samples, runs_used = _history_module_costs(records, debate_active)
    base["history_runs"] = runs_used

    low_total = 0.0
    high_total = 0.0
    unpriced: list[str] = []
    detail: dict[str, dict[str, Any]] = {}
    history_parts = 0
    forced_low = 0.0
    forced_high = 0.0
    forced_count = 0
    for sfx in planned:
        samples = hist_samples.get(sfx) or []
        if sfx in scope:
            # 重新生成范围内模块：保证重新调用（无缓存折扣），历史样本含缓存
            # 折扣不再适用——优先静态单价口径；静态不可得时回落历史样本（保守近似）
            rng = _static_module_cost_range(cfg, sfx, debate_active)
            if rng is not None:
                lo, hi = rng
                part_basis = "static"
            elif samples:
                lo, hi = min(samples), max(samples)
                part_basis = "history"
            else:
                unpriced.append(sfx)
                continue
            forced_low += lo
            forced_high += hi
            forced_count += 1
        elif samples:
            lo, hi = min(samples), max(samples)
            part_basis = "history"
            history_parts += 1
        else:
            rng = _static_module_cost_range(cfg, sfx, debate_active)
            if rng is None:
                unpriced.append(sfx)
                continue
            lo, hi = rng
            part_basis = "static"
        low_total += lo
        high_total += hi
        detail[sfx] = {
            "low": round(lo, 6),
            "high": round(hi, 6),
            "samples": len(samples),
            "basis": part_basis,
        }

    if unpriced and not detail:
        base["ok"] = False
        base["reason"] = "模型单价未知且无历史费用样本（不影响生成，仅无法预估）"
        base["unpriced"] = unpriced
        return base

    if history_parts == 0:
        part_basis = "static"
    elif history_parts == len(detail):
        part_basis = f"history:{runs_used}"
    else:
        part_basis = "mixed"
    base.update(
        {
            "low": round(low_total, 6),
            "high": round(high_total, 6),
            "basis": part_basis,
            "unpriced": unpriced,
            "detail": detail,
            "forced_count": forced_count,
            "forced_low": round(forced_low, 6),
            "forced_high": round(forced_high, 6),
        }
    )
    if unpriced:
        base["reason"] = f"部分模块无法定价（{', '.join(unpriced)}），实际费用可能高于区间"
    return base


def daily_cost_limit(llm_config: dict[str, Any] | None = None) -> float:
    """日预算上限（货币数值）；0 = 未启用。非法取值按 0 处理。"""
    cfg = llm_config if llm_config is not None else _get_llm_config()
    try:
        value = float(cfg.get("daily_cost_limit") or 0)
    except (TypeError, ValueError):
        logger.debug("[cost_forecast] daily_cost_limit 取值非法，按未启用处理", exc_info=True)
        return 0.0
    return max(value, 0.0)


def today_llm_cost(history: list[dict[str, Any]] | None = None) -> float:
    """今日（本地日期）已产生的 LLM 费用合计——与 perf 汇总同源。"""
    records = history if history is not None else _load_perf_history()
    today = date.today().isoformat()
    total = 0.0
    for rec in records:
        if not str(rec.get("timestamp") or "").startswith(today):
            continue
        llm = rec.get("llm")
        if isinstance(llm, dict):
            total += float(llm.get("total_cost") or 0.0)
    return round(total, 6)


def budget_status(
    llm_config: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """日预算状态：{enabled, limit, spent, exceeded, currency, symbol}。

    ``exceeded`` 为硬闸判定（``limit > 0 and spent >= limit``）；是否降级/中止
    由渠道层按交互能力处置（交互询问，非交互直接中止）。
    """
    cfg = llm_config if llm_config is not None else _get_llm_config()
    limit = daily_cost_limit(cfg)
    spent = today_llm_cost(history)
    return {
        "enabled": limit > 0,
        "limit": round(limit, 6),
        "spent": spent,
        "exceeded": limit > 0 and spent >= limit,
        "currency": PRICING_CURRENCY,
        "symbol": _currency_symbol(),
    }


def forecast_summary_lines(
    forecast: dict[str, Any],
    budget: dict[str, Any] | None = None,
) -> list[str]:
    """事前预估的纯文本摘要行（渠道层加各自前缀/颜色，不在此处做 UI）。"""
    symbol = forecast.get("symbol") or _currency_symbol()
    lines: list[str] = []
    if forecast.get("ok"):
        if forecast.get("module_count", 0) == 0:
            lines.append("本次生成无 LLM 模块参与，无 API 费用")
        else:
            basis = forecast.get("basis", "")
            if basis.startswith("history:"):
                basis_desc = f"近 {basis.split(':', 1)[1]} 次运行实际费用"
            elif basis == "static":
                basis_desc = "历史不足，按单价静态估算"
            elif basis == "mixed":
                basis_desc = "历史实际费用 + 静态估算"
            else:
                basis_desc = basis or "未知"
            lines.append(
                f"本次生成 LLM 费用预估 {symbol}{forecast['low']:.4f} ~ {symbol}{forecast['high']:.4f}"
                f"（计划 {forecast['module_count']} 个模块，依据：{basis_desc}）"
            )
            forced_count = int(forecast.get("forced_count") or 0)
            if forced_count:
                lines.append(
                    f"其中 {forced_count} 个模块重新生成："
                    f"{symbol}{float(forecast.get('forced_low') or 0.0):.4f} ~ "
                    f"{symbol}{float(forecast.get('forced_high') or 0.0):.4f}"
                )
        if forecast.get("reason"):
            lines.append(f"预估说明：{forecast['reason']}")
    else:
        lines.append(f"费用预估不可用（{forecast.get('reason') or '未知原因'}），不阻塞生成")
    if budget is not None:
        b_symbol = budget.get("symbol") or symbol
        if budget.get("enabled"):
            state = "已达上限" if budget["exceeded"] else "未超限"
            lines.append(
                f"今日已花费 {b_symbol}{budget['spent']:.4f} / 日预算 {b_symbol}{budget['limit']:.4f}（{state}）"
            )
        else:
            lines.append(f"今日已花费 {b_symbol}{budget['spent']:.4f}（未设日预算上限）")
    return lines


__all__ = [
    "budget_status",
    "daily_cost_limit",
    "forecast_run_cost",
    "forecast_summary_lines",
    "resolve_planned_modules",
    "today_llm_cost",
]
