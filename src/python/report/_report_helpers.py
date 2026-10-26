"""报告管线辅助函数子模块 — 轻量行情 / 数据注入 / 完整性校验。

承载管线各阶段的辅助实现：
  - 轻量级行情获取（both 路径，无指数/穿透/分类）
  - 组合演进 / 快照差异数据注入（pipeline_data 键）
  - 校验函数（prepare_report_data / capture_snapshot 完整性断言）
  - 持仓明细 → 行动建议消费字段子集（basic/both 共用）

由 `_report_generation.py`（聚合门面）re-export 对外提供。
"""

from __future__ import annotations

import logging
from typing import Any, cast

from src.python.report.progress import ProgressReporter

logger = logging.getLogger("invest")


# ── 轻量级行情获取（无指数/穿透/分类）──


def _compute_details(holdings: list, reporter: ProgressReporter) -> list:
    """轻量级行情获取，供 both 路径使用。

    仅获取行情明细，不获取指数/穿透/分类数据（与 _cmd_generate_both 语义对齐）。
    """
    from src.python.report.market_value import _generate_details

    reporter.info("正在获取行情数据...")
    details = _generate_details(holdings)
    reporter.ok(f"行情数据获取完成，共 {len(details)} 条")
    return details


# ── 组合演进数据（多快照趋势聚合）──


def _inject_evolution_data(
    pipeline_data: dict | None,
    *,
    snapshot_namespace: str | None = None,
) -> dict:
    """计算组合演进数据并注入 pipeline_data（`evolution_data` 键）。

       聚合 `data/history/snapshots/` 多期快照，供 HTML「组合演进」章节与
       Excel 页签消费。计算失败或数据不足时注入 available=False 的降级 dict，
    展示层写占位文本（§1.4.5），不阻断报告生成（隔离）。

       Args:
           pipeline_data: capture_snapshot 返回的 A 通道数据（可能为 None）
           snapshot_namespace: 快照隔离域（None=共享主目录；如 "web"=web 试算域）

       Returns:
           注入 evolution_data 后的 pipeline_data（None 时新建字典）
    """
    if pipeline_data is None:
        pipeline_data = {}
    try:
        from src.python.analysis.portfolio_evolution import build_evolution_data

        pipeline_data["evolution_data"] = build_evolution_data(snapshot_namespace=snapshot_namespace)
    except Exception:
        logger.warning("[evolution] 组合演进数据构建失败（非关键）", exc_info=True)
        pipeline_data["evolution_data"] = {"available": False, "reason": "组合演进数据构建失败"}
    return pipeline_data


def _inject_snapshot_diff_data(
    pipeline_data: dict | None,
    *,
    snapshot_namespace: str | None = None,
) -> dict:
    """计算快照差异摘要并注入 pipeline_data（`snapshot_diff_data` 键）。

       对比 `data/history/snapshots/` 分属不同交易日的最近两份快照（同一交易日
       多次运行跳过，与环比 diff 同口径，基线由 `load_comparison_baseline` 提供），
       输出组合演进章顶部
       「自上次快照变化摘要」（新增/移除品种 + 集中度 HHI 变化 + 超警戒线品种）。
       有效快照 < 2 期或无更早交易日快照时返回 available=False 的降级 dict，展示层写占位
    （§1.4.5），不阻断报告生成（隔离）。

       Args:
           pipeline_data: capture_snapshot 返回的 A 通道数据（可能为 None）
           snapshot_namespace: 快照隔离域（None=共享主目录；如 "web"=web 试算域）

       Returns:
           注入 snapshot_diff_data 后的 pipeline_data（None 时新建字典）
    """
    if pipeline_data is None:
        pipeline_data = {}
    try:
        from src.python.analysis.snapshot_diff import build_snapshot_diff

        pipeline_data["snapshot_diff_data"] = build_snapshot_diff(snapshot_namespace=snapshot_namespace)
    except Exception:
        logger.warning("[snapshot_diff] 快照差异摘要构建失败（非关键）", exc_info=True)
        pipeline_data["snapshot_diff_data"] = {"available": False, "reason": "快照差异摘要构建失败"}
    return pipeline_data


# ── 校验函数 ──


def _validate_prep_completeness(prep: dict) -> None:
    """校验 prepare_report_data 返回数据的完整性（类型异常只告警，不中断报告）。"""
    if not isinstance(prep, dict):
        logger.warning("[checkpoint] prepare_report_data 返回类型异常: %s", type(prep).__name__)
        return
    for _ck in (
        "total_mv",
        "total_cost",
        "total_profit",
        "total_today_profit",
        "categories",
        "a_indices",
        "holdings_details",
        "today_str",
        "output_dir",
        "news_top_count",
        "risk_metrics",
    ):
        if _ck not in prep:
            logger.warning("[checkpoint] prep 缺失必选键: %s", _ck)
        elif not isinstance(prep.get(_ck), (int, float, dict, list, str, type(None))):
            logger.warning("[checkpoint] prep.%s 类型异常: %s", _ck, type(prep.get(_ck)).__name__)


def _validate_pipeline_snapshot(pipeline_data: dict | None) -> None:
    """校验 capture_snapshot 返回数据的完整性。"""
    if pipeline_data is not None:
        if not isinstance(pipeline_data, dict):
            logger.warning("[checkpoint] capture_snapshot pipeline_data 类型异常: %s", type(pipeline_data).__name__)
            return
        _diff = pipeline_data.get("diff")
        if _diff is not None:
            if not isinstance(_diff, dict):
                logger.warning("[checkpoint] pipeline_data.diff 类型异常: %s", type(_diff).__name__)


# ── 持仓明细 → 行动建议消费字段子集（basic/both 共用） ──


# `attach_holding_trading_days` 已随行装配一并下沉到 `_holding_detail_rows`；
# 此处保留同名导出，既有 `from ..._report_helpers import attach_holding_trading_days` 不变。
from src.python.report._holding_detail_rows import attach_holding_trading_days  # noqa: E402, F401


def _action_holdings_details(details: list, transactions: list | None = None) -> list[dict]:
    """持仓明细 → 行动建议消费的字段子集（与编排路径同一装配点）。

    交易纪律依赖收益率数据（profit_rate），统一换算为百分数（小数 ×100）；
    shares/price 供调仓建议可行化层计算可执行卖出份额与金额；
    channel 为场内/场外渠道上下文（按账户关键词判定），供可行化层按渠道
    计算份额取整与费用（场外整数份 + 赎回费）；account 为账户名原值，供
    收益归因大类分解的单源分类判定场外渠道。

    Args:
        details: DetailRow 列表。
        transactions: 交易流水记录（可为 None）；提供时附加 holding_days
            （再平衡误报防护的「新买入品种观察期」判据）。
    """
    from src.python.report._holding_detail_rows import build_holding_detail_rows

    return build_holding_detail_rows(details, with_market_fields=False, transactions=transactions)


# ── 持仓匿名化（报告管线接线） ──────────────────────────────


def apply_report_anonymization(
    holdings_details: list[dict] | None,
    detail_rows: list | None,
    mode: str | None = None,
    alias_map: dict[str, str] | None = None,
) -> tuple[list[dict], list]:
    """报告管线明细装配边界统一匿名入口（pair，两容器共用同一代号映射）。

    装配边界规则：明细在何处物化（prepare / Excel basic 内部生成 / HTML
    内部生成）就在何处匿名一次，下游渲染、图表数据集、行动建议与 LLM
    提示词持仓块全部同源消费匿名明细。

    - mode None → 读取 ``get_anonymization_mode()``；off → 原样返回（零开销恒等）
    - code_display / full_anonymous → 明细字典与 DetailRow 行同构匿名
      （名称→代号；full 另按千位模糊数值并由模糊值派生盈亏/收益率）。
      代码字段保留真值（键控链路键），「000XXX」显示由明细渲染层与
      产物文本清扫兜底
    - summary → 明细字典折叠为大类聚合行（LLM/行动建议同源消费）；
      DetailRow 行**原样返回**（明细渲染层折叠，合计仍按真值计算）

    Args:
        holdings_details: 行动建议/LLM 消费的明细字典列表（可为 None）
        detail_rows: DetailRow 明细行列表（可为 None）
        mode: 匿名化模式（None → 配置读取）
        alias_map: 预构建的真值→代号映射（保证与文本面清扫编号一致；
            None → 由明细字典/行自行构建）

    Returns:
        (匿名后的明细字典列表, 匿名后的 DetailRow 行列表)
    """
    if mode is None:
        from src.python.config.anonymizer import get_anonymization_mode

        mode = get_anonymization_mode()

    from src.python.config.anonymizer import (
        anonymize_holdings_details,
        fold_details_summary,
        is_anonymization_enabled,
    )

    details = holdings_details or []
    rows = detail_rows or []
    if not is_anonymization_enabled(mode):
        return details, rows

    if mode == "summary":
        return fold_details_summary(details), rows

    # summary 已在上面单独分流（走 fold_details_summary），此处必然是列表形态；
    # anonymize_holdings_details 的联合返回类型在此收窄，避免下游拿到 Union 形态。
    anon_details = cast("list[dict]", anonymize_holdings_details(details, mode))
    if alias_map is None:
        from src.python.config.anonymizer import build_report_alias_map

        alias_map = build_report_alias_map(details or rows, mode)
    anon_rows = [_anonymize_detail_row(row, alias_map, mode) for row in rows]
    return anon_details, anon_rows


def _anonymize_detail_row(row: Any, alias_map: dict[str, str], mode: str) -> Any:
    """对单条 DetailRow 执行字段层匿名（返回新对象，原行不变）。

    code_display：仅名称→代号。full_anonymous：名称→代号，市值/成本千位
    模糊，盈亏与收益率（小数契约）由模糊值派生保持行内恒等，当日盈亏模糊；
    价格/昨收/净值日期等公开行情字段保留。code 保留真值（同字典侧）。
    """
    from dataclasses import replace

    from src.python.config.anonymizer import _blur_value

    updates: dict[str, Any] = {}
    if row.name in alias_map:
        updates["name"] = alias_map[row.name]

    if mode == "full_anonymous":
        mv = _blur_value(row.market_value or 0, 1000) if row.market_value else (row.market_value or 0.0)
        cost = _blur_value(row.cost or 0, 1000) if row.cost else (row.cost or 0.0)
        updates["market_value"] = mv
        updates["cost"] = cost
        updates["profit"] = round(mv - cost, 2)
        updates["profit_rate"] = (mv - cost) / cost if cost else None
        updates["today_profit"] = (
            _blur_value(row.today_profit or 0, 1000) if row.today_profit else (row.today_profit or 0.0)
        )

    if not updates:
        return row
    return replace(row, **updates)


def fold_detail_rows_summary(rows: list) -> list:
    """summary 模式：明细行按大类折叠为同构聚合 DetailRow（明细渲染层拦截点）。

    在账户分组**之内**折叠（同账户各大类一行），账户小计 = 各聚合行之和，
    口径不变。行保持 DetailRow 形态，明细表模板/序列化器零改动。
    分类基于真实名称/代码（summary 模式下字段层不替换明细行，
    分类判定发生在匿名化之前的真实值上）。
    """
    from dataclasses import replace

    from src.python.core.code_utils import is_fund_holding

    buckets: dict[str, list] = {}
    for row in rows:
        cat = "基金" if is_fund_holding(row.name, row.code, row.account) else "股票/其他"
        buckets.setdefault(cat, []).append(row)

    labels = {"基金": "基金汇总", "股票/其他": "股票汇总"}
    folded: list = []
    for cat, items in buckets.items():
        first = items[0]
        cost = sum(i.cost or 0 for i in items)
        mv = sum(i.market_value or 0 for i in items)
        profit = sum(i.profit or 0 for i in items)
        folded.append(
            replace(
                first,
                name=labels.get(cat, f"{cat}汇总"),
                code="",
                shares=sum(i.shares or 0 for i in items),
                market_value=mv,
                cost=cost,
                profit=profit,
                profit_rate=(mv - cost) / cost if cost else None,
                today_profit=sum(i.today_profit or 0 for i in items),
            )
        )
    return folded
