"""LLM 分析章的上下文块装配（块实例单次渲染的落点）。

为什么单独成模块：六类上下文块（竞争语境 / 数据质量详细状态 / 申购限购约束 /
持仓变动复盘 / 事件窗分歧例 / 调仓纪律回放引用）有一条共同不变式——**同一份块文本
既要进缓存指纹（经预检）、又要进提示词（经分发）**。两个消费点若各自渲染一次，
「进键的文本」与「进提示词的文本」就只能靠纪律对齐：渲染器一改而键不动，预检就会
命中旧键、复用按旧输入算出的结论（且不报错）。故块在这里渲染/提取一次，收成
:class:`LlmContextBlocks` 快照，由调用方把**同一实例**分别交给指纹与提示词，
结构契约用例以 `is` 身份断言守护（见 `test_generate_all_llm_contract.py`）。

本模块只做「渲染一次 / 提取一次 / 缺省归一」，不做缓存判定、不调 LLM、不写盘。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.python.llm.prompts import (
    _build_competitive_context_block,
    _build_data_quality_detail_block,
)

logger = logging.getLogger("invest")


@dataclass(frozen=True)
class LlmContextBlocks:
    """六类上下文块的取值快照（渲染一次后即固定，供指纹与提示词共用）。"""

    competitive_context: str
    data_quality_text: str
    purchase_constraint_block: str
    holding_change_block: str
    event_impact_block: str
    schedule_replay_block: str

    def fingerprint_kwargs(self) -> dict[str, str]:
        """交给指纹构造（`_compute_module_cache_info`）的关键字参数。"""
        return {
            "competitive_context": self.competitive_context,
            "data_quality_text": self.data_quality_text,
            "purchase_constraint_block": self.purchase_constraint_block,
            "holding_change_block": self.holding_change_block,
            "event_impact_block": self.event_impact_block,
            "schedule_replay_block": self.schedule_replay_block,
        }

    def prompt_kwargs(self) -> dict[str, str]:
        """交给 worker 分发（提示词附录）的关键字参数（与指纹侧同名同值）。"""
        return self.fingerprint_kwargs()


def build_context_blocks(
    *,
    a_indices: dict[str, dict[str, Any]],
    total_mv: float,
    total_today_profit: float,
    comparison_indices: dict[str, str] | None,
    history_data: dict | None,
    metrics: dict | None,
    degradation_events: list[dict] | None,
    pipeline_data: dict | None,
) -> LlmContextBlocks:
    """渲染/提取六类上下文块并收成快照（每块只产出一次）。

    Args:
        a_indices: A 股指数行情（竞争语境块用）。
        total_mv / total_today_profit: 组合总市值与当日盈亏（竞争语境块用）。
        comparison_indices: `{代码: 名称}` 对比指数池。
        history_data: 组合历史走势数据（含风险指标）。
        metrics: 量化指标字典（`compute_all_metrics()` 输出）。
        degradation_events: 降级跟踪器日志；渲染成数据质量详细状态块**一次**，
            否则数据源恢复后仍会复用故障期间缓存的健康结论。
        pipeline_data: 管线数据契约（四个「构建期已渲染」的块从中提取同一实例）。

    Returns:
        六类块的不可变快照。
    """
    blocks = LlmContextBlocks(
        # 竞争语境块：此处渲染一次，同一实例既进指纹（经预检）又进提示词（经 worker）。
        competitive_context=_build_competitive_context_block(
            a_indices,
            total_mv,
            total_today_profit,
            comparison_indices=comparison_indices,
            history_data=history_data,
            metrics=metrics,
        ),
        # 数据质量详细状态块：同样渲染一次；一并注入 data_freshness 契约——体检第 5 维
        # 要评净值新鲜度，其基准是交易日（非运行时刻），且滞后清单须与「数据质量
        # 仪表盘」可信度区块同源。
        data_quality_text=_build_data_quality_detail_block(
            degradation_events, (pipeline_data or {}).get("data_freshness")
        ),
        # 以下四块由契约构建期（report 侧）渲染一次，此处只提取同一实例。
        purchase_constraint_block=extract_purchase_constraint_block(pipeline_data),
        holding_change_block=extract_holding_change_block(pipeline_data),
        event_impact_block=extract_event_impact_block(pipeline_data),
        schedule_replay_block=extract_schedule_replay_block(pipeline_data),
    )
    _log_block_presence(blocks)
    return blocks


def _log_block_presence(blocks: LlmContextBlocks) -> None:
    """逐块打一行 DEBUG：注入了多少行 / 缺席时提示词与缓存键回退原样。"""
    for label, text in (
        ("申购限购约束块", blocks.purchase_constraint_block),
        ("持仓变动复盘提示词块", blocks.holding_change_block),
        ("事件窗分歧例块", blocks.event_impact_block),
        ("调仓纪律回放引用块", blocks.schedule_replay_block),
    ):
        if text:
            logger.debug("%s注入 LLM 分析章（含表头共 %d 行）", label, text.count("\n") + 1)
        else:
            logger.debug("%s缺席，提示词与缓存键回退原样", label)


def extract_purchase_constraint_block(pipeline_data: dict | None) -> str:
    """从管线数据提取申购限购约束块（契约字段 ``constraint_block`` 的唯一提取点）。

    消费方两处必须同源读取：本编排层（LLM 分析章统一附录与指纹）与报告侧新闻
    批量链（``report/_llm_news.py``）。契约键名或嵌套调整只改此处，避免两份
    表达式漏改一处导致块静默缺席（降级面被误触）。

    Args:
        pipeline_data: 管线数据字典（可为 None，如无管线上下文的直调路径）。

    Returns:
        约束块原文；契约缺席（None/字段缺/降级产出空串）→ ``""``（提示词与缓存键回退原样）。
    """
    return str(((pipeline_data or {}).get("purchase_status_data") or {}).get("constraint_block") or "")


def extract_holding_change_block(pipeline_data: dict | None) -> str:
    """从管线数据提取持仓变动复盘提示词块（契约字段 ``prompt_block`` 的唯一提取点）。

    契约（``holding_change_data``）由报告 seam 注入，构建期已渲染一次；此处只提取
    同一实例，同时交预检侧指纹与写侧提示词（进提示词必进指纹，见 module_fingerprint）。

    Args:
        pipeline_data: 管线数据字典（可为 None，如无管线上下文的直调路径）。

    Returns:
        提示词块原文；契约缺席（开关关闭/准入未过/字段缺）→ ``""``（提示词与缓存键回退原样）。
    """
    return str(((pipeline_data or {}).get("holding_change_data") or {}).get("prompt_block") or "")


def extract_event_impact_block(pipeline_data: dict | None) -> str:
    """从管线数据提取事件窗分歧例提示词块（契约字段 ``prompt_block`` 的唯一提取点）。

    契约（``event_impact_data``）由报告 seam 在新闻获取后注入，构建期已渲染一次；
    此处只提取同一实例，同时交预检侧指纹与写侧提示词（进提示词必进指纹，
    见 module_fingerprint）。

    Args:
        pipeline_data: 管线数据字典（可为 None，如无管线上下文的直调路径）。

    Returns:
        块原文；契约缺席（开关关闭/无分歧例/字段缺）→ ``""``（提示词与缓存键回退原样）。
    """
    return str(((pipeline_data or {}).get("event_impact_data") or {}).get("prompt_block") or "")


def extract_schedule_replay_block(pipeline_data: dict | None) -> str:
    """从管线数据提取调仓纪律回放引用提示词块（契约字段 ``prompt_block`` 的唯一提取点）。

    契约（``schedule_replay_data``）由报告 seam 装配（快照与持仓变动注入后），
    构建期已渲染一次；此处只提取同一实例，同时交预检侧指纹与写侧提示词（进提示词
    必进指纹，见 module_fingerprint）。

    Args:
        pipeline_data: 管线数据字典（可为 None，如无管线上下文的直调路径）。

    Returns:
        块原文；契约缺席（开关关闭/回放数据不足/字段缺）→ ``""``（提示词与缓存键回退原样）。
    """
    return str(((pipeline_data or {}).get("schedule_replay_data") or {}).get("prompt_block") or "")


def extract_historical_codes(pipeline_data: dict | None) -> set[str]:
    """从管线数据提取历史（已清仓/已变动）品种代码，供事实校验品种存在性白名单。

    LLM 提示词含两类历史代码来源：
      - 【环比变化】块（``pipeline_data["diff"]`` 的 removed/added 行，如
        "清仓: 易方达国证自由现金流ETF(159222)"）——进 expert_review / health_check；
      - 统一附录【持仓变动复盘】块（``holding_change_data.events`` 的 code，
        含跨期变动品种）——进四个模块。

    这些代码非当前持仓，但属 LLM 合法引用的历史语境（如"环比看，清仓某品种(159222)
    后…"）。不纳入有效集会被品种存在性校验误报"不在当前持仓中"。

    Args:
        pipeline_data: 管线数据字典（可为 None）。

    Returns:
        历史品种代码集合（无数据时为空集）。
    """
    codes: set[str] = set()
    _data = pipeline_data or {}
    _diff = _data.get("diff") or {}
    for _side in ("removed", "added"):
        for _item in _diff.get(_side) or []:
            _code = (_item or {}).get("code") or ""
            if _code:
                codes.add(str(_code))
    for _ev in (_data.get("holding_change_data") or {}).get("events") or []:
        _code = (_ev or {}).get("code") or ""
        if _code:
            codes.add(str(_code))
    return codes


__all__ = [
    "LlmContextBlocks",
    "build_context_blocks",
    "extract_event_impact_block",
    "extract_historical_codes",
    "extract_holding_change_block",
    "extract_purchase_constraint_block",
    "extract_schedule_replay_block",
]
