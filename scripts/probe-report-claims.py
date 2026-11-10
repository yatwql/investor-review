#!/usr/bin/env python3
"""报告数值声称体检 — 批量重放历史报告的确定性核对（只读，零 LLM 调用）。

用途：回答「最近这些报告里，有多少收益率声称被真正比对过、哪些与持仓真值不符」。
与 `eval-llm-hallucination.py --from-report` 同源（同一套解析与校验），区别是**批量**：
扫一个目录、按日期取最近 N 份，输出逐份与合计的覆盖率/告警/改写表。

为什么值得例行跑：单份报告看不出「告警是不是集中在同一类表述」。实测 10 份重放发现
26 条告警里 20 条是检查器自身的归因错位（仓位/净利同比/风险指标被当成持仓收益率），
据此才补出精度护栏——这类结论只能靠批量样本得出。

用法：
  python scripts/probe-report-claims.py                    # reports/ 下最近 10 份
  python scripts/probe-report-claims.py --limit 30          # 最近 30 份
  python scripts/probe-report-claims.py --since 7           # 只扫最近 7 天
  python scripts/probe-report-claims.py --output docs/tmp/claims-audit.md

退出码：
  0 — 正常完成（有告警也是 0：告警是内容线索，不是脚本失败）
  2 — 指定目录下没有可核对的分析报告
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from datetime import datetime, timedelta

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # _eval_halluc_sampler

from _eval_halluc_sampler.from_report import extract_holdings_details, extract_sections  # noqa: E402
from src.python.core.registry import get_llm_module_name  # noqa: E402
from src.python.llm.fact_checker import (  # noqa: E402
    check_numerical_consistency,
    numerical_coverage,
    reset_numerical_coverage,
)
from src.python.llm.fact_checker._utils import _strip_html  # noqa: E402

#: 参与核对的 LLM 章节（模块键 → HTML 锚点 `id="sec-<key>"`）
_MODULE_KEYS = ("global_macro", "expert_review", "health_check", "penetration_deep")


def _report_date(path: str) -> datetime | None:
    """报告路径里的日期目录（`reports/20261110/xxx.html`）→ datetime；解析失败返回 None。"""
    parent = os.path.basename(os.path.dirname(path))
    try:
        return datetime.strptime(parent, "%Y%m%d")
    except ValueError:
        return None


def select_reports(root: str, *, limit: int = 10, since_days: int | None = None) -> list[str]:
    """挑出待核对的报告（按日期倒序，最多 ``limit`` 份）。

    Args:
        root: 报告根目录（其下按 `YYYYMMDD/` 分子目录）。
        limit: 最多取多少份。
        since_days: 只取最近 N 天（None = 不限）。
    """
    paths = glob.glob(os.path.join(root, "*", "个人投资分析报告-*.html"))
    dated = [(dt, path) for path in paths if (dt := _report_date(path)) is not None]
    if since_days is not None:
        cutoff = datetime.now() - timedelta(days=since_days)
        dated = [(dt, path) for dt, path in dated if dt >= cutoff]
    dated.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [path for _dt, path in dated[:limit]]


def audit_report(path: str) -> dict:
    """核对一份报告，返回 ``{path, claims, verified, issues, rewrites, issue_lines}``。"""
    try:
        with open(path, encoding="utf-8") as handle:
            page = handle.read()
    except OSError as exc:
        print(f"[!] 跳过不可读报告 {path}: {exc}", file=sys.stderr)
        return {"path": path, "claims": 0, "verified": 0, "issues": 0, "rewrites": 0, "issue_lines": []}
    sections = extract_sections(page)
    holdings = extract_holdings_details(sections)
    result: dict = {"path": path, "claims": 0, "verified": 0, "issues": 0, "rewrites": 0, "issue_lines": []}
    for key in _MODULE_KEYS:
        chunk = sections.get(key, "")
        if not chunk:
            continue
        reset_numerical_coverage()
        issues, _checked, _passed, corrections = check_numerical_consistency(_strip_html(chunk), holdings)
        coverage = numerical_coverage()
        result["claims"] += coverage["total"]
        result["verified"] += coverage["verified"]
        result["issues"] += len(issues)
        result["rewrites"] += len(corrections)
        result["issue_lines"].extend(f"[{get_llm_module_name(key)}] {line}" for line in issues)
    reset_numerical_coverage()
    return result


def _render(rows: list[dict]) -> str:
    """逐份 + 合计的 Markdown 表（附告警明细）。"""
    total = {name: sum(row[name] for row in rows) for name in ("claims", "verified", "issues", "rewrites")}
    rate = total["verified"] / total["claims"] * 100 if total["claims"] else 0.0
    lines = [
        "# 报告数值声称体检",
        "",
        f"- **生成时间**: {datetime.now():%Y-%m-%d %H:%M}",
        f"- **报告份数**: {len(rows)}",
        f"- **合计**: 声称 {total['claims']}｜已比对 {total['verified']}（{rate:.0f}%）"
        f"｜告警 {total['issues']}｜自动改写 {total['rewrites']}",
        "",
        "| 报告 | 百分比声称 | 已比对 | 告警 | 改写 |",
        "|------|-----------:|-------:|-----:|-----:|",
    ]
    for row in rows:
        day = os.path.basename(os.path.dirname(row["path"]))
        name = os.path.basename(row["path"])
        lines.append(f"| {day}/{name} | {row['claims']} | {row['verified']} | {row['issues']} | {row['rewrites']} |")
    issue_lines = [line for row in rows for line in row["issue_lines"]]
    if issue_lines:
        lines += ["", "## 告警明细（确定性核对）", ""]
        lines += [f"- {line}" for line in issue_lines]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="批量重放历史报告做确定性数值核对（只读，零 LLM 调用）")
    parser.add_argument(
        "root", nargs="?", default=os.path.join(_PROJECT_ROOT, "reports"), help="报告根目录（默认 reports/）"
    )
    parser.add_argument("--limit", type=int, default=10, help="最多核对多少份（按日期倒序，默认 10）")
    parser.add_argument("--since", type=int, default=None, metavar="DAYS", help="只核对最近 N 天的报告")
    parser.add_argument("--output", default=None, metavar="FILE", help="Markdown 结果落点（默认打印到 stdout）")
    args = parser.parse_args(argv)

    reports = select_reports(args.root, limit=max(1, args.limit), since_days=args.since)
    if not reports:
        print(f"[ERR] {args.root} 下没有可核对的分析报告", file=sys.stderr)
        return 2

    rows = [audit_report(path) for path in reports]
    text = _render(rows)
    if args.output:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            print(f"[ERR] 无法写入结果文件 {args.output}: {exc}", file=sys.stderr)
            return 2
        print(f"[OK] 体检结果已写入 {args.output}")
    else:
        print(text, end="")
    total = {name: sum(row[name] for row in rows) for name in ("claims", "verified", "issues", "rewrites")}
    rate = total["verified"] / total["claims"] * 100 if total["claims"] else 0.0
    print(
        f"[OK] {len(rows)} 份报告：声称 {total['claims']}｜已比对 {total['verified']}（{rate:.0f}%）"
        f"｜告警 {total['issues']}｜改写 {total['rewrites']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
