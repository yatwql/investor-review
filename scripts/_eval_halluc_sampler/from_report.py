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


def _audit_module(key: str, chunk: str, holdings: list[dict], dump_skipped: str | None) -> dict:
    """单章节的数值声称核对（重置覆盖率 → 判定 → 快照）。

    数值判定只走 `check_numerical_consistency` 这一条路径（覆盖率与 issues/改写都从它派生），
    避免「覆盖率用一套、告警用另一套」的口径漂移。
    """
    from src.python.core.registry import get_llm_module_name
    from src.python.llm.fact_checker import check_numerical_consistency, numerical_coverage, reset_numerical_coverage
    from src.python.llm.fact_checker._coverage import skipped_samples
    from src.python.llm.fact_checker._utils import _strip_html

    reset_numerical_coverage()
    issues, _checked, _passed, corrections = check_numerical_consistency(_strip_html(chunk), holdings)
    cov = numerical_coverage()
    label = get_llm_module_name(key)
    dump: list[str] = []
    if dump_skipped and dump_skipped in (key, "all"):
        for reason, items in skipped_samples().items():
            dump.append(f"### {label}（{key}）｜{reason}")
            dump.append("")
            for item in items:
                dump.append(f"- `{item['value']}%` … {item['sentence']}")
            dump.append("")
    return {
        "key": key,
        "label": label,
        "claims": cov["total"],
        "verified": cov["verified"],
        "mismatched": cov["mismatched"],
        "skipped": cov["skipped"],
        "skip_reasons": dict(cov["skip_reasons"]),
        "issues": list(issues),
        "rewrites": list(corrections),
        "dump": dump,
    }


def audit_report(report_path: str, dump_skipped: str | None = None) -> dict | None:
    """核对一份报告：章节解析 + 持仓取自报告表格 + 逐模块数值核对。

    Args:
        report_path: 报告 HTML 路径。
        dump_skipped: 导出跳过声称抽样的模块键或 ``all``（None = 不导出）。

    Returns:
        ``{path, holdings, modules, claims, verified, mismatched, skipped, issues, rewrites,
        issue_lines, skip_reasons, dump}``；报告不可读或无章节时返回 None。
    """
    from src.python.llm.fact_checker import reset_numerical_coverage

    try:
        with open(report_path, encoding="utf-8") as handle:
            page = handle.read()
    except OSError as exc:
        logger.error("[ERR] 读取报告失败: %s", exc)
        return None

    sections = _extract_sections(page)
    targets = [(key, sections.get(key, "")) for key in _MODULE_KEYS if sections.get(key)]
    if not targets:
        logger.error("[ERR] 报告里没有可核对的分析章节（%s）", ", ".join(_MODULE_KEYS))
        return None

    holdings = _extract_holdings_details(sections)
    modules = [_audit_module(key, chunk, holdings, dump_skipped) for key, chunk in targets]
    reset_numerical_coverage()

    data: dict = {"path": report_path, "holdings": holdings, "modules": modules, "dump": []}
    for name in ("claims", "verified", "mismatched", "skipped"):
        data[name] = sum(module[name] for module in modules)
    data["issues"] = sum(len(module["issues"]) for module in modules)
    data["rewrites"] = sum(len(module["rewrites"]) for module in modules)
    data["issue_lines"] = [f"[{module['label']}] {line}" for module in modules for line in module["issues"]]
    aggregate: dict[str, int] = {}
    for module in modules:
        for reason, count in module["skip_reasons"].items():
            aggregate[reason] = aggregate.get(reason, 0) + int(count)
    data["skip_reasons"] = aggregate
    data["dump"] = [line for module in modules for line in module["dump"]]
    return data


def _render(data: dict) -> str:
    """单份报告的 Markdown 渲染。"""
    total = data
    rate = (total["verified"] / total["claims"] * 100) if total["claims"] else 0.0
    lines = [
        "# 报告确定性核对（离线，零 LLM 调用）",
        "",
        f"- **源报告**: `{data['path']}`",
        f"- **持仓品种**: {len(data['holdings'])}（来自报告自身的持仓明细表）",
        f"- **总体覆盖率**: {total['verified']}/{total['claims']}（{rate:.0f}%）｜不符 {total['mismatched']}",
        "",
        "| 模块 | 百分比声称 | 已比对 | 不符 | 跳过 | 跳过原因 TOP3 |",
        "|------|-----------:|-------:|-----:|-----:|----------------|",
    ]
    for module in data["modules"]:
        module_rate = (module["verified"] / module["claims"] * 100) if module["claims"] else 0.0
        reasons = module["skip_reasons"]
        top_reasons = "；".join(f"{reason}×{count}" for reason, count in list(reasons.items())[:3]) or "—"
        lines.append(
            f"| {module['label']}（{module['key']}） | {module['claims']} | {module['verified']} "
            f"({module_rate:.0f}%) | {module['mismatched']} | {module['skipped']} | {top_reasons} |"
        )
    if data["skip_reasons"]:
        lines += ["", "## 跳过原因分布（全部模块合计）", "", "| 跳过原因 | 条数 |", "|----------|-----:|"]
        for reason, count in sorted(data["skip_reasons"].items(), key=lambda kv: -kv[1]):
            lines.append(f"| {reason} | {count} |")
    if data["dump"]:
        lines += ["", "## 跳过声称抽样（人工判定：真非收益 / 漏关键词 / 漏归因）", ""] + data["dump"]
    if data["issue_lines"]:
        lines += ["", "## 告警明细（确定性核对）", ""] + [f"- {line}" for line in data["issue_lines"]]
    return "\n".join(lines).rstrip() + "\n"


def run_from_report(
    report_path: str,
    output_path: str | None = None,
    dump_skipped: str | None = None,
) -> int:
    """对既有报告跑确定性核对，写 Markdown 报告并打印汇总。

    Args:
        report_path: 报告 HTML 路径。
        output_path: 核对结果 Markdown 落点（None 时打印到 stdout）。
        dump_skipped: 导出「被跳过的声称」抽样（模块键或 ``all``），供人工判定
            是「真非收益」还是「漏了关键词/归因」——改规则前先用它看证据。

    Returns:
        0 正常（即使有告警——告警不是脚本失败）；2 报告不可读或找不到可核对章节。
    """
    data = audit_report(report_path, dump_skipped=dump_skipped)
    if data is None:
        return 2

    logger.info("源报告: %s", report_path)
    logger.info("解析到持仓品种: %d｜可核对章节: %d", len(data["holdings"]), len(data["modules"]))
    for module in data["modules"]:
        rate = (module["verified"] / module["claims"] * 100) if module["claims"] else 0.0
        logger.info(
            "[%s] 声称 %d｜已比对 %d（%.0f%%）｜不符 %d｜跳过 %d",
            module["label"],
            module["claims"],
            module["verified"],
            rate,
            module["mismatched"],
            module["skipped"],
        )

    text = _render(data)
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
    rate = (data["verified"] / data["claims"] * 100) if data["claims"] else 0.0
    logger.info(
        "总体：声称 %d｜已比对 %d（%.0f%%）｜不符 %d｜跳过 %d",
        data["claims"],
        data["verified"],
        rate,
        data["mismatched"],
        data["skipped"],
    )
    return 0


__all__ = [
    "audit_report",
    "run_from_report",
]
