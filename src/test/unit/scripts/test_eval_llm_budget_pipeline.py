"""`scripts/_eval_llm_budget/` 编排与落盘面单测：提示词替换、单次测量、矩阵、判定与 CLU 分支。

既有 `test_eval_llm_budget.py` 覆盖预算文案/度量解析/样本；本文件补：
  - `prompts`：提示词常量临时追加与还原（含异常路径）、特性开关重绑、模式→开关映射
  - `runner`：生产生成函数的参数投影、补写链路（`call_llm` 三元组 → 二元组）、
    `run_case` 记录结构与 `do_repair`/`keep_text` 分支、`run_matrix` 组合爆炸口径
  - `repair`：缺失块判定与补写失败降级
  - `report`：聚合、判定（含基线不劣化）、Markdown 渲染、落盘
  - `cli`：样本读取/模式/档位/基线的错误退出码与 dry-run 计划

全部离线：LLM 生成与 `call_llm` 一律打桩，不发起网络请求。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts._eval_llm_budget import budget, cli, prompts, repair, report, runner

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


def _record(
    mode: str = "standard",
    *,
    budget_chars: int | None = 4800,
    duration: float = 10.0,
    complete: bool = True,
    rows: int = 3,
    codes: int = 5,
    output_tokens: int = 100,
    chars: int = 3000,
    dry_run: bool = False,
) -> dict:
    return {
        "mode": mode,
        "budget_chars": budget_chars,
        "duration_seconds": duration,
        "output_tokens": output_tokens,
        "chars": chars,
        "elements": {"complete": complete, "missing": [] if complete else ["操作建议表"]},
        "actions": {"rows": rows, "codes": [str(600000 + index) for index in range(codes)]},
        "dry_run": dry_run,
    }


def _sample() -> dict:
    return {
        "total_mv": 1_000_000.0,
        "total_cost": 900_000.0,
        "total_profit": 100_000.0,
        "total_today_profit": -2_000.0,
        "holdings_count": 3,
        "categories": {"宽基": 0.6},
        "holdings_details": [{"code": "510300"}, {"code": "600519"}],
    }


class TestPatchedPrompts:
    """提示词常量是模块级字符串：追加必须在退出后精确还原。"""

    def test_appends_and_restores_standard_prompt(self):
        import src.python.llm.generators_singletons as singletons

        original = singletons._SYSTEM_EXPERT_REVIEW
        with prompts.patched_prompts("【预算段】"):
            assert singletons._SYSTEM_EXPERT_REVIEW == original + "【预算段】"
        assert singletons._SYSTEM_EXPERT_REVIEW == original

    def test_only_supplied_debate_roles_patched(self):
        import src.python.llm.generators as generators
        import src.python.llm.prompts_core as core

        originals = {
            "pro": generators._SYSTEM_DEBATE_PRO,
            "con": generators._SYSTEM_DEBATE_CON,
            "synthesis": core._SYSTEM_DEBATE_SYNTHESIS,
        }
        with prompts.patched_prompts("", debate_suffixes={"pro": "【P】", "synthesis": "【S】"}):
            assert generators._SYSTEM_DEBATE_PRO == originals["pro"] + "【P】"
            assert core._SYSTEM_DEBATE_SYNTHESIS == originals["synthesis"] + "【S】"
            assert generators._SYSTEM_DEBATE_CON == originals["con"], "未提供的角色不该被追加"
        assert generators._SYSTEM_DEBATE_PRO == originals["pro"]
        assert core._SYSTEM_DEBATE_SYNTHESIS == originals["synthesis"]

    def test_restores_when_body_raises(self):
        import src.python.llm.generators_singletons as singletons

        original = singletons._SYSTEM_EXPERT_REVIEW
        with pytest.raises(RuntimeError, match="测量中断"):
            with prompts.patched_prompts("【预算段】"):
                raise RuntimeError("测量中断")
        assert singletons._SYSTEM_EXPERT_REVIEW == original

    def test_missing_constant_location_raises(self, monkeypatch):
        monkeypatch.setattr(prompts, "STANDARD_PROMPT_TARGET", ("src.python.llm.generators_singletons", "_NO_SUCH"))
        with pytest.raises(AttributeError, match="提示词常量位置已变"):
            prompts._resolve("src.python.llm.generators_singletons", "_NO_SUCH")


class TestPatchedFeatures:
    """两个辩论开关按模式注入：未列出的开关沿用既有判定。"""

    def test_overrides_listed_flags_and_restores(self):
        from src.python.config import features

        original = features.is_feature_enabled
        with prompts.patched_features({"llm_debate_procon": True}):
            assert features.is_feature_enabled("llm_debate_procon") is True
            assert features.is_feature_enabled("no_such_feature") == bool(original("no_such_feature"))
        assert features.is_feature_enabled is original

    def test_rebinds_modules_holding_direct_import(self, monkeypatch):
        """生产模块常 `from ... import is_feature_enabled`：只改原模块属性对它们无效。"""
        import sys

        from src.python.config import features

        module = type(sys)("_eval_budget_rebind_probe")
        module.is_feature_enabled = features.is_feature_enabled
        monkeypatch.setitem(sys.modules, "_eval_budget_rebind_probe", module)
        with prompts.patched_features({"llm_debate_conditional": True}):
            assert module.is_feature_enabled("llm_debate_conditional") is True
        assert module.is_feature_enabled is features.is_feature_enabled

    def test_mode_flag_mapping_and_unknown_mode(self):
        assert prompts.debate_flags("standard") == {"llm_debate_procon": False, "llm_debate_conditional": False}
        assert prompts.debate_flags("standard-conditional") == {
            "llm_debate_procon": False,
            "llm_debate_conditional": True,
        }
        assert prompts.debate_flags("debate") == {"llm_debate_procon": True, "llm_debate_conditional": False}
        assert prompts.debate_flags("debate-conditional") == {
            "llm_debate_procon": True,
            "llm_debate_conditional": True,
        }
        with pytest.raises(ValueError, match="未知评测模式"):
            prompts.debate_flags("hyper")


class TestGenerationCalls:
    """生产生成函数的调用投影（参数顺序错位会静默换掉指标含义）。"""

    def test_standard_call_maps_sample_fields_positionally(self, monkeypatch):
        import src.python.llm.generators_singletons as singletons

        seen: dict = {}

        def _generate(*args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs
            return "正文", False

        monkeypatch.setattr(singletons, "generate_expert_review", _generate)
        result = runner._call_standard(_sample())
        assert result == ("正文", False)
        assert seen["args"][:5] == (1_000_000.0, 900_000.0, 100_000.0, -2_000.0, 3)
        assert seen["args"][5] == {"宽基": 0.6}
        assert seen["args"][6] == [], "缺省穿透资产按空列表传"
        assert seen["kwargs"]["force"] is True
        assert seen["kwargs"]["holdings_details"] == _sample()["holdings_details"]

    def test_debate_call_maps_sample_fields_positionally(self, monkeypatch):
        import src.python.llm.generators as generators

        seen: dict = {}

        def _generate(*args, **kwargs):
            seen["args"] = args
            return ("多", "空", "合")

        monkeypatch.setattr(generators, "generate_debate_procon", _generate)
        assert runner._call_debate(_sample()) == ("多", "空", "合")
        assert seen["args"][:5] == (1_000_000.0, 900_000.0, 100_000.0, -2_000.0, 3)

    def test_repair_once_wraps_call_llm_usage_tuple(self, monkeypatch):
        """`call_llm` 返回三元组（含 provider），补写链路只吃前两项。"""
        import src.python.config as config_pkg
        import src.python.llm.api as api

        seen: dict = {}

        def _call_llm(system, user, llm_config, **kwargs):
            seen.update(system=system, user=user, llm_config=llm_config, kwargs=kwargs)
            return "| 优先级 | 品种 | 建议操作 | 理由 |", {"output_tokens": 42}, "deepseek"

        monkeypatch.setattr(config_pkg, "get_llm_config", lambda: {"provider": "deepseek"})
        monkeypatch.setattr(api, "call_llm", _call_llm)
        text, info = runner._repair_once("原报告正文", "操作建议表", ["510300", "600519"])
        assert info["repaired"] is True
        assert info["usage"] == {"output_tokens": 42}
        assert text.startswith("原报告正文")
        assert "操作建议表" in seen["user"] and "510300" in seen["user"]
        assert seen["llm_config"] == {"provider": "deepseek"}
        assert seen["kwargs"]["max_tokens"] == 1200


class TestRunCase:
    """单次测量：会话用量差、分段字数、要素机检、补写与文本摘录。"""

    @pytest.fixture(name="usage")
    def _usage(self, monkeypatch):
        import src.python.llm.session as session

        state = {"usage": {"input_tokens": 0, "output_tokens": 0, "call_count": 0}, "resets": 0}

        def _reset():
            state["resets"] = state["resets"] + 1
            state["usage"] = dict(state["usage"])

        monkeypatch.setattr(session, "reset_session_usage", _reset)
        monkeypatch.setattr(session, "get_session_usage", lambda: dict(state["usage"]))
        return state

    @pytest.fixture(name="clock")
    def _clock(self, monkeypatch):
        values = iter([0.0, 12.5, 12.5, 14.0])
        monkeypatch.setattr(runner.time, "monotonic", lambda: next(values, 14.0))

    def test_standard_record_reports_usage_and_sections(self, usage, clock, monkeypatch):
        def _call(_sample):
            usage["usage"] = {"input_tokens": 210, "output_tokens": 340, "call_count": 1}
            return (
                "### 操作建议\n\n| 优先级 | 品种 | 建议操作 | 理由 |\n|---|---|---|---|\n| 高 | 510300 | 减仓 | 估值高 |",
                False,
            )

        monkeypatch.setattr(runner, "_call_standard", _call)
        record = runner.run_case("standard", _sample(), budget_chars=4000)
        assert usage["resets"] == 1
        assert record["mode"] == "standard" and record["budget_chars"] == 4000
        assert record["duration_seconds"] == pytest.approx(12.5)
        assert record["output_tokens"] == 340 and record["call_count"] == 1
        assert record["parts"] == 1 and record["dry_run"] is False
        assert record["chars"] > 0
        assert record["repair"] == {"repaired": False}

    def test_standard_prompt_carries_budget_block(self, monkeypatch, usage, clock):
        import src.python.llm.generators_singletons as singletons

        seen: dict = {}

        def _call(_sample):
            seen["prompt"] = singletons._SYSTEM_EXPERT_REVIEW
            return ("正文", False)

        monkeypatch.setattr(runner, "_call_standard", _call)
        runner.run_case("standard", _sample(), budget_chars=4800)
        assert seen["prompt"].endswith(budget.build_budget_block(4800))

    def test_debate_record_joins_three_parts(self, usage, clock, monkeypatch):
        import src.python.llm.generators as generators

        seen: dict = {}

        def _call(_sample):
            seen["prompt"] = generators._SYSTEM_DEBATE_PRO
            return ("多头", "空头", "综合")

        monkeypatch.setattr(runner, "_call_debate", _call)
        record = runner.run_case("debate", _sample())
        assert record["parts"] == 3 and record["is_debate"] is True
        assert record["budget_chars"] is None, "辩论模式用固定单篇下限，不传字数档"
        assert seen["prompt"].endswith(budget.build_debate_budget_block("pro"))

    def test_keep_text_excerpt_truncates_middle(self, usage, clock, monkeypatch):
        long_text = "甲" * 2400 + "乙" * 600
        monkeypatch.setattr(runner, "_call_standard", lambda _s: (long_text, False))
        record = runner.run_case("standard", _sample(), budget_chars=4000, keep_text=True)
        excerpt = record["text_excerpt"]
        assert excerpt.startswith("甲" * 10) and excerpt.endswith("乙" * 10)
        assert "…" in excerpt, "长文只保留首尾摘录（尾部用于排查解析问题）"
        assert len(excerpt) == 1500 + 3 + 500

    def test_short_text_excerpt_kept_verbatim(self, usage, clock, monkeypatch):
        monkeypatch.setattr(runner, "_call_standard", lambda _s: ("短文本", False))
        record = runner.run_case("standard", _sample(), budget_chars=4000, keep_text=True)
        assert record["text_excerpt"] == "短文本"

    def test_repair_loop_appends_and_records_seconds(self, usage, clock, monkeypatch):
        monkeypatch.setattr(runner, "_call_standard", lambda _s: ("缺表的正文", False))
        monkeypatch.setattr(repair, "missing_blocks", lambda _text, mode: ["操作建议表"])
        merged: list[str] = []

        def _repair_once(text, block, codes):
            merged.append(f"{text}|{block}|{len(codes)}")
            return text + "\n\n补写表", {"repaired": True, "usage": {"output_tokens": 7}}

        monkeypatch.setattr(runner, "_repair_once", _repair_once)
        record = runner.run_case("standard", _sample(), budget_chars=4000, do_repair=True)
        assert record["repair"]["repaired"] is True
        assert "seconds" in record["repair"]
        assert merged and merged[0].endswith("|操作建议表|2"), "缺品种码时退回样本前几个持仓"
        assert record["repair"]["usage"]["output_tokens"] == 7

    def test_unknown_mode_rejected(self, usage):
        with pytest.raises(ValueError, match="未知模式"):
            runner.run_case("nope", _sample())

    def test_dry_run_returns_plan_without_calling_llm(self, monkeypatch):
        def _no_call(_sample):
            raise AssertionError("dry_run 不得调用 LLM")

        monkeypatch.setattr(runner, "_call_standard", _no_call)
        plan = runner.run_case("standard-conditional", _sample(), budget_chars=3200, dry_run=True)
        assert plan["dry_run"] is True
        assert plan["budget_chars"] == 3200
        assert plan["flags"] == prompts.debate_flags("standard-conditional")
        assert plan["is_debate"] is False


class TestRunMatrix:
    """矩阵口径：标准模式逐档 × 重复；辩论模式固定单档，避免组合爆炸。"""

    def test_matrix_shape_for_standard_and_debate(self, monkeypatch):
        calls: list[tuple] = []

        def _fake(mode, _sample, *, budget_chars=None, dry_run=False, keep_text=False, do_repair=False):
            calls.append((mode, budget_chars))
            return _record(mode, budget_chars=budget_chars, dry_run=True)

        monkeypatch.setattr(runner, "run_case", _fake)
        records = runner.run_matrix(_sample(), modes=("standard", "debate"), tiers=("6000", "4000"), repeats=2)
        assert [call for call in calls if call[0] == "standard"] == [
            ("standard", 6000),
            ("standard", 6000),
            ("standard", 4000),
            ("standard", 4000),
        ]
        assert [call for call in calls if call[0] == "debate"] == [("debate", None), ("debate", None)]
        assert [record["repeat_index"] for record in records if record["mode"] == "standard"] == [0, 1, 0, 1]


class TestRepairPrimitives:
    def test_missing_action_table_detected_in_standard(self):
        assert repair.missing_blocks("没有表格的正文", mode="standard") == ["操作建议表"]
        table = (
            "### 操作建议\n\n| 优先级 | 品种 | 建议操作 | 理由 |\n|---|---|---|---|\n| 高 | 510300 | 减仓 | 估值高 |"
        )
        assert repair.missing_blocks(table, mode="standard") == []

    def test_non_standard_mode_requires_no_table(self):
        assert repair.missing_blocks("辩论体正文", mode="debate") == []

    def test_repair_text_merges_and_reports_usage(self):
        seen: dict = {}
        text, info = repair.repair_text(
            "原文  ",
            block="操作建议表",
            codes=["510300"],
            caller=lambda system, user: seen.update(system=system, user=user) or ("表格", {"output_tokens": 12}),
        )
        assert info == {"repaired": True, "usage": {"output_tokens": 12}}
        assert text.startswith("原文\n\n表格")
        assert "操作建议表" in seen["user"] and "510300" in seen["user"]
        assert seen["system"].endswith("输出 Markdown。")

    def test_empty_codes_uses_generic_hint(self):
        seen: dict = {}
        repair.repair_text(
            "原文", block="操作建议表", codes=[], caller=lambda system, user: (seen.setdefault("user", user), None)
        )
        assert "报告中出现的品种" in seen["user"]

    def test_failed_repair_keeps_original_text(self):
        text, info = repair.repair_text(
            "原文", block="操作建议表", codes=["510300"], caller=lambda _s, _u: (None, None)
        )
        assert text == "原文" and info["repaired"] is False and info["usage"] == {}


class TestReportAndVerdict:
    def test_summarize_groups_and_skips_dry_run(self):
        summary = report.summarize(
            [
                _record(duration=10.0),
                _record(duration=20.0, complete=False),
                _record(mode="debate", budget_chars=None, duration=30.0),
                _record(dry_run=True),
            ]
        )
        assert [row["mode"] for row in summary] == ["debate", "standard"]
        standard = next(row for row in summary if row["mode"] == "standard")
        assert standard["runs"] == 2
        assert standard["duration_p50"] == pytest.approx(20.0)
        assert standard["elements_complete_rate"] == pytest.approx(0.5)
        assert standard["action_rows_mean"] == pytest.approx(3.0)

    def test_verdict_flags_slow_and_incomplete_standard(self):
        summary = report.summarize([_record(duration=60.0, complete=False, rows=0)])
        verdict = report.build_verdict(summary)
        item = verdict["checks"]["standard@4800"]
        assert item["structure_ok"] is False
        assert item["action_table_ok"] is False
        assert item["p50_ok"] is False and item["p90_ok"] is False
        assert verdict["passed"] is False and verdict["failed"] == ["standard@4800"]

    def test_debate_only_checks_structure(self):
        summary = report.summarize([_record(mode="debate", budget_chars=None, duration=90.0)])
        verdict = report.build_verdict(summary)
        item = verdict["checks"]["debate@debate"]
        assert "p50_ok" not in item, "辩论模式不参与时延收益判定"
        assert item["passed"] is True

    def test_baseline_regression_flags_rows_and_codes(self):
        summary = report.summarize([_record(rows=1, codes=2)])
        verdict = report.build_verdict(summary, {"action_rows": 3, "codes": 6})
        item = verdict["checks"]["standard@4800"]
        assert item["rows_ok"] is False
        assert item["codes_ok"] is False
        assert verdict["passed"] is False

    def test_baseline_zero_codes_skips_coverage_check(self):
        summary = report.summarize([_record(rows=9, codes=0)])
        verdict = report.build_verdict(summary, {"action_rows": 1, "codes": 0})
        assert verdict["checks"]["standard@4800"]["codes_ok"] is True
        assert verdict["passed"] is True

    def test_markdown_lists_rows_and_verdict(self):
        summary = report.summarize([_record(), _record(mode="debate", budget_chars=None, rows=0)])
        markdown = report.render_markdown(
            summary, report.build_verdict(summary), {"sample": "a.json", "holdings_count": 3}
        )
        assert "| standard | 4800 |" in markdown
        assert "| debate | 单篇下限 |" in markdown
        assert "**总判定：通过**" in markdown
        assert "本报告只覆盖可机检项" in markdown

    def test_write_outputs_creates_three_files(self, tmp_path):
        summary = report.summarize([_record()])
        verdict = report.build_verdict(summary)
        paths = report.write_outputs(
            tmp_path / "out", [_record()], summary, report.render_markdown(summary, verdict, {})
        )
        assert set(paths) == {"records", "summary", "report"}
        assert json.loads(paths["summary"].read_text(encoding="utf-8")) == summary
        assert paths["report"].read_text(encoding="utf-8").startswith("# LLM 表达预算校准报告")


def _run_args(**overrides) -> argparse.Namespace:
    base = {
        "sample": "sample.json",
        "modes": "",
        "tiers": "",
        "repeats": 1,
        "dry_run": False,
        "keep_text": False,
        "repair": False,
        "baseline": None,
        "out_dir": "out",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


class TestCliBranches:
    def test_freeze_error_reports_and_returns_one(self, monkeypatch, capsys):
        def _raise(_path):
            raise ValueError("快照缺字段")

        monkeypatch.setattr(cli, "build_sample_from_snapshot", _raise)
        assert cli._cmd_freeze(argparse.Namespace(snapshot="s.json", out="o.json")) == 1
        assert "样本构建失败：快照缺字段" in capsys.readouterr().out

    def test_run_missing_sample_returns_one(self, tmp_path, capsys):
        args = _run_args(sample=str(tmp_path / "absent.json"))
        assert cli._cmd_run(args) == 1
        assert "样本读取失败" in capsys.readouterr().out

    def test_unknown_mode_and_tier_rejected(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(cli, "load_sample", lambda _path: _sample())
        assert cli._cmd_run(_run_args(modes="standard,hyper")) == 2
        assert "未知模式" in capsys.readouterr().out
        assert cli._cmd_run(_run_args(tiers="9999")) == 2
        assert "未知档位" in capsys.readouterr().out

    def test_dry_run_reports_plan_without_records(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "load_sample", lambda _path: _sample())
        seen: dict = {}

        def _matrix(_sample, **kwargs):
            seen.update(kwargs)
            return [{"dry_run": True}, {"dry_run": True}]

        monkeypatch.setattr(cli, "run_matrix", _matrix)
        assert cli._cmd_run(_run_args(dry_run=True, modes="debate", tiers="3200", repeats=2)) == 0
        assert "计划 2 次生成" in capsys.readouterr().out
        assert seen["modes"] == ("debate",) and seen["tiers"] == ("3200",) and seen["repeats"] == 2

    def test_passing_run_writes_outputs_and_returns_zero(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(cli, "load_sample", lambda _path: _sample())
        monkeypatch.setattr(cli, "run_matrix", lambda *_a, **_k: [_record()])
        written: dict = {}

        def _write(out_dir, records, summary, markdown):
            written.update(out_dir=out_dir, records=records, summary=summary, markdown=markdown)
            return {"records": Path("r.json"), "summary": Path("s.json"), "report": Path("rep.md")}

        monkeypatch.setattr(cli, "write_outputs", _write)
        rc = cli._cmd_run(_run_args(out_dir=str(tmp_path / "out")))
        out = capsys.readouterr().out
        assert rc == 0 and "判定通过" in out
        assert written["out_dir"] == tmp_path / "out"
        assert "| standard | 4800 |" in written["markdown"]

    def test_failed_verdict_returns_three(self, monkeypatch, capsys):
        monkeypatch.setattr(cli, "load_sample", lambda _path: _sample())
        monkeypatch.setattr(cli, "run_matrix", lambda *_a, **_k: [_record(duration=120.0, complete=False, rows=0)])
        monkeypatch.setattr(
            cli,
            "write_outputs",
            lambda *_a, **_k: {"records": Path("r"), "summary": Path("s"), "report": Path("p")},
        )
        assert cli._cmd_run(_run_args()) == 3
        assert "判定不通过" in capsys.readouterr().out

    def test_unreadable_baseline_returns_two(self, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(cli, "load_sample", lambda _path: _sample())
        monkeypatch.setattr(cli, "run_matrix", lambda *_a, **_k: [_record()])
        assert cli._cmd_run(_run_args(baseline=str(tmp_path / "absent.json"))) == 2
        assert "基线读取失败" in capsys.readouterr().out
