"""摘要区「本期要点」派生模块。

从 ``pipeline_data`` 的快照环比数据（``diff`` 键，由 ``report/_snapshot.py``
的 ``capture_snapshot`` 计算注入）纯内存派生首屏执行摘要契约：关键指标环比行
（总市值 / 总收益率 / 持仓数 / 集中度）+ 本期关键变化 Top N（新增/清仓/
大幅加减仓，按市值变化绝对值降序）。

设计约束：
  - 零取数零计算复用——不发请求、不读快照文件，只消费管线内既有 diff；
  - 单一数据源——组合级环比取 ``diff``，集中度环比取 ``snapshot_diff_data``
    的 ``hhi_change``（同为快照 diff 产物；演进开关关闭时该键缺席 → 集中度
    行省略，属行级降级，不隐藏整块）；
  - 无上期快照（``diff`` 缺席或 ``is_first_check``）→ 返回 None → 渲染层
    整块隐藏（不写占位，首屏不出现降级痕迹）。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("invest")

#: 关键变化默认展示条数上限（plan 目标 3~5 条，取 5）
_DEFAULT_MAX_CHANGES = 5


def build_summary_highlights(
    pipeline_data: dict | None,
    *,
    max_changes: int = _DEFAULT_MAX_CHANGES,
) -> dict | None:
    """派生摘要区「本期要点」数据契约。

    Args:
        pipeline_data: 管线数据字典（含 ``diff`` 与可选 ``snapshot_diff_data`` 键），
            首次运行/非正式持仓源时可能为 None
        max_changes: 关键变化展示条数上限（默认 5）

    Returns:
        契约 dict；无上期快照可对比时返回 None（渲染层整块隐藏）：
          - days_since_last_report: 距上次报告天数
          - baseline_trading_day: 对比基线报告的所属交易日（YYYY-MM-DD；基线时间戳
            不可解析时为 ""，渲染层省略对比基准行）
          - baseline_generated_at: 对比基线报告的生成时间（YYYY-MM-DD HH:MM，同上降级）
          - total_value_diff / total_value_diff_pct: 总市值环比金额与比率
          - qdii_value_diff / qdii_lagged: 环比中含有的 QDII 官方净值变动金额及
            是否滞后口径（T-1）——供渲染层在环比行下注明「其中 QDII …」，无 QDII
            或变动为 0 时渲染层省略该注
          - total_pnl_diff / total_pnl_pct_diff: 总盈亏环比金额与盈亏率百分点
          - holding_count_delta: 持仓数环比（新增品种数 - 清仓品种数）
          - added_count / removed_count: 本期新增/清仓品种数（持仓数环比注脚）
          - hhi_change: 集中度 HHI 环比（本期 - 上期；快照差异摘要不可得时 None，
            渲染层省略该行）
          - changes: 关键变化列表（按 |value_diff| 降序，最多 max_changes 条），
            每项 {name, code, action, value_diff, shares_diff}
          - change_total: 全部变化条数（超上限时渲染层写「等 N 条」提示）
    """
    diff = (pipeline_data or {}).get("diff")
    if not diff or diff.get("is_first_check"):
        return None

    changes: list[dict] = []
    for action_key in ("added", "removed", "increased", "decreased"):
        for item in diff.get(action_key) or []:
            changes.append(
                {
                    "name": item.get("name", ""),
                    "code": item.get("code", ""),
                    "action": item.get("action", ""),
                    "value_diff": item.get("value_diff", 0.0),
                    "shares_diff": item.get("shares_diff", 0.0),
                }
            )
    # 关键变化按市值变化绝对值降序（结构性变化——新增/清仓——通常金额大，
    # 自然排前；同额时保持 added→removed→increased→decreased 稳定顺序）
    changes.sort(key=lambda c: abs(c["value_diff"]), reverse=True)
    change_total = len(changes)

    added_count = len(diff.get("added") or [])
    removed_count = len(diff.get("removed") or [])

    # 集中度环比：取快照差异摘要（演进开关关闭时键缺席 → None → 行省略）
    hhi_change = None
    snap_diff = (pipeline_data or {}).get("snapshot_diff_data") or {}
    if snap_diff.get("available"):
        hhi_change = snap_diff.get("hhi_change")

    return {
        "days_since_last_report": diff.get("days_since_last_report", 0),
        "baseline_trading_day": diff.get("baseline_trading_day", ""),
        "baseline_generated_at": diff.get("baseline_generated_at", ""),
        "total_value_diff": diff.get("total_value_diff", 0.0),
        "total_value_diff_pct": diff.get("total_value_diff_pct", 0.0),
        "qdii_value_diff": diff.get("qdii_value_diff", 0.0),
        "qdii_lagged": bool(diff.get("qdii_lagged", False)),
        "total_pnl_diff": diff.get("total_pnl_diff", 0.0),
        "total_pnl_pct_diff": diff.get("total_pnl_pct_diff", 0.0),
        "holding_count_delta": added_count - removed_count,
        "added_count": added_count,
        "removed_count": removed_count,
        "hhi_change": hhi_change,
        "changes": changes[:max_changes],
        "change_total": change_total,
    }
