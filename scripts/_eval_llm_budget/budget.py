"""表达预算档位与分节上界文案。

单一事实来源：评测用预算档位（字数）与「各阶段占总量比例」都在本模块声明，
`prompts` 只负责把它们拼进系统提示。正式改造时若改用同一口径，应把本模块的
``section_caps`` 结果迁到生产侧常量，避免两处数字各写一遍。

设计要点：
  - 预算以**中文字数**表达（对模型不敏感），表格类输出另行给行数上限；
  - 分节比例之和恒为 1.0，由 ``section_caps`` 断言；
  - 辩论模式是三次调用，按**单篇论据完整性**设下限（pro/con 各 1,200 字、
    综合 1,500 字/1,800 字），不把总字数摊到三篇。
"""

from __future__ import annotations

from dataclasses import dataclass

BUDGET_TIERS: dict[str, int] = {
    "6000": 6000,
    "4800": 4800,
    "4000": 4000,
    "3200": 3200,
}
"""标准模式（单次调用）的候选预算档位：档位名 → 全篇目标字数。"""

DEFAULT_TIER = "4800"


@dataclass(frozen=True)
class SectionCap:
    """一个输出块的预算占比。

    Attributes:
        name: 上屏用的块名（与系统提示中的小节标题一致）。
        ratio: 占全篇预算的比例；所有块的比例之和为 1.0。
        note: 该块的额外约束（行数/必须包含的要素）。
    """

    name: str
    ratio: float
    note: str


SECTION_CAPS: tuple[SectionCap, ...] = (
    SectionCap("Phase 1 召集令", 0.15, "每人一行立场 + 一句核心矛盾"),
    SectionCap("Phase 2 第一轮", 0.25, "主张 + 一条数据引用 + 判断，每人一图"),
    SectionCap("Phase 2 第二轮", 0.25, "只写被谁反驳 / 修正为什么，不复述第一轮"),
    SectionCap("Phase 3 定音锤", 0.30, "方案 + 优先级 + 风险 + 置信度各一段"),
    SectionCap("操作建议表", 0.05, "≤8 行，表头与列序不变"),
)
"""标准模式的分节预算（比例之和 = 1.0）。"""

DEBATE_SINGLE_CAPS: dict[str, int] = {
    "pro": 1200,
    "con": 1200,
    "synthesis": 1500,
    "synthesis_conditional": 1800,
}
"""辩论路径的单篇下限（字）：pro/con 各 1,200，综合 1,500 / 条件推理综合 1,800。"""


def section_caps(total_chars: int) -> list[tuple[str, int, str]]:
    """把全篇预算按比例拆成分节预算。

    Args:
        total_chars: 全篇目标字数。

    Returns:
        ``[(块名, 该块字数上限, 额外约束), ...]``；比例之和不为 1.0 时抛 ValueError
        （配置写错要在评测前暴露，不能静默按错比例生成）。
    """
    ratio_sum = sum(cap.ratio for cap in SECTION_CAPS)
    if abs(ratio_sum - 1.0) > 1e-9:
        raise ValueError(f"分节预算比例之和必须为 1.0，当前 {ratio_sum}")
    return [(cap.name, max(50, int(total_chars * cap.ratio)), cap.note) for cap in SECTION_CAPS]


def build_budget_block(total_chars: int) -> str:
    """标准模式的预算段（追加到系统提示尾部）。

    Args:
        total_chars: 全篇目标字数。

    Returns:
        含分节上界、去重禁令与图表行数约束的提示词片段；标题与小节名与
        ``SECTION_CAPS`` 同源，改比例只改一处。
    """
    lines = [f"\n\n【表达预算（硬约束）】全篇 ≤ {total_chars} 字，超出即视为不合格。分节上界："]
    for name, cap, note in section_caps(total_chars):
        lines.append(f"- {name}：≤ {cap} 字（{note}）")
    lines += [
        "- 禁止复述输入段落中的数值表格与持仓明细；同一结论不得换句重复表述；",
        "- 表格类输出按行数约束（操作建议表 ≤8 行），不受上面的字数口径影响；",
        "- 预算只压表达，不删维度：5 位专家、两轮辩论、量化调仓、风险提示、情景段（如有）必须齐全；",
        "- **必须输出 `### 操作建议` 表格**（表头「优先级 / 品种 / 建议操作 / 理由」不变），缺表即视为不合格；",
        "- **优先级**：篇幅不足时先压缩正文，表格与情景段最后压缩——表格整段缺失属最严重问题。",
    ]
    return "\n".join(lines)


def build_debate_budget_block(role: str) -> str:
    """辩论路径的预算段（追加到 pro / con / 综合三套系统提示尾部）。

    Args:
        role: ``pro`` / ``con`` / ``synthesis`` / ``synthesis_conditional``。

    Returns:
        该角色的单篇预算提示；未知角色抛 ValueError。
    """
    if role not in DEBATE_SINGLE_CAPS:
        raise ValueError(f"未知辩论角色：{role}")
    cap = DEBATE_SINGLE_CAPS[role]
    if role == "synthesis_conditional":
        extra = "按每个情景分别给出行动建议，情景之外不重复白/黑脸原文"
    elif role == "synthesis":
        extra = "不重复白/黑脸原文，只给收敛结论与冲突裁决"
    else:
        extra = "论据完整优先：关键判断必须附品种代码与一条数据依据"
    return (
        f"\n\n【表达预算（硬约束）】本篇 ≤ {cap} 字。{extra}；"
        "禁止复述输入段落中的数值表格与持仓明细；预算只压表达，不删分析维度。"
    )
