"""已删除 / 已改名的配置键登记表（用户配置里「旧键」的唯一对照源）。

为什么单独一张表：用户按旧文档配了键这件事，原先在三个站点各说一套——`report_section_order`
逐键告警后从内存剔除、`features.json` 的无消费者开关汇成一条告警但仍写入运行时开关表、
数据源表只写「未知，将被忽略」。用户从日志里看不出「该填什么」，维护侧也说不清
「这一版到底删了哪些键」。

本模块只负责**登记与措辞归一**：
- `RENAMED`：旧键 → 新键（沿用旧键的配置会被提示改用新键）；
- `REMOVED`：已删除的键 → 一句话说明后果（配了也不生效，为什么）。

各站点实际的处置动作（剔除 / 忽略 / 仍然写入）仍由各站点决定，本模块不改变行为；
用户手册的「旧键对照表」与站点告警文案都由这里派生，避免三处措辞各自漂移。

维护约定：删除或改名任何一个可配置键时，先在此登记一条，再改代码；只登记真实存在过
的键，不登记推测的拼写错误（那类归「未知键」）。
"""

from __future__ import annotations

from collections.abc import Iterable

#: 旧键 → 新键（沿用旧键名会被提示改用新键）
RENAMED: dict[str, str] = {}

#: 已删除的键 → 一句话说明（配了也不生效的原因/替代做法）
REMOVED: dict[str, str] = {
    "llm_usage": "LLM 用量为章内块、恒排在末位，不参与 report_section_order 排序",
}


def classify_legacy_key(name: str) -> tuple[str, str]:
    """判定一个键的旧键归属。

    Args:
        name: 键名。

    Returns:
        ``("renamed", "旧键 → 新键: x")`` / ``("removed", "已删除: 说明")`` /
        ``("unknown", "未登记（疑似拼写错误）")``。
    """
    if name in RENAMED:
        return "renamed", f"请改用 {RENAMED[name]}"
    if name in REMOVED:
        return "removed", f"已删除（{REMOVED[name]}）"
    return "unknown", "未登记（疑似拼写错误）"


def format_unknown_keys(scope: str, names: Iterable[str]) -> str:
    """把一批无效/旧键归并成**一条**告警文案（同口径、逐键给处置建议）。

    逐键打印会在每次启动刷屏（配置在模块导入时就会加载一次），故调用方收集后
    只调本函数一次；键名排序固定，日志与报告可逐字比对。

    Args:
        scope: 键所在位置（如 ``config.json report_section_order``）。
        names: 无效/旧键名集合。

    Returns:
        单行中文告警：``<scope> 含 N 项无效/旧键：a（已删除（…））、b（未登记…）``。
    """
    ordered = sorted(set(names))
    if not ordered:
        return ""
    details = "、".join(f"{name}（{classify_legacy_key(name)[1]}）" for name in ordered)
    return f"{scope} 含 {len(ordered)} 项无效/旧键：{details}"
