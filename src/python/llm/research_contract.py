"""LLM 复盘结论的结构化契约 —— 主张 / 证据 / 判决（解析、校验与运行作用域载体）。

定位：**纯解析与校验**（零 I/O、零取数、零 LLM 调用）。提示词侧只负责要求模型输出
一行机器可读头；本模块负责把它解析出来、按证据索引校验，并给出模块级判决。

与事实校验的分工（冲突时以数值为准）：
  - `llm.fact_checker` 判「数字与语料是否相符」；
  - 本模块判「结论引用的证据是否存在、是否越出本次分析时点、失效条件是否写明」。

开关：`config/_feature_registry.py` 的 `llm_research_contract`（默认关；关时不注入
提示词、不解析、不渲染，产物与该功能引入前逐字节一致）。
"""

from __future__ import annotations

from typing import Any

from src.python.llm.evidence_index import render_index_lines

#: 功能开关名（注册见 `config/_feature_registry.py`）
FEATURE_FLAG = "llm_research_contract"

#: 契约头的行内标记（与决策头 `决策头：` 并列、互不覆盖）
STRUCTURED_CLAIMS_MARKER = "主张契约："

#: 模块级判决枚举（与设计稿一致；不引入第二套）
VERDICT_READY = "ready"
VERDICT_REVISE = "revise"
VERDICT_EVIDENCE_NEEDED = "evidence_needed"
VERDICT_REJECT = "reject"

VERDICT_LABELS: dict[str, str] = {
    VERDICT_READY: "证据齐备",
    VERDICT_REVISE: "待复核",
    VERDICT_EVIDENCE_NEEDED: "证据不足",
    VERDICT_REJECT: "与证据矛盾",
}

#: 主张条数上限（宁少勿滥；超出截断并记一条校验错误）
MAX_CLAIMS = 6

#: 运行作用域载体：模块 → 契约校验结果（每轮报告开始清空）
_MODULE_CONTRACTS: dict[str, dict[str, Any]] = {}
#: 运行作用域载体：本轮注入提示词的证据索引（校验与渲染复用同一份，避免「提示词里没有、
#: 校验却放行」的错配）
_EVIDENCE_INDEX: dict[str, str] = {}


def is_enabled() -> bool:
    """开关生效值（关时不注入提示词、不解析、不渲染）。"""
    from src.python.config.features import is_feature_enabled

    return is_feature_enabled(FEATURE_FLAG)


def reset_contract_state() -> None:
    """清空运行作用域载体（报告边界与测试隔离调用）。"""
    _MODULE_CONTRACTS.clear()
    _EVIDENCE_INDEX.clear()


def record_evidence_index(index: dict[str, str]) -> None:
    """登记本轮注入提示词的证据索引（多次调用按并集累积）。"""
    for eid, summary in (index or {}).items():
        _EVIDENCE_INDEX.setdefault(eid, summary)


def get_evidence_index() -> dict[str, str]:
    """当前轮的证据索引（提示词构建侧写入，解析校验与渲染侧读取）。"""
    return dict(_EVIDENCE_INDEX)


def record_module_contract(module_key: str, payload: dict[str, Any] | None) -> None:
    """记录某模块的契约校验结果（None 表示无契约，不落载体）。"""
    if payload:
        _MODULE_CONTRACTS[module_key] = payload


def get_module_contracts() -> dict[str, dict[str, Any]]:
    """当前轮各模块的契约校验结果（渲染层零参 pull）。"""
    return dict(_MODULE_CONTRACTS)


def build_instruction(index: dict[str, str]) -> str:
    """提示词追加段：契约头格式 + 证据索引（索引为空时只给格式，不给空清单）。

    Args:
        index: `evidence_index.build_evidence_index()` 的产物。

    Returns:
        追加到提示词末尾的文本块；关闭开关时调用方不应调用本函数。
    """
    lines = [
        "\n【结构化主张】",
        "在回复正文之后追加一行机器可读 JSON（仅一行，无需代码块）：",
        f'{STRUCTURED_CLAIMS_MARKER}{{"claims":[{{"id":"c1","statement":"…","evidence":["ev:hold:600900"],'
        '"inference":true,"invalidations":["…"]}],"verdict":"ready"}}',
        f"规则：每条主张至少引用 1 个 evidence id 且只能取自下方索引；推断性结论 inference=true；"
        f"invalidations 写清「什么情况推翻这条」；宁少勿滥（2~{MAX_CLAIMS} 条）。",
        "verdict 仅可取值 ready / revise / evidence_needed / reject。",
    ]
    if index:
        lines.append("【证据索引】")
        lines.extend(render_index_lines(index))
    return "\n".join(lines)


def parse_contract(text: str | None) -> dict[str, Any] | None:
    """从回复正文中解析契约头（JSON 一行）。

    复用决策头的括号配对扫描（引号内的花括号不计深度），不另写解析器。

    Args:
        text: 模块回复正文（含 markdown）。

    Returns:
        解析出的 dict；无标记、JSON 非法或缺 `claims` 时返回 None。
    """
    import json

    from src.python.core.decision_header import _match_json_end

    if not text or STRUCTURED_CLAIMS_MARKER not in text:
        return None
    tail = text.split(STRUCTURED_CLAIMS_MARKER, 1)[1]
    line = (tail.splitlines() or [""])[0]
    start = line.find("{")
    if start < 0:
        return None
    end = _match_json_end(line, start, len(line))
    if end is None:
        return None
    try:
        payload = json.loads(line[start:end])
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("claims"), list):
        return None
    return payload


def validate_contract(
    payload: dict[str, Any] | None,
    index: dict[str, str],
    *,
    as_of: str | None = None,
) -> dict[str, Any] | None:
    """校验契约头并给出模块级判决。

    Args:
        payload: `parse_contract()` 的结果；None 表示模型未给契约。
        index: 证据索引（`{evidence_id: 摘要}`）。
        as_of: 本次报告的数据口径日（`YYYY-MM-DD`）；保留参数用于「证据时点」扩展，
            当前索引项均来自本次装配，天然不越界，故仅记录不阻断。

    Returns:
        {claims:[{id,statement,evidence,inference,invalidations}], errors:[...],
        verdict, verdict_label, as_of}；payload 为 None 时返回 None。
    """
    if payload is None:
        return None
    allowed = set(index)
    errors: list[str] = []
    claims: list[dict[str, Any]] = []
    raw_claims = payload.get("claims") or []
    if len(raw_claims) > MAX_CLAIMS:
        errors.append(f"claims_truncated:{len(raw_claims)}")
    for raw in raw_claims[:MAX_CLAIMS]:
        if not isinstance(raw, dict):
            errors.append("claim_not_object")
            continue
        cid = str(raw.get("id") or f"c{len(claims) + 1}")
        statement = str(raw.get("statement") or "").strip()
        evidence = [str(e) for e in (raw.get("evidence") or []) if isinstance(e, str) and e]
        invalidations = [str(v) for v in (raw.get("invalidations") or []) if isinstance(v, str) and v]
        inference = bool(raw.get("inference", True))
        if not statement:
            errors.append(f"statement_missing:{cid}")
            continue
        if not evidence:
            errors.append(f"evidence_missing:{cid}")
        unknown = [e for e in evidence if e not in allowed]
        if unknown:
            errors.append(f"evidence_unknown:{cid}:{'/'.join(unknown[:3])}")
        if not invalidations:
            errors.append(f"invalidations_missing:{cid}")
        claims.append(
            {
                "id": cid,
                "statement": statement,
                "evidence": evidence,
                "inference": inference,
                "invalidations": invalidations,
            }
        )

    declared = str(payload.get("verdict") or "").strip()
    verdict = _derive_verdict(errors, declared)
    return {
        "claims": claims,
        "errors": errors,
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS.get(verdict, verdict),
        "declared_verdict": declared,
        "as_of": as_of or "",
    }


def strip_contract_line(text: str | None) -> str | None:
    """去掉正文里的契约头那一行（展示用；缓存里仍保留原文，便于下次解析）。"""
    if not text or STRUCTURED_CLAIMS_MARKER not in text:
        return text
    kept = [line for line in text.splitlines() if STRUCTURED_CLAIMS_MARKER not in line]
    return "\n".join(kept)


def _derive_verdict(errors: list[str], declared: str) -> str:
    """按校验错误推模块级判决（模型的 declared 只作参考，不能自证 ready）。"""
    if any(err.startswith(("evidence_unknown", "claim_not_object")) for err in errors):
        return VERDICT_REVISE
    if any(err.startswith("evidence_missing") for err in errors):
        return VERDICT_EVIDENCE_NEEDED
    if not errors and declared in VERDICT_LABELS:
        return declared
    if errors:
        return VERDICT_REVISE
    return VERDICT_READY


__all__ = [
    "FEATURE_FLAG",
    "STRUCTURED_CLAIMS_MARKER",
    "VERDICT_EVIDENCE_NEEDED",
    "VERDICT_LABELS",
    "VERDICT_READY",
    "VERDICT_REJECT",
    "VERDICT_REVISE",
    "build_instruction",
    "get_module_contracts",
    "is_enabled",
    "parse_contract",
    "strip_contract_line",
    "record_evidence_index",
    "record_module_contract",
    "get_evidence_index",
    "reset_contract_state",
    "validate_contract",
]
