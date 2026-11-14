"""LLM 结构化契约的**展示层**装配（HTML 折叠块 / Excel 行）。

数据来源是 `llm.research_contract` 的运行作用域载体（生成后一遍写入），本模块只做
「契约结果 → 展示形态」的转换，零取数、零 LLM：

- HTML：每个模块正文之后追加 `<details>` 折叠块（默认收起，句式同既有折叠块）；
- Excel：同一页签内追加「主张与证据」小节行（复用块标题/行书写习惯，不改列数）；
- 正文里那行机器可读契约头在展示前剥离（缓存里保留原文，便于下次解析）。

开关关闭时载体为空 → 两个入口都返回空（产物逐字节不变）。
"""

from __future__ import annotations

from typing import Any

from src.python.llm.research_contract import get_module_contracts, strip_contract_line

__all__ = ["contract_html", "contract_rows", "strip_contract_line"]

#: 折叠块标题（HTML）与小节标题（Excel）同源
BLOCK_TITLE = "主张与证据"


def _contract(module_key: str) -> dict[str, Any] | None:
    return get_module_contracts().get(module_key)


def contract_html(module_key: str) -> str:
    """模块正文后的折叠块 HTML（无契约 / 开关关闭时返回空串）。"""
    import html as _html

    result = _contract(module_key)
    if not result:
        return ""
    claims = result.get("claims") or []
    if not claims:
        return ""
    verdict_label = str(result.get("verdict_label") or result.get("verdict") or "")
    rows = []
    for claim in claims:
        statement = _html.escape(str(claim.get("statement") or ""))
        evidence = "、".join(_html.escape(str(e)) for e in (claim.get("evidence") or []))
        invalidations = "；".join(_html.escape(str(v)) for v in (claim.get("invalidations") or []))
        extra = []
        if evidence:
            extra.append(f"证据 {evidence}")
        if invalidations:
            extra.append(f"失效条件 {invalidations}")
        rows.append(
            f"<li>{statement}"
            + (
                '<div class="text-muted" style="font-size: var(--fs-table-sm);">' + "；".join(extra) + "</div>"
                if extra
                else ""
            )
            + "</li>"
        )
    return (
        f'<details class="contract-block"><summary>{BLOCK_TITLE}（判决：{_html.escape(verdict_label)}）</summary>'
        f"<ul>{''.join(rows)}</ul></details>"
    )


def contract_rows(module_key: str) -> list[list[str]]:
    """模块正文后的 Excel 小节行（无契约时返回空列表）。"""
    result = _contract(module_key)
    if not result:
        return []
    claims = result.get("claims") or []
    if not claims:
        return []
    verdict_label = str(result.get("verdict_label") or result.get("verdict") or "")
    rows: list[list[str]] = [[f"{BLOCK_TITLE}（判决：{verdict_label}）"]]
    for claim in claims:
        evidence = "、".join(str(e) for e in (claim.get("evidence") or []))
        invalidations = "；".join(str(v) for v in (claim.get("invalidations") or []))
        detail = "；".join(
            part
            for part in (f"证据 {evidence}" if evidence else "", f"失效条件 {invalidations}" if invalidations else "")
            if part
        )
        rows.append([f"· {claim.get('statement') or ''}", detail])
    return rows
