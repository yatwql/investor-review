"""单次测量编排：重置会话用量 → 临时替换提示词/开关 → 生成 → 采集度量。

真实 LLM 调用只发生在本模块的 ``generate`` 分支；``dry_run=True`` 时只返回计划，
不触网（供 CLI 自检与单测使用）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import measure, repair
from .budget import DEFAULT_TIER, BUDGET_TIERS, build_budget_block, build_debate_budget_block
from .prompts import debate_flags, patched_features, patched_prompts

logger = logging.getLogger(__name__)

STANDARD_MODES = ("standard", "standard-conditional")
DEBATE_MODES = ("debate", "debate-conditional")
ALL_MODES = STANDARD_MODES + DEBATE_MODES


def _call_standard(sample: dict[str, Any]) -> tuple[str | None, bool]:
    from src.python.llm.generators_singletons import generate_expert_review

    return generate_expert_review(
        sample["total_mv"],
        sample["total_cost"],
        sample["total_profit"],
        sample["total_today_profit"],
        sample["holdings_count"],
        sample["categories"],
        sample.get("penetrated_assets") or [],
        holdings_details=sample["holdings_details"],
        force=True,
        pipeline_data=sample.get("pipeline_data") or {},
        competitive_context=sample.get("competitive_context") or "",
        metrics=sample.get("metrics") or {},
    )


def _call_debate(sample: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    from src.python.llm.generators import generate_debate_procon

    return generate_debate_procon(
        sample["total_mv"],
        sample["total_cost"],
        sample["total_profit"],
        sample["total_today_profit"],
        sample["holdings_count"],
        sample["categories"],
        sample.get("penetrated_assets") or [],
        holdings_details=sample["holdings_details"],
        force=True,
        pipeline_data=sample.get("pipeline_data") or {},
        competitive_context=sample.get("competitive_context") or "",
        metrics=sample.get("metrics") or {},
    )


def _repair_once(text: str, block: str, codes: list[str]) -> tuple[str, dict[str, Any]]:
    """执行一次补写：走生产同一条 ``call_llm`` 链路（Provider Chain 必经）。"""
    from src.python.config import get_llm_config
    from src.python.llm.api import call_llm

    llm_config = get_llm_config() or {}

    def _caller(system: str, user: str) -> tuple[str | None, dict | None]:
        content, usage, _provider = call_llm(
            system,
            user,
            llm_config,
            timeout=60.0,
            max_tokens=1200,
            config_field="max_tokens_expert_review",
            temperature=0.1,
        )
        return content, usage

    return repair.repair_text(text, block=block, codes=codes, caller=_caller)


def _usage_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    """会话累计用量的差（生成期间产生的 token）。"""
    return {
        "input_tokens": int(after.get("input_tokens", 0)) - int(before.get("input_tokens", 0)),
        "output_tokens": int(after.get("output_tokens", 0)) - int(before.get("output_tokens", 0)),
        "call_count": int(after.get("call_count", 0)) - int(before.get("call_count", 0)),
    }


def run_case(
    mode: str,
    sample: dict[str, Any],
    *,
    budget_chars: int | None = None,
    dry_run: bool = False,
    keep_text: bool = False,
    do_repair: bool = False,
) -> dict[str, Any]:
    """跑一次（模式 × 预算）测量。

    Args:
        mode: ``standard`` / ``standard-conditional`` / ``debate`` / ``debate-conditional``。
        sample: 冻结样本（``sample.load_sample`` 的产物）。
        budget_chars: 标准模式的预算字数；None 取 ``DEFAULT_TIER``。辩论路径用固定单篇下限。
        dry_run: True 时不调用 LLM，只返回将执行的计划（供自检）。
        keep_text: True 时在记录里保留输出摘录（前 1,500 + 末 500 字），用于排查解析问题。
        do_repair: True 时对缺失结构追加一次短补写（评测实验，验证兜底是否有效）。

    Returns:
        单次测量记录：模式 / 预算 / 墙钟 / token / 分段字数 / 要素机检 / 操作建议表。
    """
    if mode not in ALL_MODES:
        raise ValueError(f"未知模式：{mode}")
    chars = budget_chars if budget_chars is not None else BUDGET_TIERS[DEFAULT_TIER]
    plan = {
        "mode": mode,
        "budget_chars": chars if mode in STANDARD_MODES else None,
        "flags": debate_flags(mode),
        "is_debate": mode in DEBATE_MODES,
    }
    if dry_run:
        return {**plan, "dry_run": True}

    from src.python.llm.session import get_session_usage, reset_session_usage

    standard_suffix = build_budget_block(chars) if mode in STANDARD_MODES else ""
    debate_suffixes = (
        {
            "pro": build_debate_budget_block("pro"),
            "con": build_debate_budget_block("con"),
            "synthesis": build_debate_budget_block("synthesis"),
            "synthesis_conditional": build_debate_budget_block("synthesis_conditional"),
        }
        if mode in DEBATE_MODES
        else None
    )

    reset_session_usage()
    before = get_session_usage()
    started = time.monotonic()
    with patched_features(debate_flags(mode)), patched_prompts(standard_suffix, debate_suffixes=debate_suffixes):
        if mode in STANDARD_MODES:
            text, _cached = _call_standard(sample)
            parts = [text or ""]
        else:
            pro, con, synthesis = _call_debate(sample)
            parts = [part or "" for part in (pro, con, synthesis)]
    duration = time.monotonic() - started
    after = get_session_usage()
    joined = "\n\n".join(part for part in parts if part)

    repair_info: dict[str, Any] = {"repaired": False}
    if do_repair:
        repair_started = time.monotonic()
        for block in repair.missing_blocks(joined, mode=mode):
            codes = measure.count_action_rows(joined)["codes"] or [
                row["code"] for row in sample["holdings_details"][:12]
            ]
            joined, repair_info = _repair_once(joined, block, codes)
            if repair_info.get("repaired"):
                logger.info(
                    "[eval] 补写完成：%s（%s tokens）", block, (repair_info.get("usage") or {}).get("output_tokens")
                )
        repair_info["seconds"] = round(time.monotonic() - repair_started, 2)

    record = {
        **plan,
        "dry_run": False,
        "duration_seconds": round(duration, 2),
        **_usage_delta(before, after),
        "chars": sum(len(part) for part in parts),
        "sections": measure.section_char_counts(joined),
        "elements": measure.check_elements(joined),
        "actions": measure.count_action_rows(joined),
        "parts": len(parts),
        "repair": repair_info,
    }
    if keep_text:
        record["text_excerpt"] = joined[:1500] + ("\n…\n" + joined[-500:] if len(joined) > 1500 else "")
    logger.info(
        "[eval] %s 预算=%s 墙钟=%.1fs 输出=%s tokens 字数=%d 要素缺失=%s",
        mode,
        plan["budget_chars"] or "单篇下限",
        duration,
        record["output_tokens"],
        record["chars"],
        record["elements"]["missing"],
    )
    return record


def run_matrix(
    sample: dict[str, Any],
    *,
    modes: tuple[str, ...] = ALL_MODES,
    tiers: tuple[str, ...] = ("6000", "4800", "4000", "3200"),
    repeats: int = 3,
    dry_run: bool = False,
    keep_text: bool = False,
    do_repair: bool = False,
) -> list[dict[str, Any]]:
    """按「模式 × 档位 × 重复」跑矩阵。

    辩论模式只跑一次档位（固定单篇下限），避免 4×4×3 的组合爆炸；标准模式按
    ``tiers`` 逐档、每档 ``repeats`` 次。

    Args:
        sample: 冻结样本。
        modes: 要跑的模式；默认全部四条（回退路径与标准同提示词，由 standard 覆盖）。
        tiers: 标准模式的候选档位。
        repeats: 每个组合的重复次数（取 p50 用于判定）。
        dry_run: True 时只输出计划，不调用 LLM。
        keep_text: 是否在记录里保留输出摘录（排查解析问题时用）。
        do_repair: 是否对缺失结构做一次短补写（评测实验）。

    Returns:
        单次测量记录列表。
    """
    records: list[dict[str, Any]] = []
    for mode in modes:
        budget_list: tuple[int | None, ...]
        if mode in STANDARD_MODES:
            budget_list = tuple(BUDGET_TIERS[tier] for tier in tiers)
        else:
            budget_list = (None,)
        for chars in budget_list:
            for index in range(repeats):
                record = run_case(
                    mode, sample, budget_chars=chars, dry_run=dry_run, keep_text=keep_text, do_repair=do_repair
                )
                record["repeat_index"] = index
                records.append(record)
    return records
