"""`_eval_halluc_sampler.report`（幻觉率采样报告 Markdown 渲染）单元测试。

渲染层是评测结论的**唯一出口**：幻觉率口径、建议提及与幻觉的区分、检查器明细
都必须在这一层如实呈现，否则前面的统计再准也会被读错。断言因此落在
「数字口径 + 分类归属 + 降级文案」上，而不是逐字比对整篇 Markdown。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _eval_halluc_sampler.report import _generate_report  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


def _fact_check(
    total_checks: int,
    *,
    numerical: list[str] | None = None,
    symbol: list[str] | None = None,
    rank: list[str] | None = None,
    suggestions: list[str] | None = None,
) -> dict:
    numerical = numerical or []
    symbol = symbol or []
    rank = rank or []
    suggestions = suggestions or []
    issues_total = len(numerical) + len(symbol) + len(rank)
    return {
        "total_checks": total_checks,
        "hallucination_rate": (issues_total / total_checks) if total_checks else 0.0,
        "num_checked": total_checks - 2,
        "sym_checked": 2,
        "rank_checked": 0,
        "sym_suggestion_count": len(suggestions),
        "issues": {
            "numerical": numerical,
            "symbol": symbol,
            "rank": rank,
            "symbol_suggestion": suggestions,
        },
    }


def _result(name: str, fact_check: dict, *, llm_output: str = "分析正文", description: str = "描述") -> dict:
    return {
        "dataset": {"name": name, "description": description, "holdings_details": [{"code": "600519"}]},
        "fact_check": fact_check,
        "llm_output": llm_output,
    }


def _table_rows(text: str) -> dict[str, str]:
    """两列表格行 → {指标名: 值}（按 Markdown 结构解析，避免逐字比对）。"""
    rows: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) == 2 and cells[0] and not set(cells[0]) <= set("-: "):
            rows[cells[0]] = cells[1]
    return rows


def _bullets(text: str) -> dict[str, str]:
    """报告头的「- **标签**: 值」条目 → {标签: 值}。"""
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^- \*\*(.+?)\*\*: (.+)$", line.strip())
        if match:
            found[match.group(1)] = match.group(2)
    return found


def test_aggregates_issues_across_datasets_and_flags_target_missed():
    """跨数据集汇总：三类告警相加作分子，校验项相加作分母，建议提及不计入幻觉率。"""
    results = [
        _result("数据集甲", _fact_check(10, numerical=["10% ≠ 12%"], symbol=["600000 声称持有"])),
        _result("数据集乙", _fact_check(10, suggestions=["510300 建议增持"])),
    ]

    text = _generate_report("expert_review", results)
    rows = _table_rows(text)

    assert rows["总事实校验项"] == "20"
    assert rows["❌ 疑似幻觉 — 数值一致性"] == "1"
    assert rows["❌ 疑似幻觉 — 品种存在性（声称持有）"] == "1"
    assert rows["ℹ️ 建议提及（非幻觉，不计入率）"] == "1"
    assert rows["**幻觉率**"] == "**10.00%**"  # (1+1)/20，建议提及不计入
    assert rows["**达标**"] == "**❌ 否**"
    assert _bullets(text)["Dry-Run"] == "否"


def test_target_met_uses_strict_five_percent_threshold():
    """幻觉率 < 5% 达标；恰等 5% 不达标（阈值口径只在一处定义，报告不得放宽）。"""
    under = _generate_report("health_check", [_result("甲", _fact_check(100, numerical=["一条"]))])
    at_threshold = _generate_report("health_check", [_result("甲", _fact_check(20, numerical=["一条"]))])

    assert _table_rows(under)["**幻觉率**"] == "**1.00%**"
    assert _table_rows(under)["**达标**"] == "**✅ 是**"
    assert _table_rows(at_threshold)["**幻觉率**"] == "**5.00%**"
    assert _table_rows(at_threshold)["**达标**"] == "**❌ 否**"


def test_dataset_section_lists_issues_by_category():
    """每数据集小节按类别列告警，类别标题与条目一一对应。"""
    fact_check = _fact_check(
        9,
        numerical=["收益率 -5.06% ≠ -8.5%"],
        symbol=["000001 声称持有但不在持仓"],
        rank=["第一大持仓实为 600519"],
    )

    text = _generate_report("expert_review", [_result("数据集甲", fact_check, llm_output="x" * 42)])

    assert "### 数据集 1: 数据集甲" in text
    assert "- **LLM 输出**: 42 字符" in text
    assert "**数值一致性**：" in text
    assert "- ❌ 收益率 -5.06% ≠ -8.5%" in text
    assert "**品种存在性（幻觉）**：" in text
    assert "**排名正确性**：" in text
    assert "✅ 无告警 —— 全部通过" not in text


def test_dataset_section_without_issues_states_no_alarm():
    """无告警数据集显式写「全部通过」，并给空 LLM 输出的「空」标记。"""
    text = _generate_report("global_macro", [_result("干净集", _fact_check(6), llm_output="")])

    assert "✅ 无告警 —— 全部通过" in text
    assert "- **LLM 输出**: 空" in text
    assert "#### 告警详情" not in text


def test_suggestions_are_rendered_but_excluded_from_hallucination():
    """建议提及单独成段（ℹ️），不进「告警详情」的幻觉类别里。"""
    fact_check = _fact_check(6, suggestions=["600036 建议买入（不在持仓）"])

    text = _generate_report("penetration_deep", [_result("数据集甲", fact_check)])

    assert "**品种存在性（建议提及 — 不计入幻觉率）**：" in text
    assert "- ℹ️ 600036 建议买入（不在持仓）" in text
    assert "#### 告警详情" not in text
    assert _table_rows(text)["**幻觉率**"] == "**0.00%**"


def test_dry_run_report_states_no_llm_called():
    """dry-run 报告须自带免责说明：本次未调用 LLM、也未做事实校验。"""
    text = _generate_report("expert_review", [_result("数据集甲", _fact_check(0))], dry_run=True)

    assert _bullets(text)["Dry-Run"] == "是（未调用 LLM API）"
    assert "未调用 LLM、也未做事实校验" in text


def test_empty_results_produce_zero_rate_without_datasets():
    """零数据集：幻觉率按 0.00% 展示（不除零），且不产出任何数据集小节。"""
    text = _generate_report("expert_review", [])

    assert _bullets(text)["数据集数"] == "0"
    assert _table_rows(text)["**幻觉率**"] == "**0.00%**"
    assert "## 各数据集详情" in text
    assert "### 数据集 1" not in text


def test_header_records_module_and_generation_time():
    """报告头写明 LLM 模块与北京时间戳（跨模块产物要能对上是哪次采样）。"""
    text = _generate_report("expert_review", [_result("甲", _fact_check(4))])

    assert _bullets(text)["LLM 模块"] == "expert_review"
    assert re.search(r"- \*\*生成时间\*\*: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text)
