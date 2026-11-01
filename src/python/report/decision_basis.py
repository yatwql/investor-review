"""判断依据章内块 — 数据装配（形态 A：行动建议章内块，纯确定性，零 LLM）。

「新章装事实，LLM 章装解释」的确定性侧单一数据源：只读 `signal_ledger` /
持仓 / 配置 / `decision_ledger`，不取外部数据、不触碰任何 LLM 链路
（设计稿 `docs/plan/investment-decision-basis-design.md` §2/§3）。

契约（数据子契约，`pipeline_data` 键 `decision_basis_data`，附录 H 登记）：
  enabled     功能开关 `decision_basis` 生效值；False → 双端完全隐藏（回滚通道）
  available   数据可用性（骨架阶段恒 False，走 Data States 空态口径）
  reason      不可用原因（页面呈现「数据不可用：<原因>」）
  title       区块显示名「判断依据」（双端同源单一真值）
  summary     一句话结论（折叠组 summary；空态给缺省引导语）
  confidence / signals / risk_budget / discipline / settlement
              后续轮次逐节填充（骨架阶段为空结构，字段先立、数据后到）

演进（骨架先行，后续轮次只加不改）：信号清单与置信度 → 风险预算 →
纪律明细 → 结算摘要。任一节缺失 → 该节空态，不隐藏整块容器。
"""

from __future__ import annotations

from typing import Any

from src.python.config.features import is_feature_enabled

#: 功能开关名（登记见 config/_feature_registry.py，TUI [C] 面板可切换）
FEATURE_FLAG = "decision_basis"
#: 区块显示名（双端同源；归一化名与 section_block_registry 清单一致）
BLOCK_TITLE = "判断依据"
#: 骨架阶段空态原因（接入信号源后改写）
_UNAVAILABLE_REASON = "骨架阶段未接入数据源"


def is_decision_basis_enabled() -> bool:
    """开关 `decision_basis` 生效值（默认开——纯事实块，不增加风险）。"""
    return is_feature_enabled(FEATURE_FLAG)


def build_decision_basis_data() -> dict[str, Any]:
    """装配判断依据块数据（骨架：规范空契约；零 LLM、零取数、零参数）。

    Returns:
        数据子契约 dict（见模块 docstring）；开关关闭 → 仅 ``{"enabled": False}``。
    """
    if not is_decision_basis_enabled():
        return {"enabled": False}
    return {
        "enabled": True,
        "available": False,
        "reason": _UNAVAILABLE_REASON,
        "title": BLOCK_TITLE,
        "summary": f"{BLOCK_TITLE}：数据不可用（{_UNAVAILABLE_REASON}）",
        "confidence": {},
        "signals": [],
        "risk_budget": {},
        "discipline": {},
        "settlement": {},
    }
