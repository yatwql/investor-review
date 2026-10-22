"""doc-traces 结论输出与缓存回放解析（全量与缓存两路共用，输出逐字一致）。

CLI 只做扫描编排与报告，本模块承载「退出码 + 汇总行」与「缓存结论结构校验」
两件纯逻辑。高置信度分类在 `_traces_doc.bundle` 单一声明（与分类全集同源）。
"""

from __future__ import annotations

from _traces_doc.bundle import HIGH_CATEGORIES


def _render_summary(total: int, high: int, low: int, summary: dict[str, int]) -> int:
    """结论汇总输出（全量与缓存回放两路共用，保证输出逐字一致）。"""
    print()
    if total == 0:
        print("[OK] 未发现历史变更痕迹，文档干净")
        return 0
    cat_stats = ", ".join(f"{k}={v}" for k, v in sorted(summary.items()))
    print(f"[!] 发现 {total} 处可疑痕迹（{cat_stats}）")
    if high > 0:
        print(f"    {high} 处高置信度（{'/'.join(HIGH_CATEGORIES)}），应从文档中移除")
        return 1
    print(f"[!] 仅 {low} 处 LOW 级别痕迹（需人工判断），建议复核")
    return 2


def _replay_conclusion(conclusion: dict | None) -> tuple[list[str], int, int, int, dict] | None:
    """校验缓存结论结构 → 回放元组；结构不完整 → None（全量重算）。"""
    if not isinstance(conclusion, dict):
        return None
    lines = conclusion.get("findings")
    try:
        total = int(conclusion["total"])
        high = int(conclusion["high"])
        low = int(conclusion["low"])
        cat_summary = conclusion["summary"]
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(lines, list) or not isinstance(cat_summary, dict):
        return None
    return lines, total, high, low, cat_summary


__all__ = ["HIGH_CATEGORIES", "_render_summary", "_replay_conclusion"]
