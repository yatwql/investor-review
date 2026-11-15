"""建议执行态的唯一事实位：枚举 + 校验（需复核 / 不可执行不得携带可执行数量）。

为什么放在 `core/`：这条约束同时被 **analysis 层**（机械建议清单装配）与 **llm 层**
（结构化契约解析）使用。放在任一侧都会造成反向依赖（analysis 是下层，不得 import
`llm/`；llm 也不应替 analysis 定义业务约束），故收敛到零业务依赖的 core 层，
两侧都单向引用本模块。
"""

from __future__ import annotations

#: 执行态枚举（与设计稿一致；不引入第二套取值）
EXECUTION_CONDITIONAL = "conditional"
EXECUTION_BLOCKED = "blocked"
EXECUTION_NOT_APPLICABLE = "not_applicable"

_EXECUTION_STATUSES = (EXECUTION_CONDITIONAL, EXECUTION_BLOCKED, EXECUTION_NOT_APPLICABLE)

__all__ = [
    "EXECUTION_BLOCKED",
    "EXECUTION_CONDITIONAL",
    "EXECUTION_NOT_APPLICABLE",
    "validate_recommendation",
]


def validate_recommendation(
    *,
    review_required: bool = False,
    execution_status: str = EXECUTION_CONDITIONAL,
    quantity: int | None = None,
) -> list[str]:
    """建议级硬约束：需复核 / 不可执行的建议**不得带可执行数量**。

    与「集中度只标注不阻断」的口径并列：这条是**校验期拒绝**，不依赖提示词自律——
    需复核态或不可执行态一旦给出数量，读者会当成可下单的确定动作。

    Args:
        review_required: 是否需复核（证据不足 / 判决非 ready）。
        execution_status: 执行态（conditional / blocked / not_applicable）。
        quantity: 建议执行数量；None 表示未给出数量。

    Returns:
        违规项列表（空表示通过）。
    """
    errors: list[str] = []
    if execution_status not in _EXECUTION_STATUSES:
        errors.append(f"execution_status_invalid:{execution_status}")
    if quantity is not None:
        if quantity <= 0:
            errors.append("quantity_not_positive")
        if review_required:
            errors.append("quantity_forbidden_when_review_required")
        if execution_status in (EXECUTION_BLOCKED, EXECUTION_NOT_APPLICABLE):
            errors.append("quantity_forbidden_when_not_executable")
    return errors
