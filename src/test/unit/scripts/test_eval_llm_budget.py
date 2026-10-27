"""`scripts/_eval_llm_budget/` 单测：预算文案、度量解析、样本构建、汇总判定与 CLI 干跑。

全部离线：不发起任何 LLM 调用或网络请求（CLI 只用 ``--dry-run`` 与 ``freeze``）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts._eval_llm_budget import budget, measure, report, sample
from scripts._eval_llm_budget.cli import main

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


class TestBudgetText:
    """预算分节与文案：比例之和必须为 1.0，文案含关键约束。"""

    def test_section_caps_sum_to_total(self):
        caps = budget.section_caps(4000)
        total = sum(cap for _, cap, _ in caps)
        assert all(cap > 0 for _, cap, _ in caps)
        assert abs(total - 4000) <= len(caps)  # 逐块取整允许每块 <1 字的偏差
        assert max(cap for _, cap, _ in caps) <= 4000

    def test_ratio_sum_guard(self, monkeypatch):
        broken = (*budget.SECTION_CAPS[:-1], budget.SECTION_CAPS[-1].__class__("尾块", 0.5, "x"))
        monkeypatch.setattr(budget, "SECTION_CAPS", broken)
        with pytest.raises(ValueError, match="比例之和"):
            budget.section_caps(4000)

    def test_standard_block_mentions_caps_and_ban(self):
        text = budget.build_budget_block(4800)
        assert "4800" in text
        for cap in budget.SECTION_CAPS:
            assert cap.name in text
        assert "禁止复述" in text
        assert "### 操作建议" in text
        assert "先压缩正文" in text
        assert "不删维度" in text

    def test_debate_block_per_role(self):
        pro = budget.build_debate_budget_block("pro")
        assert str(budget.DEBATE_SINGLE_CAPS["pro"]) in pro
        assert "论据完整" in pro
        with pytest.raises(ValueError, match="未知辩论角色"):
            budget.build_debate_budget_block("nope")


class TestMeasure:
    """度量解析：分段字数、要素机检、操作建议表。"""

    SAMPLE = """## Phase 1 召集令
核心矛盾是集中度偏高。专家甲（保守派）立场。

## Phase 2 圆桌会
专家甲反驳专家乙：600900 收益率 +5.00% 支撑结论。
### 操作建议
| 优先级 | 品种 | 建议操作 | 理由 |
|:--:|---|---|---|
| 高 | 600900 长江电力 | 减仓 | 集中度超限 |

## Phase 3 定音锤
调仓方案：降低 600900 权重；风险提示：回撤；置信度：中。
"""

    def test_sections_split(self):
        counts = measure.section_char_counts(self.SAMPLE)
        assert set(counts) == {"phase1", "phase2", "phase3", "actions"}
        assert all(value > 0 for value in counts.values())

    def test_sections_absent_not_filled(self):
        counts = measure.section_char_counts("Phase 1 召集令\n只有一段")
        assert "scenario" not in counts

    def test_elements_complete(self):
        result = measure.check_elements(self.SAMPLE)
        assert result["complete"], result["missing"]

    def test_elements_report_missing(self):
        result = measure.check_elements("无结构的纯文本")
        assert not result["complete"]
        assert "定音锤" in result["missing"]

    def test_action_rows_and_codes(self):
        result = measure.count_action_rows(self.SAMPLE)
        assert result["has_table"] is True
        assert result["rows"] == 1
        assert result["codes"] == ["600900"]

    def test_action_rows_without_table(self):
        result = measure.count_action_rows("没有建议表")
        assert result == {"rows": 0, "codes": [], "has_table": False}

    def test_action_rows_loose_heading(self):
        """标题容错：`**操作建议**`（无 ### 前缀）也要能定位表格。"""
        text = "**操作建议**\n| 优先级 | 品种 | 建议操作 | 理由 |\n|---|---|---|---|\n| 高 | 600900 | 减仓 | 超限 |"
        result = measure.count_action_rows(text)
        assert result["rows"] == 1 and result["codes"] == ["600900"]

    def test_action_rows_html_table(self):
        """HTML `<tr>` 表格（生产 seam 可能的输入形态）同样可解析。"""
        text = "<h3>操作建议</h3><table><tr><th>优先级</th><th>品种</th><th>操作</th><th>理由</th></tr>\n<tr><td>高</td><td>601398 工商银行</td><td>减仓</td><td>集中度</td></tr></table>"
        result = measure.count_action_rows(text)
        assert result["rows"] == 1 and result["codes"] == ["601398"]


class TestSample:
    """冻结样本：从快照映射、校验缺失键与空持仓。"""

    def _snapshot(self, tmp_path: Path) -> Path:
        payload = {
            "timestamp": "2026-10-26T21:40:32",
            "accounts": [
                {
                    "account_name": "全部",
                    "holdings": [
                        {
                            "code": "600900",
                            "name": "长江电力",
                            "shares": 900,
                            "market_value": 26874,
                            "total_pnl": 10599.3,
                            "cost_total": 16274.7,
                        },
                        {
                            "code": "011506",
                            "name": "建信高端装备股票A",
                            "shares": 21500,
                            "market_value": 29949.5,
                            "total_pnl": 1000,
                            "cost_total": 28949.5,
                        },
                        {
                            "code": "561910",
                            "name": "招商中证电池主题ETF",
                            "shares": 35000,
                            "market_value": 20300,
                            "total_pnl": -11025,
                            "cost_total": 31325,
                        },
                    ],
                }
            ],
        }
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_build_from_snapshot(self, tmp_path):
        built = sample.build_sample_from_snapshot(self._snapshot(tmp_path))
        assert built["holdings_count"] == 3
        assert built["total_mv"] == pytest.approx(26874 + 29949.5 + 20300)
        rates = [row["profit_rate"] for row in built["holdings_details"]]
        assert all(rate is not None for rate in rates)
        # 分类走 core/code_utils（不内联前缀判断）：A股 / 场内基金 / 场外基金各一
        assert built["categories"] == {"A股": 1, "场内基金": 1, "场外基金": 1}

    def test_empty_snapshot_rejected(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text(json.dumps({"accounts": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="没有可用持仓"):
            sample.build_sample_from_snapshot(path)

    def test_load_missing_keys(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"holdings_details": [{"code": "600900"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="缺少必需键"):
            sample.load_sample(path)


class TestReport:
    """汇总与判定：p50/p90、结构门禁、基线覆盖。"""

    def _record(self, duration: float, complete: bool = True, rows: int = 3, codes: int = 3) -> dict:
        return {
            "mode": "standard",
            "budget_chars": 4800,
            "duration_seconds": duration,
            "output_tokens": 5000,
            "chars": 4000,
            "elements": {"complete": complete, "missing": [] if complete else ["风险提示"]},
            "actions": {"rows": rows, "codes": ["6000" + str(i) for i in range(codes)], "has_table": True},
            "dry_run": False,
        }

    def test_summary_percentiles(self):
        rows = report.summarize([self._record(30), self._record(40), self._record(50)])
        assert rows[0]["duration_p50"] == pytest.approx(40.0)
        assert rows[0]["duration_p90"] == pytest.approx(50.0)
        assert rows[0]["elements_complete_rate"] == 1.0

    def test_verdict_fails_when_action_table_missing(self):
        """缺少操作建议表 → 结构不合格（实测模型会整段丢掉该表）。"""
        rows = report.summarize([self._record(30, rows=0, codes=0)])
        verdict = report.build_verdict(rows)
        assert not verdict["passed"]
        assert verdict["checks"]["standard@4800"]["action_table_ok"] is False

    def test_verdict_fails_on_structure(self):
        rows = report.summarize([self._record(30, complete=False)])
        verdict = report.build_verdict(rows)
        assert not verdict["passed"]

    def test_verdict_baseline_rows(self):
        rows = report.summarize([self._record(30, rows=1, codes=1)])
        verdict = report.build_verdict(rows, baseline={"action_rows": 3, "codes": 3})
        assert not verdict["passed"]

    def test_markdown_contains_sections(self):
        rows = report.summarize([self._record(30)])
        md = report.render_markdown(rows, report.build_verdict(rows), {"sample": "s.json", "holdings_count": 2})
        assert "# LLM 表达预算校准报告" in md
        assert "| 模式 |" in md
        assert "判定" in md


class TestCli:
    """CLI 干跑：不触网、不调用 LLM。"""

    def test_freeze_then_dry_run(self, tmp_path):
        snapshot = tmp_path / "snap.json"
        snapshot.write_text(
            json.dumps(
                {
                    "accounts": [
                        {
                            "holdings": [
                                {
                                    "code": "600900",
                                    "name": "长江电力",
                                    "market_value": 100,
                                    "total_pnl": 10,
                                    "cost_total": 90,
                                }
                            ]
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        out = tmp_path / "sample.json"
        assert main(["freeze", "--snapshot", str(snapshot), "--out", str(out)]) == 0
        assert out.exists()
        assert main(["run", "--sample", str(out), "--dry-run"]) == 0

    def test_unknown_mode_rejected(self, tmp_path):
        out = tmp_path / "sample.json"
        out.write_text(
            json.dumps(
                {
                    "holdings_details": [{"code": "600900", "market_value": 1, "profit": 0, "cost": 1}],
                    "total_mv": 1,
                    "total_cost": 1,
                    "total_profit": 0,
                    "holdings_count": 1,
                }
            ),
            encoding="utf-8",
        )
        assert main(["run", "--sample", str(out), "--modes", "nope", "--dry-run"]) == 2
