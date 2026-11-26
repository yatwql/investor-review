"""`scripts/eval-llm-hallucination.py` 的落盘失败分支（边缘场景）。

四类 OSError（输出目录、prompt 目录、prompt 文件、报告文件）都必须转成带
`[ERR]` 前缀的 `SystemExit`——采样跑完之后才在写入处崩栈，会让人误以为是
LLM 侧失败。这里用「路径被文件/目录占位」制造系统级 OSError，不 mock `os`。
"""

from __future__ import annotations

import sys

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts, pytest.mark.edge]

_SCRIPT = "eval-llm-hallucination.py"

_EMPTY_FACT_CHECK = {
    "issues": {"numerical": [], "symbol": [], "rank": [], "symbol_suggestion": []},
    "total_checks": 0,
    "num_checked": 0,
    "sym_checked": 0,
    "rank_checked": 0,
    "sym_suggestion_count": 0,
    "hallucination_rate": 0.0,
}


@pytest.fixture
def cli(monkeypatch, tmp_path):
    """单数据集、单次 LLM 调用的最小桩；仅保留落盘路径为真实实现。"""
    mod = load_script(_SCRIPT, module_name="eval_llm_hallucination_cli_edge")
    monkeypatch.setattr(mod, "_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(mod, "_load_datasets", lambda dataset_filter: [{"name": "样本", "holdings_details": []}])
    monkeypatch.setattr(
        mod,
        "_compute_portfolio_values",
        lambda holdings: {"total_mv": 0.0, "total_cost": 0.0, "total_profit": 0.0, "total_today_profit": 0.0},
    )
    monkeypatch.setattr(mod, "_compute_categories", lambda holdings: {})
    monkeypatch.setattr(mod, "_call_llm_module", lambda *a, **k: ("正文", None))
    monkeypatch.setattr(mod, "_run_fact_check", lambda *a, **k: dict(_EMPTY_FACT_CHECK))
    monkeypatch.setattr(mod, "_generate_report", lambda *a, **k: "# 报告")
    return mod


def _run(cli, monkeypatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", [_SCRIPT, *argv])
    cli.main()


def test_output_dir_creation_failure_exits_with_err(cli, monkeypatch, tmp_path):
    """输出目录的上级是文件 → makedirs 抛 NotADirectoryError → SystemExit 带 ERR。"""
    blocker = tmp_path / "blocker"
    blocker.write_text("占位", encoding="utf-8")
    output = blocker / "sub" / "report.md"
    with pytest.raises(SystemExit) as exc:
        _run(cli, monkeypatch, "--output", str(output))
    assert "无法创建输出目录" in str(exc.value.code)


def test_prompt_dir_creation_failure_exits_with_err(cli, monkeypatch, tmp_path):
    """项目根被文件占位时 dry-run 的 docs/tmp 建不出来 → SystemExit 带 ERR。"""
    blocker = tmp_path / "root_is_file"
    blocker.write_text("占位", encoding="utf-8")
    monkeypatch.setattr(cli, "_PROJECT_ROOT", str(blocker))
    with pytest.raises(SystemExit) as exc:
        _run(cli, monkeypatch, "--dry-run", "--output", str(tmp_path / "report.md"))
    assert "无法创建 prompt 目录" in str(exc.value.code)


def test_prompt_write_failure_exits_with_err(cli, monkeypatch, tmp_path):
    """prompt 文件路径被同名目录占位 → open() 抛 IsADirectoryError → SystemExit 带 ERR。"""
    prompt_path = tmp_path / "docs" / "tmp" / "hallucination-prompts-expert_review.md"
    prompt_path.mkdir(parents=True)
    with pytest.raises(SystemExit) as exc:
        _run(cli, monkeypatch, "--dry-run", "--output", str(tmp_path / "report.md"))
    assert "无法写入 prompt 文件" in str(exc.value.code)


def test_report_write_failure_exits_with_err(cli, monkeypatch, tmp_path):
    """报告路径被同名目录占位 → SystemExit 带 ERR（不抛未捕获的 OSError）。"""
    output = tmp_path / "report.md"
    output.mkdir()
    with pytest.raises(SystemExit) as exc:
        _run(cli, monkeypatch, "--output", str(output))
    assert "无法写入报告" in str(exc.value.code)


def test_unknown_module_choice_is_rejected_by_argparse(cli, monkeypatch, tmp_path):
    """未知模块名在参数解析阶段即退出 2（不进采样循环、不产生半份报告）。"""
    with pytest.raises(SystemExit) as exc:
        _run(cli, monkeypatch, "--module", "no_such_module", "--output", str(tmp_path / "report.md"))
    assert exc.value.code == 2
    assert not (tmp_path / "report.md").exists()
