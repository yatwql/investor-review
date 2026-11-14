"""决策书（主张 / 证据 / 判决）—— 行动建议章内的 LLM 解读位装配。

定位：把「LLM 复盘结论的结构化契约」（`llm.research_contract` 的运行作用域载体）
装配成章内可读块，供行动建议章渲染（HTML 折叠块 + Excel 小节）。落地位置既不是
判断依据块本体（该块契约是纯确定性零 LLM），也不新增章节/页签。

开关与降级：
  - 开关 `llm_research_contract` 关闭 / 无契约载体 → 返回 None（契约键缺席，产物逐字节不变）；
  - 匿名化模式非 off → 返回 None：证据 id 内的代码脱敏不在本模块职责内，宁可不出块
    也不泄露真值（脱敏方案另行评审后再放开）。
"""

from __future__ import annotations

from typing import Any

__all__ = ["BLOCK_TITLE", "attach_decision_book", "build_decision_book"]

#: 块标题（HTML 与 Excel 同源）
BLOCK_TITLE = "决策书（主张与证据）"


#: 模块键 → 中文显示名（与 LLM 章节同源取自注册表，缺失回退键名）
def _module_label(module_key: str) -> str:
    try:
        from src.python.core.registry import get_llm_module_name

        return get_llm_module_name(module_key)
    except Exception:  # 注册表不可用时回退键名，不阻断
        return module_key


def build_decision_book() -> dict[str, Any] | None:
    """装配决策书契约（无可见内容时返回 None）。

    Returns:
        {available, title, modules: [{key, label, verdict, verdict_label, claims:
        [{statement, evidence, invalidations}]}], note}
    """
    from src.python.llm.research_contract import get_module_contracts, is_enabled

    if not is_enabled():
        return None
    try:
        from src.python.config.anonymizer import get_anonymization_mode

        if get_anonymization_mode() != "off":
            # Known Gap：证据 id 内的代码脱敏未实现 → 匿名化模式下不渲染，避免泄露真值
            return None
    except Exception:  # 配置不可读时按 off 处理（与其余报告口径一致）
        pass

    contracts = get_module_contracts()
    modules: list[dict[str, Any]] = []
    for module_key, payload in contracts.items():
        claims = []
        for claim in payload.get("claims") or []:
            claims.append(
                {
                    "statement": str(claim.get("statement") or ""),
                    "evidence": [str(e) for e in (claim.get("evidence") or [])],
                    "invalidations": [str(v) for v in (claim.get("invalidations") or [])],
                }
            )
        if not claims:
            continue
        modules.append(
            {
                "key": module_key,
                "label": _module_label(module_key),
                "verdict": str(payload.get("verdict") or ""),
                "verdict_label": str(payload.get("verdict_label") or payload.get("verdict") or ""),
                "claims": claims,
            }
        )
    if not modules:
        return None
    return {
        "available": True,
        "title": BLOCK_TITLE,
        "modules": modules,
        "note": "主张与证据来自本次 LLM 复盘；判决为机械校验结果（证据是否齐备、失效条件是否写明），不替代事实校验。",
    }


def attach_decision_book(basis: dict[str, Any] | None) -> dict[str, Any] | None:
    """把决策书补挂到判断依据块契约（幂等；渲染期调用，规避装配早于 LLM 的时序）。

    判断依据块在数据准备阶段装配，而结构化契约在 LLM 生成后一遍才落载体——
    因此在渲染入口补一次：已有 `decision_book` 则不动，否则按当前载体尝试装配。

    Args:
        basis: `decision_basis_data` 契约（可为 None）。

    Returns:
        原契约（可能新增 `decision_book` 键）；None 原样返回。
    """
    if not isinstance(basis, dict) or basis.get("decision_book"):
        return basis
    book = build_decision_book()
    if book:
        basis = {**basis, "decision_book": book}
    return basis
