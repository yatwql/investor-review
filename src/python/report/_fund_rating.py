"""基金评级内核：评级判定、超额收益修正与收益率/排名格式化。

纯计算层（不写 Excel）——页签写入编排仍在 :mod:`report.fund_performance`。
"""

from __future__ import annotations

import logging
import re
from typing import Any


logger = logging.getLogger("invest")


_RATING_COMMENT: dict[str, str] = {
    "优秀": "优秀 持续跑赢基准，超额收益显著",
    "良好": "良好 稳定跑赢基准，组合管理得当",
    "稳定": "稳定 收益率稳健，波动控制良好",
    "偏差": "偏差 近期表现欠佳，需关注持仓变化",
    "较差": "较差 同类排名靠后，建议评估持续持有理由",
}


_RATING_ORDER = ["较差", "偏差", "稳定", "良好", "优秀"]


_DEFAULT_EXCESS_THRESHOLD_UP = 80


_DEFAULT_EXCESS_THRESHOLD_DOWN = 40


def _get_excess_thresholds() -> tuple[int, int]:
    """从 config.json 读取超额收益评分阈值，失败时返回内置默认值。"""
    try:
        from src.python.config import get_config

        cfg = get_config().get("performance_evaluation", {})
        up = int(cfg.get("excess_threshold_up", _DEFAULT_EXCESS_THRESHOLD_UP))
        down = int(cfg.get("excess_threshold_down", _DEFAULT_EXCESS_THRESHOLD_DOWN))
        return up, down
    except (TypeError, ValueError, KeyError):
        return _DEFAULT_EXCESS_THRESHOLD_UP, _DEFAULT_EXCESS_THRESHOLD_DOWN


def _format_return(val: Any) -> float | str:
    """格式化收益率为小数（供 Excel 百分比格式使用）。

    Returns:
        小数（如 0.0523 表示 5.23%），或 "--" 表示无数据
    """
    if val is None or val == "--":
        return "--"
    try:
        return float(val) / 100  # 转为小数供 Excel 0.00% 格式使用
    except (ValueError, TypeError):
        return "--"


def _format_rank(entry: dict) -> str:
    """格式化排名为 ``排名/总数``；带数据日期时附注期次以使其可追溯。

    为何附注日期：同类排名与百分位是上游**独立数组**且会各自滞后（实测读到过落后
    一个很早期次的 ``253`` 同类池），只报数字会让读者无法分辨「这是哪一天的排名」。
    日期与数值同源（同一数组末位的 ``x``），故不存在额外取数成本。

    Returns:
        ``"155/362"``；带日期时 ``"155/362（09-27）"``；无数据 ``"--"``。
    """
    rank = entry.get("rank", "--")
    total = entry.get("total", "--")
    if rank is None or rank == "--" or total is None or total == "--":
        return "--"
    text = f"{rank}/{total}"
    data_date = str(entry.get("data_date", "") or "")
    # 只取 M-D 附注（表格列宽有限；年份在报告「所属交易日」与净值新鲜度中已交代）
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", data_date)
    return f"{text}（{m.group(1)}-{m.group(2)}）" if m else text


def _calc_rating_comment(rating: str, perf_eval: dict | None, benchmark: str) -> str:
    """根据评级 + 超额收益数据 + 业绩基准，生成带具体描述的业绩评价文本。

    Args:
        rating: 最终评级（优秀/良好/稳定/偏差/较差）
        perf_eval: Data_performanceEvaluation 的 JSON 对象，含 categories/data
        benchmark: 业绩比较基准名称

    Returns:
        完整业绩评价字符串
    """
    base = _RATING_COMMENT.get(rating, "--")

    # 如果有超额收益评分，追加说明
    if perf_eval:
        categories = perf_eval.get("categories") or []
        scores = perf_eval.get("data") or []
        # 找到"超额收益"对应的分值
        excess_idx = next((i for i, c in enumerate(categories) if c and ("超额" in c or "超额收益" in c)), -1)
        if excess_idx >= 0 and excess_idx < len(scores):
            excess_score = scores[excess_idx]
            if isinstance(excess_score, (int, float)):
                base += f"（超额收益评分{excess_score:.0f}）"
                return base

    # 没有超额收益评分但有基准名，附加基准信息
    if benchmark and benchmark != "--":
        base += f"（基准：{benchmark}）"

    return base


def _adjust_rating_with_benchmark(peer_rating: str, perf_eval: dict | None = None) -> str:
    """用基准比较数据修正纯同类排名评级。

    修正规则：
      - 超额收益评分 ≥ 80  → 评级上调一级（如 良好→优秀）
      - 超额收益评分 < 40  → 评级下调一级（如 稳定→偏差）
      - 无超额收益数据或评分居中 → 保持原评级

    Args:
        peer_rating: 纯同类排名评级（优秀/良好/稳定/偏差/较差）
        perf_eval: Data_performanceEvaluation 对象，含"超额收益"评分

    Returns:
        修正后的最终评级
    """
    if not perf_eval or peer_rating not in _RATING_ORDER:
        return peer_rating

    categories = perf_eval.get("categories") or []
    scores = perf_eval.get("data") or []

    # 找到"超额收益"在 categories 中的索引
    excess_idx = -1
    for i, cat in enumerate(categories):
        if cat and ("超额" in cat or "超额收益" in cat):
            excess_idx = i
            break

    if excess_idx < 0 or excess_idx >= len(scores):
        return peer_rating

    excess_score = scores[excess_idx]
    if not isinstance(excess_score, (int, float)):
        return peer_rating

    current_idx = _RATING_ORDER.index(peer_rating)

    up, down = _get_excess_thresholds()

    if excess_score >= up:
        # 超额收益显著 → 上调
        new_idx = min(current_idx + 1, len(_RATING_ORDER) - 1)
    elif excess_score < down:
        # 超额收益较差 → 下调
        new_idx = max(current_idx - 1, 0)
    else:
        # 中间区间 → 不调整
        return peer_rating

    adjusted = _RATING_ORDER[new_idx]
    if adjusted != peer_rating:
        logger.debug("评级调整: %s → %s（超额收益评分 %.0f）", peer_rating, adjusted, excess_score)
    return adjusted
