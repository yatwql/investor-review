"""LLM 生成后一遍：事实锚定 → 生成后自检 → 跨模块一致性核对。

顺序是契约（不是实现细节）：锚定把每个模块的正文对齐到本次数据（可能改写正文并回写
缓存），自检与跨模块核对都读**锚定之后**的正文，且在自检输入里必须剥掉「运行元信息」
（LLM 用量页脚 + 校验摘要/建议提及/已修正明细）——否则同一份分析正文会因缓存态不同
算出不同的自检缓存键，表现为「上游重算后必多一次自检调用」。

本模块只做这三步编排与调用；正文渲染、缓存判定、worker 分发不在此处。`run_fact_check`
与 `run_self_review` 的调用点在这里，测试对这些名字的 patch 目标随之落在本模块
（`src.python.llm._llm_post_pass.run_fact_check`）。
"""

from __future__ import annotations

import logging
from typing import Any

from src.python.llm.fact_checker import run_fact_check

from src.python.llm._llm_context_blocks import (
    LlmContextBlocks,
    extract_historical_codes,
)

logger = logging.getLogger("invest")

#: 四基础模块（顺序即返回元组位序，供调用方按位取回）。
BASE_MODULES: tuple[str, ...] = ("global_macro", "expert_review", "health_check", "penetration_deep")


def review_text(html: str | None) -> str | None:
    """自检/跨模块核对的输入：只留分析正文，剥掉用量页脚与校验产物段落。

    两者都是「本次运行的元信息」而非分析结论：页脚随缓存态必然不同（新生成含
    Token/耗时/费用，命中含"使用缓存"），校验摘要的检查项计数随缓存态变化、
    修正条数随正文变化。任一混进输入，同一份分析正文都会算出不同的缓存键。
    报告渲染仍用含这两段的完整正文。
    """
    if not html:
        return html
    from src.python.llm.fact_checker import strip_fact_check_blocks
    from src.python.llm.skeleton import strip_llm_footer

    return strip_fact_check_blocks(strip_llm_footer(html))


def _penetrated_codes(penetrated_assets: list[dict] | None) -> set[str]:
    """穿透资产里的股票代码（穿透分析/智囊团/体检的品种存在性白名单）。"""
    codes: set[str] = set()
    for asset in penetrated_assets or []:
        codes.update((asset or {}).get("codes") or [])
    return codes


def anchor_fact_checks(
    contents: dict[str, str | None],
    cached: dict[str, bool],
    *,
    holdings_details: list[dict] | None,
    penetrated_assets: list[dict] | None,
    pipeline_data: dict | None,
    history_data: dict | None,
    llm_config: dict | None,
    cache_info: dict,
    module_labels: dict[str, str],
) -> dict[str, str | None]:
    """对四模块正文逐个做事实校验（仅非空模块），返回锚定后的正文。

    缓存命中同样校验：内容基于生成时的快照，数值/品种仍可能与本轮数据不符；但排名
    校验跳过（用当前市值校验旧快照的排名声称会因价格变动误报）。

    修正只改产出不改输入：缓存键（内容寻址生成输入）不变，正文一变就得回写缓存——
    否则每次运行重做同一批修正，且展示正文与缓存正文口径不一致（不可复现）。回写时机
    在摘要拼接前：摘要是当轮元信息，不能混进缓存正文。
    """
    from src.python.config import get_llm_setting_default

    if not holdings_details or not any(contents.get(key) for key in BASE_MODULES):
        return dict(contents)

    fc_cfg = (llm_config or {}).get("fact_check", {})
    tolerance: float = fc_cfg.get("tolerance", get_llm_setting_default("fact_check.tolerance"))
    overrides: dict = fc_cfg.get("tolerance_overrides", {})

    # 智囊团/体检/穿透三模块提示词均含【穿透 TOP10】，LLM 会引用穿透股票代码——它们非
    # 直接持仓但属穿透范围，须作为额外有效集，否则误报「不在当前持仓中」。全球政经
    # 提示词不含穿透数据，保持严格校验。历史代码（已清仓/已变动）经统一附录进四模块，
    # 故对所有模块均有效。
    penetrated = _penetrated_codes(penetrated_assets)
    historical = extract_historical_codes(pipeline_data)

    anchored = dict(contents)
    for module_key in BASE_MODULES:
        result = anchored.get(module_key)
        if not result:
            continue
        extra_valid = (
            (penetrated if module_key in ("penetration_deep", "expert_review", "health_check") else set()) | historical
        ) or None
        corrected, summary = run_fact_check(
            result,
            holdings_details,
            module_label=module_labels.get(module_key, module_key),
            extra_valid_codes=extra_valid,
            is_penetration_module=module_key == "penetration_deep",
            tolerance_pct=overrides.get(module_key, tolerance),
            history_data=history_data,
            skip_ranking_check=cached.get(module_key, False),
        )
        if corrected != result and corrected != summary:
            from src.python.llm.skeleton import write_back_module_cache

            write_back_module_cache(
                corrected,
                cache_key=(cache_info.get(module_key) or {}).get("key", ""),
                module_key=module_key,
                cached=cached.get(module_key, False),
            )
            result = corrected
        if summary and summary not in result:
            result = result + "\n" + summary
        anchored[module_key] = result
    return anchored


def apply_generation_post_pass(
    contents: dict[str, str | None],
    *,
    holdings_details: list[dict] | None,
    penetrated_assets: list[dict] | None,
    llm_config: dict | None,
    force_self_review: bool,
    blocks: LlmContextBlocks,
    module_labels: dict[str, str],
) -> None:
    """生成后自检 + 跨模块一致性核对（两者都读锚定后的正文，副产物落运行作用域载体）。

    自检的输入是四模块产出的纯分析正文；跨模块核对是纯算术判定、零 token，检出时并入
    复核区块**最前**（事实先于观点）。
    """
    _record_research_contracts(contents)

    from src.python.llm.self_review import run_self_review

    run_self_review(
        {module_key: review_text(contents.get(module_key)) for module_key in BASE_MODULES},
        holdings_details,
        penetrated_assets,
        llm_config,
        force=force_self_review,
        purchase_constraint_block=blocks.purchase_constraint_block,
        holding_change_block=blocks.holding_change_block,
        event_impact_block=blocks.event_impact_block,
        schedule_replay_block=blocks.schedule_replay_block,
    )

    # 单模块事实校验只回答「这段文字与本模块数据是否相符」，看不出模块之间互相打架
    # （实测同一只基金一处 -8.5%、两处 -5.06%）。这类冲突是纯算术可判定的，放在模型层
    # 自检之外做；检出时并入复核区块最前方。
    from src.python.llm.fact_checker import build_cross_module_block, check_cross_module_claims
    from src.python.llm.self_review import prepend_review_block

    cross_issues = check_cross_module_claims(
        {
            module_labels.get(module_key, module_key): review_text(contents.get(module_key)) or ""
            for module_key in BASE_MODULES
        },
        holdings_details,
    )
    if cross_issues:
        prepend_review_block(build_cross_module_block(cross_issues))
        logger.info("[cross_module] 检出 %d 处跨模块收益率口径冲突", len(cross_issues))


def _record_research_contracts(contents: dict[str, str | None]) -> None:
    """解析各模块的结构化契约头并校验（开关关闭时零行为）。

    证据索引由提示词构建侧登记（`record_evidence_index`），此处按同一份索引校验——
    模型只能引用它真正看到的证据；校验失败只标注「未验证」，不阻断报告。
    """
    from src.python.llm.research_contract import (
        get_evidence_index,
        is_enabled,
        parse_contract,
        record_module_contract,
        validate_contract,
    )

    if not is_enabled():
        return
    index = get_evidence_index()
    try:
        from src.python.core.market_hours import market_snapshot_bucket

        as_of = market_snapshot_bucket().as_of
    except Exception:  # 口径桶不可用不阻断：as_of 仅记录用途
        as_of = ""
    for module_key in BASE_MODULES:
        payload = parse_contract(contents.get(module_key))
        record_module_contract(module_key, validate_contract(payload, index, as_of=as_of))


def contents_from_results(
    precheck_results: dict,
    worker_results: dict,
    *,
    module_keys: tuple[str, ...] = BASE_MODULES,
) -> tuple[dict[str, str | None], dict[str, bool]]:
    """合并预检与 worker 结果，按位取出四模块正文与命中标志。

    Args:
        precheck_results: 预检结果（`{module: {result, cached}}`）。
        worker_results: 线程池结果（`{module: (content, from_cache)}`，覆盖预检项）。
        module_keys: 取用顺序（默认四基础模块，即返回元组的位序）。

    Returns:
        `(contents, cached)`：两个按 `module_keys` 顺序的字典。
    """
    merged = dict(precheck_results)
    for key, value in (worker_results or {}).items():
        if key in merged:
            merged[key] = value

    contents: dict[str, str | None] = {}
    cached: dict[str, bool] = {}
    for key in module_keys:
        entry: Any = merged.get(key, {})
        if isinstance(entry, tuple):  # worker 结果形态 (content, from_cache)
            contents[key], cached[key] = entry[0], bool(entry[1])
        else:
            contents[key], cached[key] = entry.get("result"), bool(entry.get("cached", False))
    return contents, cached


__all__ = [
    "BASE_MODULES",
    "anchor_fact_checks",
    "apply_generation_post_pass",
    "contents_from_results",
    "review_text",
]
