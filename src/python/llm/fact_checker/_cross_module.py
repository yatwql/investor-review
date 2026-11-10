"""检查器 4：跨模块结论一致性（确定性，零 LLM 调用）。

为什么需要：单模块校验只回答「这段文字与持仓数据是否相符」，看不出**模块之间**
互相打架。实测（017730 嘉实全球产业升级）：全球政经局势写「亏损 8.5%」，智囊团与
持仓体检写「-5.06%」（摘要真值 -5.06%）——模型层自检不但没查出来，还把模块里的
错值当事实转述。这类冲突是纯算术可判定的，不该交给第二次 LLM 调用。

判据（保守，宁缺勿滥）：
  - 只比「同一实体 + 同一指标族」的百分比声称（收益率/亏损/盈利/浮亏/浮盈/涨跌幅）；
  - 实体取持仓代码或持仓名称（代码优先，名称命中要求同句有该实体代码或完整名称）；
  - 两个模块给出相差 > ``_TOLERANCE_PP`` 个百分点 → 记为一条冲突。

输出是给人看的冲突行（含两处原值与所属模块中文名），由编排层并入复核区块。
"""

from __future__ import annotations

import re

from ._utils import _strip_html

#: 指标族关键词：只有这些语境下的百分比才算「同一口径」，避免拿收益率比仓位或涨跌幅
_CLAIM_KEYWORDS = ("收益率", "亏损", "盈利", "浮亏", "浮盈", "涨跌幅")

#: 实体两侧的取材窗口（字符）：百分比与实体名的距离上限
_WINDOW = 48

#: 判定为冲突的最小差值（百分点）：小于它可能是不同取整精度，不算矛盾
_TOLERANCE_PP = 0.5

_PCT_RE = re.compile(r"([-+]?)\s*(\d+(?:\.\d+)?)\s*%")


def _signed_pct(match: re.Match[str]) -> float:
    value = float(match.group(2))
    return -value if match.group(1) == "-" else value


def _entity_mentions(text: str, holdings_details: list | None) -> list[tuple[str, str, int]]:
    """文本中的实体命中：``[(显示名, 名称或代码, 位置)]``（同一实体去重到首个位置）。"""
    mentions: list[tuple[str, str, int]] = []
    seen: set[str] = set()
    for item in holdings_details or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        code = str(item.get("code") or "").strip()
        if not name and not code:
            continue
        label = f"{name}({code})" if name and code else (name or code)
        needle = code or name
        pos = text.find(needle)
        if pos < 0 and name:
            pos = text.find(name)
        if pos < 0 or label in seen:
            continue
        seen.add(label)
        mentions.append((label, needle, pos))
    return mentions


def _claims_in_window(window: str) -> list[float]:
    """窗口内的百分比声称（要求含指标族关键词，百分比必须带 % 号）。

    方向由措辞补齐：中文常写「亏损 8.5%」而不带负号，此时按亏损语境取负值，
    否则同一事实在两处的符号会不一致（实测 -8.5% 判成 +8.5%，与 -5.06% 同号而漏报）。
    """
    keywords = [kw for kw in _CLAIM_KEYWORDS if kw in window]
    if not keywords:
        return []
    loss_context = any(kw in ("亏损", "浮亏") for kw in keywords) and not any(kw in ("盈利", "浮盈") for kw in keywords)
    values = [_signed_pct(m) for m in _PCT_RE.finditer(window)]
    if loss_context:
        return [-abs(value) for value in values]
    return values


def check_cross_module_claims(
    module_outputs: dict[str, str],
    holdings_details: list | None = None,
) -> list[str]:
    """跨模块收益率口径冲突（确定性）。

    Args:
        module_outputs: 模块中文名 → 该模块正文（HTML 或 Markdown）。
        holdings_details: 持仓明细（实体名单来源）。

    Returns:
        冲突描述行列表；无冲突返回空列表。
    """
    # 实体 → 模块 → 该模块声称的收益率集合
    claims: dict[str, dict[str, list[float]]] = {}
    for module_label, html in (module_outputs or {}).items():
        if not isinstance(html, str) or not html.strip():
            continue
        text = _strip_html(html)
        for label, _needle, pos in _entity_mentions(text, holdings_details):
            window = text[max(0, pos - _WINDOW) : pos + _WINDOW]
            for value in _claims_in_window(window):
                claims.setdefault(label, {}).setdefault(module_label, []).append(value)

    issues: list[str] = []
    for label, per_module in claims.items():
        flat = [(module, value) for module, values in per_module.items() for value in values]
        if len(flat) < 2:
            continue
        values = [value for _m, value in flat]
        if max(values) - min(values) <= _TOLERANCE_PP:
            continue
        detail = " / ".join(f"{module} {value:+.2f}%" for module, value in flat)
        issues.append(f"「{label}」收益率在不同模块间不一致：{detail}")
    return issues


def build_cross_module_block(issues: list[str]) -> str:
    """冲突行 → 报告用的复核区块 HTML（并入自检区块的确定性段，零 token）。"""
    if not issues:
        return ""
    # 用报告既有的 data-status 组件承载「状态 → 观感」（DESIGN.md：状态着色只由
    # data-status/组件状态类承载，不自造标记或内联颜色）。
    items = "".join(f'<div class="data-status-warn">{issue}</div>' for issue in issues)
    return (
        '<div class="data-status">'
        '<div class="data-status-title">跨模块一致性核对（确定性，无需模型调用）</div>'
        f"{items}"
        "<p>同一实体在不同分析模块被赋予不同收益率——请以持仓摘要为真值来源核对原文。</p>"
        "</div>"
    )
