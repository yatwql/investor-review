"""输出侧度量：分段字数、要素机检、操作建议表行数。

只做**结构性**判定（有无要素、有多少行、多长），不评价内容好坏——内容质量由
人工抽检负责。判定口径与设计文档「质量守门」章节一致：

  - 五要素：每专家立场 / 数据依据 / 结论 / 反驳对象；Phase 3 方案 / 优先级 /
    风险 / 置信度；
  - 操作建议表：行数与覆盖品种代码集合（对齐
    ``src/python/report/decision_llm_capture.py`` 的解析口径：以竖线起止的表行）。
    **刻意独立实现**（不复用生产解析器）：评测若与生产共用同一解析器，解析器的
    错误会被一起测成"通过"；此处按契约独立实现，两套结果不一致即说明其中一套
    有缺陷（并在 HTML 表格上额外兼容 ``<tr>``）。
  - 分段字数：按提示词的小节标题切分，用于校准分节预算。
"""

from __future__ import annotations

import re
from typing import Any

_PHASE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("phase1", r"Phase\s*1|召集令"),
    ("phase2", r"Phase\s*2|圆桌"),
    ("phase3", r"Phase\s*3|定音锤"),
    ("scenario", r"###\s*情景分析"),
    ("actions", r"###\s*操作建议"),
)
_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")


def _strip_html(text: str) -> str:
    """去掉 HTML 标签（真实 seam 输入是 HTML，评测也可能给纯文本）。"""
    return re.sub(r"<[^>]+>", "", text or "")


def section_char_counts(text: str) -> dict[str, int]:
    """按小节标题切分并统计各段字数。

    Args:
        text: 模型输出（HTML 或纯文本）。

    Returns:
        ``{段名: 字数}``，段名为 ``phase1/phase2/phase3/scenario/actions``；
        未出现的段不计入（不补 0，避免把「没有情景段」误判成「情景段为空」）。
    """
    plain = _strip_html(text)
    marks: list[tuple[int, str]] = []
    for name, pattern in _PHASE_PATTERNS:
        for match in re.finditer(pattern, plain):
            marks.append((match.start(), name))
    marks.sort()
    if not marks:
        return {"all": len(plain)}
    counts: dict[str, int] = {}
    for index, (start, name) in enumerate(marks):
        end = marks[index + 1][0] if index + 1 < len(marks) else len(plain)
        counts[name] = counts.get(name, 0) + len(plain[start:end].strip())
    return counts


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def check_elements(text: str) -> dict[str, Any]:
    """五要素机检（结构判定，不看观点质量）。

    Args:
        text: 模型输出。

    Returns:
        ``{"checks": {要素: bool}, "missing": [要素...], "complete": bool}``。
    """
    plain = _strip_html(text)
    checks: dict[str, bool] = {
        "召集令/立场": _has_any(plain, ("Phase 1", "召集令", "立场", "流派")),
        "数据依据": bool(_CODE_RE.search(plain)) and _has_any(plain, ("%", "占比", "收益", "市值")),
        "结论/建议": _has_any(plain, ("建议", "结论", "判断", "操作")),
        "反驳/修正": _has_any(plain, ("反驳", "修正", "反对", "不认同")),
        "定音锤": _has_any(plain, ("Phase 3", "定音锤", "调仓方案", "优先级")),
        "风险提示": _has_any(plain, ("风险", "止损", "警戒")),
        "置信度": _has_any(plain, ("置信度", "高置信", "中置信", "低置信")),
    }
    missing = [name for name, ok in checks.items() if not ok]
    return {"checks": checks, "missing": missing, "complete": not missing}


def count_action_rows(text: str) -> dict[str, Any]:
    """统计「操作建议」表的行数与覆盖品种代码集合。

    标题容错（``###`` / ``**`` / 行内出现「操作建议」均可定位）；表格容错：
    Markdown 竖线表优先，无竖线行时回退解析 HTML ``<tr>/<td>``（生产 seam 的输入
    可能是 HTML，而 ``_strip_html`` 会抹掉行结构，故原始文本与纯文本都保留）。

    Args:
        text: 模型输出（Markdown 或 HTML）。

    Returns:
        ``{"rows": int, "codes": [...], "has_table": bool}``；无该表时行数为 0、
        ``has_table=False``（是否必需由调用方按模式判断）。
    """
    raw = text or ""
    plain = _strip_html(raw)
    match = re.search(r"操作建议", plain)
    has_table = bool(match)
    rows = 0
    codes: set[str] = set()

    for stripped in (plain[match.start() :] if match else "").splitlines():
        stripped = stripped.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 3 or set("".join(cells)) <= set("-: "):
            continue
        if any(header in "".join(cells) for header in ("优先级", "建议操作", "品种")):
            continue
        rows += 1
        codes.update(_CODE_RE.findall(" ".join(cells)))

    if rows == 0 and "<tr" in raw.lower():
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.I | re.S):
            cells = [
                _strip_html(cell).strip() for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.I | re.S)
            ]
            if len(cells) < 3 or any(header in "".join(cells) for header in ("优先级", "建议操作", "品种")):
                continue
            rows += 1
            codes.update(_CODE_RE.findall(" ".join(cells)))

    return {"rows": rows, "codes": sorted(codes), "has_table": has_table}
