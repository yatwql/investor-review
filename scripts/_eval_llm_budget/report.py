"""结果汇总与验收判定（Markdown/JSON 落盘）。

判定口径与设计文档「质量守门」一致，但只覆盖**可自动判定**的部分：

  - 结构：要素机检齐全、操作建议表存在（标准模式）；
  - 时延：标准模式各档 p50/p90 与基线对比；
  - 深度代理：建议行数、覆盖品种数不低于基线（需传 ``--baseline``）。

人工抽检与盲评不在本模块（主观项，脚本无法代替）。
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

STANDARD_P50_LIMIT = 42.0
"""标准模式 p50 墙钟上限（秒），取自设计文档验收标准。"""

STANDARD_P90_LIMIT = 50.0
"""标准模式 p90 墙钟上限（秒）。"""


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * ratio))
    return round(ordered[index], 2)


def summarize(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按「模式 × 预算」聚合：p50/p90/均值、输出 token、要素齐全率、建议行数。

    Args:
        records: ``runner.run_matrix`` 的产物（dry_run 记录会被跳过）。

    Returns:
        聚合行列表（每行一个 模式×预算 组合）。
    """
    groups: dict[tuple[str, Any], list[dict[str, Any]]] = {}
    for record in records:
        if record.get("dry_run"):
            continue
        groups.setdefault((record["mode"], record.get("budget_chars")), []).append(record)
    summary: list[dict[str, Any]] = []
    for (mode, budget), items in groups.items():
        durations = [float(item["duration_seconds"]) for item in items]
        outputs = [float(item["output_tokens"]) for item in items]
        summary.append(
            {
                "mode": mode,
                "budget_chars": budget,
                "runs": len(items),
                "duration_p50": _percentile(durations, 0.5),
                "duration_p90": _percentile(durations, 0.9),
                "duration_mean": round(statistics.mean(durations), 2),
                "output_tokens_mean": round(statistics.mean(outputs)),
                "elements_complete_rate": round(
                    sum(1 for item in items if item["elements"]["complete"]) / len(items), 2
                ),
                "action_rows_mean": round(statistics.mean(item["actions"]["rows"] for item in items), 1),
                "codes_mean": round(statistics.mean(len(item["actions"]["codes"]) for item in items), 1),
                "chars_mean": round(statistics.mean(item["chars"] for item in items)),
            }
        )
    summary.sort(key=lambda row: (row["mode"], row["budget_chars"] or 0))
    return summary


def build_verdict(
    summary: list[dict[str, Any]],
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """判定各组合是否达标。

    Args:
        summary: :func:`summarize` 的产物。
        baseline: 可选基线（含 ``duration_p50`` / ``action_rows`` / ``codes``），
            用于「不劣化」与「覆盖 ≥90%」判定。

    Returns:
        ``{"checks": {组合: {...}}, "passed": bool, "failed": [...]}``；辩论模式只
        校验结构完整（不参与时延收益判定）。
    """
    checks: dict[str, Any] = {}
    failed: list[str] = []
    for row in summary:
        key = f"{row['mode']}@{row['budget_chars'] or 'debate'}"
        item: dict[str, Any] = {"structure_ok": row["elements_complete_rate"] >= 1.0}
        if row["mode"].startswith("standard"):
            # 实测：预算约束下模型可能整段丢掉「操作建议表」——要素机检看不出来，必须单列
            item["action_table_ok"] = row["action_rows_mean"] >= 1
        if row["mode"].startswith("standard"):
            item["p50_ok"] = row["duration_p50"] <= STANDARD_P50_LIMIT
            item["p90_ok"] = row["duration_p90"] <= STANDARD_P90_LIMIT
        if baseline:
            base_rows = float(baseline.get("action_rows") or 0)
            base_codes = float(baseline.get("codes") or 0)
            item["rows_ok"] = row["action_rows_mean"] >= base_rows
            item["codes_ok"] = base_codes <= 0 or row["codes_mean"] >= base_codes * 0.9
        item["passed"] = all(value for name, value in item.items() if name != "passed")
        if not item["passed"]:
            failed.append(key)
        checks[key] = item
    return {"checks": checks, "passed": not failed, "failed": failed}


def render_markdown(summary: list[dict[str, Any]], verdict: dict[str, Any], meta: dict[str, Any]) -> str:
    """渲染 Markdown 报告（表格 + 结论）。

    Args:
        summary: 聚合行。
        verdict: :func:`build_verdict` 的结果。
        meta: 运行元信息（样本、时间、模型等）。

    Returns:
        Markdown 文本。
    """
    lines = [
        "# LLM 表达预算校准报告",
        "",
        f"- 样本：{meta.get('sample', '—')}（{meta.get('holdings_count', '—')} 只持仓）",
        f"- 运行时间：{meta.get('started_at', '—')}",
        f"- 模型：{meta.get('model', '—')}",
        "",
        "| 模式 | 预算(字) | 次数 | p50(s) | p90(s) | 输出tokens | 字数 | 要素齐全率 | 建议行数 | 覆盖品种 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in summary:
        lines.append(
            f"| {row['mode']} | {row['budget_chars'] or '单篇下限'} | {row['runs']} | "
            f"{row['duration_p50']} | {row['duration_p90']} | {row['output_tokens_mean']} | "
            f"{row['chars_mean']} | {row['elements_complete_rate']} | {row['action_rows_mean']} | {row['codes_mean']} |"
        )
    lines += ["", "## 判定", ""]
    for key, item in verdict["checks"].items():
        flags = "，".join(f"{name}={value}" for name, value in item.items() if name != "passed")
        lines.append(f"- {'✅' if item['passed'] else '❌'} **{key}**：{flags}")
    lines += [
        "",
        f"**总判定：{'通过' if verdict['passed'] else '不通过（' + '、'.join(verdict['failed']) + '）'}**",
        "",
    ]
    lines.append("> 本报告只覆盖可机检项；人工抽检与盲评结论需另行记录。")
    return "\n".join(lines) + "\n"


def write_outputs(
    out_dir: Path, records: list[dict[str, Any]], summary: list[dict[str, Any]], markdown: str
) -> dict[str, Path]:
    """落盘 JSON（原始记录 + 聚合）与 Markdown。

    Args:
        out_dir: 输出目录（默认 ``docs/tmp/llm-budget/``）。
        records: 原始测量记录。
        summary: 聚合行。
        markdown: 已渲染的报告文本。

    Returns:
        ``{"records": path, "summary": path, "report": path}``。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "records": out_dir / "records.json",
        "summary": out_dir / "summary.json",
        "report": out_dir / "report.md",
    }
    paths["records"].write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["report"].write_text(markdown, encoding="utf-8")
    return paths
