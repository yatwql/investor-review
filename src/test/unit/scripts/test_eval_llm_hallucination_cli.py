"""`scripts/eval-llm-hallucination.py` 薄 CLI 分支覆盖。

该脚本自身不实现采样/校验/渲染（分别在 `_eval_halluc_sampler` 包的四个模块里），
只剩「参数解析 → 数据集过滤 → 逐数据集调度 → 落盘」的编排。编排错了不会报错，
只会静默少跑数据集、把 dry-run 的提示词当正文校验、或把报告写到别处，因此这里
断言调度**行为**：数据集过滤是否传到加载器、dry-run 是否落 prompt 且不校验、
空输出是否记为 0 项校验、自检抽样是否走对分支、`--from-report` 是否直达重放。
LLM 与报告渲染全部打桩，零网络零花费。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]

_SCRIPT = "eval-llm-hallucination.py"
_LONG_OUTPUT = "涨" * 2500  # 超过 2000 字符截断阈值


def _holdings(count: int = 2) -> list[dict]:
    return [{"name": f"品种{i}", "code": f"60000{i}", "shares": 100.0, "cost": 10.0} for i in range(count)]


def _datasets(names: list[str]) -> list[dict]:
    return [{"name": name, "holdings_details": _holdings()} for name in names]


def _fact_check(
    total_checks: int,
    issues: dict[str, list[str]] | None = None,
    rate: float = 0.0,
) -> dict:
    issues = issues or {"numerical": [], "symbol": [], "rank": [], "symbol_suggestion": []}
    return {
        "issues": issues,
        "total_checks": total_checks,
        "num_checked": total_checks,
        "sym_checked": 0,
        "rank_checked": 0,
        "sym_suggestion_count": 0,
        "hallucination_rate": rate,
    }


class _Recorder:
    """记录各打桩钩子的调用实参（避免用 mock 的恒真属性做断言）。"""

    def __init__(self) -> None:
        self.load_dataset_filters: list[list[int] | None] = []
        self.llm_calls: list[dict] = []
        self.fact_checks: list[dict] = []
        self.self_review_live: list[object] = []
        self.self_review_prompt: list[object] = []
        self.reports: list[tuple[str, bool]] = []
        self.self_review_sections: list[list[dict]] = []


@pytest.fixture
def cli(monkeypatch, tmp_path):
    """加载脚本并把项目根指向 tmp_path，全部外部钩子换成记录型打桩。"""
    mod = load_script(_SCRIPT, module_name="eval_llm_hallucination_cli")
    monkeypatch.setattr(mod, "_PROJECT_ROOT", str(tmp_path))
    rec = _Recorder()

    def fake_load_datasets(dataset_filter):
        rec.load_dataset_filters.append(dataset_filter)
        names = [f"样本{i}" for i in (dataset_filter or [1, 2])]
        return _datasets(names)

    def fake_values(holdings):
        return {"total_mv": 1000.0, "total_cost": 900.0, "total_profit": 100.0, "total_today_profit": 5.0}

    def fake_call_llm(module_name, holdings, values, categories, *, dry_run, force):
        rec.llm_calls.append(
            {
                "module": module_name,
                "dry_run": dry_run,
                "force": force,
                "holdings": holdings,
                "values": values,
                "categories": categories,
            }
        )
        return (mod._LLM_REPLY if hasattr(mod, "_LLM_REPLY") else "LLM 正文", {"input_tokens": 10})

    def fake_fact_check(text, holdings, *, module_label, extra_valid_codes):
        rec.fact_checks.append({"text": text, "module_label": module_label, "extra_codes": extra_valid_codes})
        return _fact_check(4, {"numerical": ["1 → 2"], "symbol": [], "rank": [], "symbol_suggestion": []}, 0.25)

    def fake_report(module_name, all_results, *, dry_run):
        rec.reports.append((module_name, dry_run))
        return f"# 报告 {module_name} dry_run={dry_run} datasets={len(all_results)}"

    def fake_self_review_section(samples):
        rec.self_review_sections.append(samples)
        return "\n## 自检抽样\n"

    def fake_self_review_prompt(module_outputs, holdings, extra):
        rec.self_review_prompt.append(module_outputs)
        return "复核提示词"

    def fake_self_review_live(module_outputs, holdings, extra):
        rec.self_review_live.append(module_outputs)
        return "复核结论"

    monkeypatch.setattr(mod, "_load_datasets", fake_load_datasets)
    monkeypatch.setattr(mod, "_compute_portfolio_values", fake_values)
    monkeypatch.setattr(mod, "_compute_categories", lambda holdings: {"stock": len(holdings)})
    monkeypatch.setattr(mod, "_call_llm_module", fake_call_llm)
    monkeypatch.setattr(mod, "_run_fact_check", fake_fact_check)
    monkeypatch.setattr(mod, "_generate_report", fake_report)
    monkeypatch.setattr(mod, "_generate_self_review_section", fake_self_review_section)
    monkeypatch.setattr(mod, "_build_self_review_dry_run_prompt", fake_self_review_prompt)
    monkeypatch.setattr(mod, "_run_self_review_sample", fake_self_review_live)
    mod_rec = (mod, rec)
    return mod_rec


def _run(mod, monkeypatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", [_SCRIPT, *argv])
    mod.main()


class TestDatasetSelection:
    """`--dataset` 过滤必须原样传给数据集加载器（不传即等于全量）。"""

    def test_explicit_dataset_filter_is_parsed_to_ints(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        _run(mod, monkeypatch, "--dry-run", "--dataset", "1, 3", "--output", str(tmp_path / "r.md"))
        assert rec.load_dataset_filters == [[1, 3]]

    def test_absent_dataset_filter_passes_none(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        _run(mod, monkeypatch, "--dry-run", "--output", str(tmp_path / "r.md"))
        assert rec.load_dataset_filters == [None]

    def test_every_loaded_dataset_is_visited_once(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        _run(mod, monkeypatch, "--dry-run", "--dataset", "1,2,3", "--output", str(tmp_path / "r.md"))
        assert len(rec.llm_calls) == 3


class TestDryRun:
    """dry-run 只落提示词、不做事实校验（提示词当正文校验会产出无意义告警率）。"""

    def test_dry_run_writes_prompt_file_and_skips_fact_check(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        out = tmp_path / "reports" / "r.md"
        _run(mod, monkeypatch, "--dry-run", "--output", str(out))
        prompt_path = tmp_path / "docs" / "tmp" / "hallucination-prompts-expert_review.md"
        assert prompt_path.is_file()
        assert rec.fact_checks == []
        assert assert_prompt_sections(prompt_path.read_text(encoding="utf-8"))
        assert out.is_file()
        assert rec.reports == [("expert_review", True)]

    def test_dry_run_truncates_long_llm_output(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        monkeypatch.setattr(mod, "_call_llm_module", lambda *a, **k: (_LONG_OUTPUT, None))
        _run(mod, monkeypatch, "--dry-run", "--output", str(tmp_path / "r.md"))
        prompt = (tmp_path / "docs" / "tmp" / "hallucination-prompts-expert_review.md").read_text(encoding="utf-8")
        assert "（截断）" in prompt
        assert _LONG_OUTPUT not in prompt

    def test_dry_run_keeps_short_llm_output_verbatim(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        monkeypatch.setattr(mod, "_call_llm_module", lambda *a, **k: ("简短提示词", None))
        _run(mod, monkeypatch, "--dry-run", "--output", str(tmp_path / "r.md"))
        prompt = (tmp_path / "docs" / "tmp" / "hallucination-prompts-expert_review.md").read_text(encoding="utf-8")
        assert "简短提示词" in prompt
        assert "（截断）" not in prompt

    def test_dry_run_flag_reaches_llm_call(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        _run(mod, monkeypatch, "--dry-run", "--output", str(tmp_path / "r.md"))
        assert [c["dry_run"] for c in rec.llm_calls] == [True, True]


def assert_prompt_sections(prompt: str) -> bool:
    """dry-run 提示词文件同时含标题、数据集分节与代码块包裹。"""
    return "# LLM 幻觉率采样 — 构建的 Prompt（expert_review）" in prompt and "## 数据集 1" in prompt and "```" in prompt


class TestFactCheckPath:
    """非 dry-run 路径：真实调用 → 事实校验 → 汇总口径。"""

    def test_non_dry_run_checks_output_with_module_label(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        _run(mod, monkeypatch, "--output", str(tmp_path / "r.md"), "--force")
        assert [c["text"] for c in rec.fact_checks] == ["LLM 正文", "LLM 正文"]
        assert {c["module_label"] for c in rec.fact_checks} == {"智囊团深度复盘"}
        assert [c["force"] for c in rec.llm_calls] == [True, True]
        assert rec.reports == [("expert_review", False)]

    @pytest.mark.parametrize(
        ("module", "label"),
        [
            ("global_macro", "全球政经局势"),
            ("health_check", "持仓体检报告"),
            ("penetration_deep", "穿透深度分析"),
        ],
    )
    def test_module_option_selects_module_label(self, cli, monkeypatch, tmp_path, module, label):
        mod, rec = cli
        _run(mod, monkeypatch, "--module", module, "--output", str(tmp_path / "r.md"))
        assert {c["module_label"] for c in rec.fact_checks} == {label}
        assert {c["module"] for c in rec.llm_calls} == {module}

    def test_empty_llm_output_is_recorded_as_zero_checks_without_fact_check(self, cli, monkeypatch, tmp_path):
        """LLM 返回空串时跳过事实校验，但数据集仍计入报告（不能被静默丢弃）。"""
        mod, rec = cli
        monkeypatch.setattr(mod, "_call_llm_module", lambda *a, **k: (None, None))
        seen: list[dict] = []
        monkeypatch.setattr(
            mod,
            "_generate_report",
            lambda module_name, all_results, *, dry_run: seen.extend(all_results) or "# r",
        )
        _run(mod, monkeypatch, "--output", str(tmp_path / "r.md"))
        assert rec.fact_checks == []
        assert len(seen) == 2
        assert [r["fact_check"]["total_checks"] for r in seen] == [0, 0]
        assert [r["llm_output"] for r in seen] == [None, None]

    def test_report_receives_one_result_per_dataset_with_fact_check(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        seen: list[dict] = []
        monkeypatch.setattr(
            mod,
            "_generate_report",
            lambda module_name, all_results, *, dry_run: seen.extend(all_results) or "# r",
        )
        _run(mod, monkeypatch, "--dataset", "1,2", "--output", str(tmp_path / "r.md"))
        assert len(seen) == 2
        assert [r["fact_check"]["hallucination_rate"] for r in seen] == [0.25, 0.25]
        assert [r["dataset"]["name"] for r in seen] == ["样本1", "样本2"]


class TestSelfReview:
    """`--self-review` 的两条分支：dry-run 只导出复核提示词，实跑才调模型。"""

    def test_self_review_dry_run_never_calls_model(self, cli, monkeypatch, tmp_path):
        """dry-run 下 `--self-review` 不得触发模型层抽样（零花费是这一档的硬口径）。"""
        mod, rec = cli
        _run(mod, monkeypatch, "--dry-run", "--self-review", "--output", str(tmp_path / "r.md"))
        assert rec.self_review_live == []

    def test_self_review_live_sample_is_appended_to_report(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        out = tmp_path / "r.md"
        _run(mod, monkeypatch, "--self-review", "--output", str(out))
        assert len(rec.self_review_live) == 2
        assert rec.self_review_prompt == []
        assert [s["content"] for s in rec.self_review_sections[0]] == ["复核结论", "复核结论"]
        assert "## 自检抽样" in out.read_text(encoding="utf-8")

    def test_without_self_review_no_section_is_appended(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        out = tmp_path / "r.md"
        _run(mod, monkeypatch, "--output", str(out))
        assert rec.self_review_sections == []
        assert "# 报告 expert_review" in out.read_text(encoding="utf-8")


class TestFromReportAndOutput:
    """`--from-report` 直达重放（零 LLM 调用）；报告路径默认可定位。"""

    def test_from_report_delegates_and_exits_with_its_code(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        calls: list[dict] = []
        monkeypatch.setattr(
            mod,
            "run_from_report",
            lambda html, out, *, dump_skipped: calls.append({"html": html, "out": out, "dump": dump_skipped}) or 3,
        )
        with pytest.raises(SystemExit) as exc:
            _run(
                mod,
                monkeypatch,
                "--from-report",
                str(tmp_path / "report.html"),
                "--dump-skipped",
                "all",
                "--output",
                str(tmp_path / "r.md"),
            )
        assert exc.value.code == 3
        assert calls == [{"html": str(tmp_path / "report.html"), "out": str(tmp_path / "r.md"), "dump": "all"}]
        assert rec.load_dataset_filters == []
        assert rec.llm_calls == []

    def test_default_output_path_is_under_project_docs_tmp(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        _run(mod, monkeypatch, "--dry-run")
        assert (tmp_path / "docs" / "tmp" / "hallucination-report.md").is_file()
        assert rec.reports == [("expert_review", True)]

    def test_report_body_comes_from_generator(self, cli, monkeypatch, tmp_path):
        mod, rec = cli
        out = tmp_path / "r.md"
        _run(mod, monkeypatch, "--dataset", "1", "--output", str(out))
        assert out.read_text(encoding="utf-8") == "# 报告 expert_review dry_run=False datasets=1"
