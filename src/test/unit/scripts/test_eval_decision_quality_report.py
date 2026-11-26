"""`scripts/_eval_decision_quality/report.py` 摘要渲染与控制台输出面测试。

既有 `test_eval_decision_quality.py` 覆盖各阶段的判定函数与两类阶段的 Markdown；
本文件补全部阶段（视界/因子 IC/纪律/相关性/估值）的判定表渲染、控制台摘要分支与
产物落盘（JSON + Markdown，含写入失败中止）。

全部用例用内存构造的阶段结果，不读真实账本与行情。
"""

from __future__ import annotations

import json

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

# 内部实现包按 `_eval_decision_quality.*` 绝对名导入，经入口脚本加载以完成 sys.path 自助修补
mod = load_script("eval-decision-quality.py", module_name="eval_decision_quality_report_under_test")
report = mod


def _horizon_result() -> dict:
    return {
        "phase": "horizon",
        "horizons": {
            str(h): {
                "n_matured": 10,
                "n_decisions": 12,
                "hit_rate": 0.6,
                "mean_raw_return": 0.01,
                "mean_excess": 0.005,
                "verdict": "有区分度",
            }
            for h in report.HORIZONS
        },
        "caveats": ["样本期短，结论不得外推"],
    }


def _factor_result() -> dict:
    return {
        "phase": "factor-ic",
        "n_signals": 42,
        "date_range": ["2026-01-05", "2026-03-20"],
        "rows": [
            {
                "factor": "momentum",
                "horizon": 20,
                "n": 30,
                "ic": 0.12,
                "tercile_monotonic": True,
                "verdict": "通过",
                "passed": True,
            },
            {
                "factor": "value",
                "horizon": 20,
                "n": 28,
                "ic": 0.01,
                "tercile_monotonic": False,
                "verdict": "无区分度",
                "passed": False,
            },
        ],
        "caveats": [],
    }


def _discipline_result() -> dict:
    return {
        "phase": "discipline",
        "n_decisions": 5,
        "summary": {
            "n_samples": 4,
            "fixed": {"n": 1, "hit_rate": 0.25, "mean_effect_return": -0.01},
            "normalized": {"n": 3, "hit_rate": 0.75, "mean_effect_return": 0.02},
            "verdict": "归一化线更优",
            "edge": 0.03,
        },
        "params": {
            "fixed_stop_pct": 0.08,
            "vol_multiple": 2.0,
            "vol_window": 20,
            "min_edge": 0.05,
            "min_samples": 3,
        },
        "caveats": ["未计入交易成本"],
    }


def _correlation_result() -> dict:
    return {
        "phase": "correlation",
        "n_codes": 30,
        "summary": {"span_days": 120, "n_windows": 10, "ic": 0.21, "tercile_monotonic": True, "verdict": "通过"},
        "params": {"window": 20, "step": 5},
        "caveats": [],
    }


def _valuation_result() -> dict:
    return {
        "phase": "valuation",
        "n_signals": 8,
        "real_unavailable_reasons": {"缺 PE 历史": 3},
        "summary": {
            str(h): {
                "proxy": {"n": 8, "ic": 0.1, "tercile_monotonic": True, "verdict": "通过"},
                "real": {"n": 2, "ic": 0.05, "tercile_monotonic": False, "verdict": "样本不足"},
            }
            for h in report.HORIZONS
        },
        "caveats": ["真实口径样本不足"],
    }


class TestRenderMarkdown:
    def test_horizon_table_lists_every_horizon(self):
        markdown = report.render_markdown(_horizon_result())
        assert "# 回测摘要 — horizon" in markdown
        for horizon in report.HORIZONS:
            assert f"| {horizon} 日 | 10/12 | 0.6 | 0.01 | 0.005 | 有区分度 |" in markdown
        assert "## 已知陷阱（结论不得外推）" in markdown
        assert "- 样本期短，结论不得外推" in markdown

    def test_factor_ic_rows_and_monotonic_flags(self):
        markdown = report.render_markdown(_factor_result())
        assert "信号条数：42；日期范围：2026-01-05 ~ 2026-03-20" in markdown
        assert "| momentum | 20 | 30 | 0.12 | 是 | 通过 |" in markdown
        assert "| value | 20 | 28 | 0.01 | 否 | 无区分度 |" in markdown

    def test_discipline_compares_two_lines(self):
        markdown = report.render_markdown(_discipline_result())
        assert "固定线 8% vs 归一化线 −2.0σ（窗口 20 日）" in markdown
        assert "| 固定线 | 1 | 0.25 | -0.01 |" in markdown
        assert "| 归一化线 | 3 | 0.75 | 0.02 |" in markdown
        assert "预注册门槛 ±5%、样本 ≥3" in markdown

    def test_correlation_single_row(self):
        markdown = report.render_markdown(_correlation_result())
        assert "品种 30 个；样本期 120 交易日；窗口 20 日 / 步长 5 日" in markdown
        assert "| 10 | 0.21 | 是 | 正（相关性↑→回撤↑） | 通过 |" in markdown

    def test_valuation_lists_proxy_and_real_calibers(self):
        markdown = report.render_markdown(_valuation_result())
        assert "真实口径不可得原因分布：{'缺 PE 历史': 3}" in markdown
        assert "| 价格代理 |" in markdown and "| 真实PE·PB |" in markdown
        assert markdown.count("真实PE·PB") == len(report.HORIZONS)

    def test_empty_caveats_renders_section_without_items(self):
        markdown = report.render_markdown(_factor_result())
        assert "## 已知陷阱（结论不得外推）" in markdown
        assert "- " not in markdown.split("## 已知陷阱", 1)[1]


class TestPrintPhaseSummary:
    """控制台摘要：每阶段一行口径，UI 前缀 `[..]` 由入口统一打印。"""

    def test_horizon_lines(self, capsys):
        report._print_phase_summary(_horizon_result())
        out = capsys.readouterr().out
        assert out.count("日视界: 成熟 10/12 命中率 0.6") == len(report.HORIZONS)

    def test_factor_ic_counts_passed_rows(self, capsys):
        report._print_phase_summary(_factor_result())
        out = capsys.readouterr().out
        assert "因子数 2" in out
        assert "有区分度判定 1 条" in out

    def test_correlation_and_discipline_lines(self, capsys):
        report._print_phase_summary(_correlation_result())
        assert "IC=0.21 → 通过" in capsys.readouterr().out
        report._print_phase_summary(_discipline_result())
        out = capsys.readouterr().out
        assert "固定线触发 1 / 归一化线触发 3 → 归一化线更优" in out

    def test_valuation_lines_per_horizon(self, capsys):
        report._print_phase_summary(_valuation_result())
        out = capsys.readouterr().out
        assert "代理 n=8 IC=0.1 → 通过 | 真实 n=2 IC=0.05 → 样本不足" in out


class TestWriteOutputs:
    def test_writes_json_and_markdown_side_by_side(self, tmp_path):
        result = _horizon_result()
        paths = report.write_outputs(result, tmp_path / "out")
        assert [path.name for path in paths] == ["horizon.json", "horizon.md"]
        assert json.loads(paths[0].read_text(encoding="utf-8")) == result
        assert paths[1].read_text(encoding="utf-8").startswith("# 回测摘要 — horizon")

    def test_unwritable_directory_aborts_with_hint(self, tmp_path, monkeypatch):
        blocker = tmp_path / "blocked"
        blocker.write_text("occupied", encoding="utf-8")
        # 目录位置被同名文件占住：mkdir 会抛 FileExistsError（OSError 子类）
        with pytest.raises((SystemExit, OSError)):
            report.write_outputs(_horizon_result(), blocker / "out")


class TestPhaseCoverageContract:
    """每个阶段都必须有渲染分支（新增阶段漏渲染会在产物里静默丢判定表）。"""

    def test_every_renderable_phase_produces_table(self):
        builders = {
            "horizon": _horizon_result,
            "factor-ic": _factor_result,
            "discipline": _discipline_result,
            "correlation": _correlation_result,
            "valuation": _valuation_result,
        }
        for phase, build in builders.items():
            markdown = report.render_markdown(build())
            assert markdown.startswith(f"# 回测摘要 — {phase}")
            assert "|" in markdown.split("## 已知陷阱")[0], f"{phase} 阶段未渲染判定表"
