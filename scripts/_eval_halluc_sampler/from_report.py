"""既有报告重放（离线确定性核对）——`--from-report <html>` 的实现。

用途：不调 LLM、不花 token，对**一份已经生成好的报告**重跑确定性校验，回答两件事：

  1. 这轮有多少「收益率声称」被真正比对过（覆盖率），跳过的都因为什么；
  2. 哪些声称与持仓真值不符（`-8.5%` vs `-5.06%` 这类）。

持仓明细直接从报告自身的「持仓明细」表解析——重放的意义就是用**当时的**数据，
而不是拿今天的价格去校验昨天的正文。
"""

from __future__ import annotations

import html as html_lib
import logging
import re

logger = logging.getLogger("invest")

#: 需要核对的 LLM 章节（模块键 → HTML 锚点 `id="sec-<key>"`）
_MODULE_KEYS = ("global_macro", "expert_review", "health_check", "penetration_deep", "self_review")

_TAG_RE = re.compile(r"<[^>]+>")
_CELL_RE = re.compile(r"<t[hd][^>]*>(.*?)</t[hd]>", re.S)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)


def _text(cell: str) -> str:
    """单元格 → 纯文本（去标签、解实体、折叠空白）。"""
    return re.sub(r"\s+", " ", html_lib.unescape(_TAG_RE.sub(" ", cell))).strip()


def _number(value: str) -> float | None:
    """单元格 → 数值（去千分位/货币符号/百分号；空/占位返回 None）。"""
    cleaned = value.replace(",", "").replace("¥", "").replace("%", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_sections(page: str) -> dict[str, str]:
    """按 `id="sec-<key>"` 切出各章节正文（到下一个章节锚点为止）。"""
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'id="sec-([a-z_]+)"', page)]
    sections: dict[str, str] = {}
    for idx, (pos, key) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(page)
        sections[key] = page[pos:end]
    return sections


def _extract_holdings_details(sections: dict[str, str]) -> list[dict]:
    """从「持仓明细」表解析 ``{name, code, market_value, cost, profit, profit_rate}``。"""
    chunk = sections.get("holdings_detail", "")
    if not chunk:
        return []
    head_start = chunk.find("<table")
    if head_start < 0:
        return []
    head_end = chunk.find("</thead>", head_start)
    head_html = chunk[head_start : head_end if head_end > 0 else head_start + 2000]
    headers = [_text(c) for c in _CELL_RE.findall(head_html)]
    if "代码" not in headers:
        return []
    col = {name: headers.index(name) for name in ("名称", "代码", "市值", "成本", "盈亏", "收益率") if name in headers}

    rows: list[dict] = []
    for raw in _ROW_RE.findall(chunk[head_start:]):
        cells = [_text(c) for c in _CELL_RE.findall(raw)]
        if len(cells) <= col.get("代码", 0):
            continue
        code = cells[col["代码"]]
        if not re.fullmatch(r"\d{6}", code):
            continue
        market_value = _number(cells[col["市值"]]) if "市值" in col else None
        cost = _number(cells[col["成本"]]) if "成本" in col else None
        profit = _number(cells[col["盈亏"]]) if "盈亏" in col else None
        rate = _number(cells[col["收益率"]]) if "收益率" in col else None
        if rate is None and profit is not None and cost:
            rate = round(profit / cost * 100, 2)
        rows.append(
            {
                "name": cells[col.get("名称", 1)] if "名称" in col else "",
                "code": code,
                "market_value": market_value,
                "cost": cost,
                "profit": profit,
                "profit_rate": rate,
            }
        )
    return rows


def run_from_report(report_path: str, output_path: str | None = None) -> int:
    """对既有报告跑确定性核对，写 Markdown 报告并打印汇总。

    Returns:
        0 正常（即使有告警——告警不是脚本失败）；2 报告不可读或找不到可核对章节。
    """
    from src.python.core.registry import get_llm_module_name
    from src.python.llm.fact_checker import numerical_coverage, reset_numerical_coverage, run_fact_check

    try:
        with open(report_path, encoding="utf-8") as handle:
            page = handle.read()
    except OSError as exc:
        logger.error("[ERR] 读取报告失败: %s", exc)
        return 2

    sections = _extract_sections(page)
    targets = [(key, sections.get(key, "")) for key in _MODULE_KEYS if sections.get(key)]
    if not targets:
        logger.error("[ERR] 报告里没有可核对的分析章节（%s）", ", ".join(_MODULE_KEYS))
        return 2

    holdings = _extract_holdings_details(sections)
    logger.info("源报告: %s", report_path)
    logger.info("解析到持仓品种: %d｜可核对章节: %d", len(holdings), len(targets))

    lines = [
        "# 报告确定性核对（离线，零 LLM 调用）",
        "",
        f"- **源报告**: `{report_path}`",
        f"- **持仓品种**: {len(holdings)}（来自报告自身的持仓明细表）",
        "",
        "| 模块 | 百分比声称 | 已比对 | 不符 | 跳过 | 跳过原因 TOP3 |",
        "|------|-----------:|-------:|-----:|-----:|----------------|",
    ]
    detail: list[str] = []
    total = {"total": 0, "verified": 0, "mismatched": 0, "skipped": 0}
    aggregate: dict[str, int] = {}

    for key, chunk in targets:
        reset_numerical_coverage()
        _checked_html, summary = run_fact_check(
            chunk,
            holdings,
            module_label=get_llm_module_name(key),
            auto_correct=False,
            skip_ranking_check=True,
        )
        cov = numerical_coverage()
        for name in total:
            total[name] += int(cov.get(name, 0))
        reasons = cov.get("skip_reasons") or {}
        # TOP3 跳过原因：只报首个原因会掩盖真实分布（哪类归因缺口占大头看不出来）
        top_reasons = "；".join(f"{reason}×{count}" for reason, count in list(reasons.items())[:3]) or "—"
        rate = (cov["verified"] / cov["total"] * 100) if cov["total"] else 0.0
        lines.append(
            f"| {get_llm_module_name(key)}（{key}） | {cov['total']} | {cov['verified']} "
            f"({rate:.0f}%) | {cov['mismatched']} | {cov['skipped']} | {top_reasons} |"
        )
        for reason, count in reasons.items():
            aggregate[reason] = aggregate.get(reason, 0) + int(count)
        logger.info(
            "[%s] 声称 %d｜已比对 %d（%.0f%%）｜不符 %d｜跳过 %d",
            get_llm_module_name(key),
            cov["total"],
            cov["verified"],
            rate,
            cov["mismatched"],
            cov["skipped"],
        )
        if summary:
            detail.append(f"### {get_llm_module_name(key)}（{key}）")
            detail.append("")
            detail.append(summary.strip())
            detail.append("")

    overall = (total["verified"] / total["total"] * 100) if total["total"] else 0.0
    lines.insert(
        4, f"- **总体覆盖率**: {total['verified']}/{total['total']}（{overall:.0f}%）｜不符 {total['mismatched']}"
    )
    if aggregate:
        lines += ["", "## 跳过原因分布（全部模块合计）", "", "| 跳过原因 | 条数 |", "|----------|-----:|"]
        for reason, count in sorted(aggregate.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {reason} | {count} |")

    if detail:
        lines += ["", "## 告警明细（确定性事实校验摘要）", ""] + detail

    text = "\n".join(lines).rstrip() + "\n"
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            logger.error("[ERR] 写入核对报告失败: %s", exc)
            return 2
        logger.info("核对报告已生成: %s", output_path)
    else:
        print(text)
    logger.info(
        "总体：声称 %d｜已比对 %d（%.0f%%）｜不符 %d｜跳过 %d",
        total["total"],
        total["verified"],
        overall,
        total["mismatched"],
        total["skipped"],
    )
    reset_numerical_coverage()
    return 0
