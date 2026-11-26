"""CLI 处理器分支：LLM 状态渲染、持仓定位提示、费用确认中断、cache 子分支。

覆盖此前未触达的降级/中断/兜底路径：
- `_show_llm_config_status_cli`：多链（含模块偏好）与单 provider 两种渲染
- `_missing_holdings_hint`：目标目录不存在 / 目录无 xlsx 两种修法提示
- `_cli_resolve_holdings_file`：路径是空目录（无 xlsx）→ None
- `_cli_read_holdings`：文件存在但持仓为空表 → 记错误并返回 None
- `_confirm_cost_forecast`：预算询问与 y/N 询问被 Ctrl-C/EOF 打断 → 中止
- `_print_eval_status`：随报告回测成功且带 tail 时追加输出
- `_handle_cache` / `_handle_cache_update`：clean / stats / update 与未知类型的退出码
"""

from __future__ import annotations

import argparse
import contextlib
import io
from unittest.mock import MagicMock, patch

import pytest

from src.python.cli import _handlers

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    return result, buf.getvalue()


class TestShowLlmConfigStatus:
    """CLI 状态行：按 `llm_status()` 的单源分支渲染，不自行判定。"""

    def test_multi_provider_with_module_preference(self, caplog) -> None:
        status = {
            "configured": True,
            "mode": "multi",
            "strategy": "优先级",
            "providers": [{"name": "主线路", "backend": "claude", "model": "opus", "priority": "1", "circuit": "关闭"}],
            "preferred": ["全球宏观 → 主线路"],
            "chain_head": "主线路",
        }
        with patch("src.python.core.system_info.llm_status", return_value=status):
            with caplog.at_level("INFO", logger="invest"):
                _handlers._show_llm_config_status_cli()

        assert "状态: 已配置 | 策略: 优先级 | 多链服务: 1 provider" in caplog.text
        assert "▶ 模块偏好: 全球宏观 → 主线路" in caplog.text

    def test_single_provider_flat_rendering(self, caplog) -> None:
        status = {
            "configured": True,
            "mode": "flat",
            "provider": "openai",
            "model": "gpt-4o",
            "endpoint_display": "api.openai.com",
            "circuit": "关闭",
        }
        with patch("src.python.core.system_info.llm_status", return_value=status):
            with caplog.at_level("INFO", logger="invest"):
                _handlers._show_llm_config_status_cli()

        assert "状态: 已配置 | provider=openai | model=gpt-4o" in caplog.text
        assert "endpoint=api.openai.com" in caplog.text


class TestMissingHoldingsHint:
    """缺文件提示区分「目录不存在」与「目录在但文件名不对」。"""

    def test_missing_directory_points_at_holdings_dir(self, tmp_path) -> None:
        target = tmp_path / "不存在的目录" / "持仓.xlsx"

        hint = _handlers._missing_holdings_hint(str(target))

        assert "本身不存在" in hint
        assert "config.json 的 holdings_dir" in hint

    def test_existing_directory_without_xlsx_points_at_dir_content(self, tmp_path) -> None:
        hint = _handlers._missing_holdings_hint(str(tmp_path / "持仓.xlsx"))

        assert "下没有任何 .xlsx 文件" in hint
        assert "holdings_dir" in hint


class TestResolveHoldingsFile:
    """持仓路径解析的两个 None 出口。"""

    def test_directory_without_xlsx_returns_none(self, tmp_path, caplog) -> None:
        """holdings_filename 指向一个空目录 → 无 xlsx 可选，返回 None。"""
        config = {"holdings_dir": str(tmp_path), "holdings_filename": str(tmp_path)}
        with caplog.at_level("ERROR", logger="invest"):
            result = _handlers._cli_resolve_holdings_file(config)

        assert result is None
        assert f"持仓目录 {tmp_path} 中找不到 .xlsx 文件" in caplog.text

    def test_multiple_xlsx_picks_first_with_warning(self, tmp_path, caplog) -> None:
        (tmp_path / "a.xlsx").write_bytes(b"x")
        (tmp_path / "b.xlsx").write_bytes(b"x")
        config = {"holdings_dir": str(tmp_path), "holdings_filename": str(tmp_path)}
        with caplog.at_level("WARNING", logger="invest"):
            result = _handlers._cli_resolve_holdings_file(config)

        assert result is not None and result.endswith(".xlsx")
        assert f"中有多个 .xlsx 文件，自动选择第一个: {result}" in caplog.text


def test_read_holdings_empty_table_returns_none(tmp_path, caplog) -> None:
    """持仓文件可读但无有效行 → 记 error 并返回 None（不进入管线）。"""
    book = tmp_path / "持仓.xlsx"
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["名称", "代码", "持仓份额", "每份成本"])
    wb.save(book)
    config = {"holdings_dir": str(tmp_path), "holdings_filename": str(book)}

    with caplog.at_level("ERROR", logger="invest"):
        result = _handlers._cli_read_holdings(config)

    assert result is None
    assert caplog.text.strip() != ""


class TestConfirmCostForecastInterrupts:
    """交互询问被 Ctrl-C/EOF 打断 → 一律中止（(False, False)）。"""

    _FORECAST = {"ok": True, "module_count": 2, "low": 0.1, "high": 0.2}
    _BUDGET_OK = {"enabled": True, "limit": 5.0, "spent": 0.0, "exceeded": False}

    def _run(self, budget, interrupt_on_input):
        args = argparse.Namespace(yes=False, non_interactive=False)
        stdin = MagicMock()
        stdin.isatty.return_value = True
        with (
            patch("src.python.llm.cost_forecast.forecast_run_cost", return_value=self._FORECAST),
            patch("src.python.llm.cost_forecast.budget_status", return_value=budget),
            patch("src.python.llm.cost_forecast.forecast_summary_lines", return_value=[]),
            patch("src.python.cli._handlers.sys.stdin", stdin),
            patch("builtins.input", side_effect=interrupt_on_input),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return _handlers._confirm_cost_forecast(args)

    def test_budget_prompt_interrupted_aborts(self) -> None:
        budget = dict(self._BUDGET_OK, exceeded=True)
        assert self._run(budget, KeyboardInterrupt()) == (False, False)

    def test_confirm_prompt_interrupted_aborts(self) -> None:
        assert self._run(self._BUDGET_OK, EOFError()) == (False, False)


class TestPrintEvalStatus:
    """随报告回测（--post-eval）成功时附带 tail，失败只告警不改退出码。"""

    def test_success_with_tail(self) -> None:
        with (
            patch(
                "src.python.core.eval_status.run_post_eval",
                return_value={"ok": True, "tail": "命中 3 条"},
            ),
            patch("src.python.core.eval_status.format_eval_hint", return_value="评测提示") as hint,
        ):
            _out, text = _capture(_handlers._print_eval_status, post_eval=True)

        hint.assert_called_once()
        assert "[OK] 随报告回测已完成（zero-取数阶段）" in text
        assert "命中 3 条" in text

    def test_failure_reports_error_without_tail(self) -> None:
        with (
            patch("src.python.core.eval_status.run_post_eval", return_value={"ok": False, "error": "缺历史数据"}),
            patch("src.python.core.eval_status.format_eval_hint", return_value="评测提示"),
        ):
            _out, text = _capture(_handlers._print_eval_status, post_eval=True)

        assert "[!] 随报告回测未完成（不影响报告）：缺历史数据" in text

    def test_post_eval_off_only_prints_hint(self) -> None:
        with (
            patch("src.python.core.eval_status.run_post_eval") as run,
            patch("src.python.core.eval_status.format_eval_hint", return_value="评测提示"),
        ):
            _out, text = _capture(_handlers._print_eval_status, post_eval=False)

        run.assert_not_called()
        assert text.strip() == "评测提示"


class TestHandleCache:
    """cache 子命令：clean / stats / update 分派与未知分支的严重退出码。"""

    def _args(self, **over):
        base = {"verbose": False, "clean": False, "stats": False, "update": None}
        base.update(over)
        return argparse.Namespace(**base)

    def test_clean_delegates_and_succeeds(self) -> None:
        with patch("src.python.cache.operations.cleanup_cache") as cleanup:
            assert _handlers._handle_cache(self._args(clean=True), {}) == _handlers._EXIT_SUCCESS

        cleanup.assert_called_once()

    def test_stats_prints_llm_status(self) -> None:
        with (
            patch("src.python.cache.operations.get_cache_stats") as stats,
            patch.object(_handlers, "_show_llm_config_status_cli") as show,
        ):
            assert _handlers._handle_cache(self._args(stats=True), {}) == _handlers._EXIT_SUCCESS

        stats.assert_called_once()
        show.assert_called_once()

    def test_update_delegates_to_update_handler(self) -> None:
        with patch.object(_handlers, "_handle_cache_update", return_value=_handlers._EXIT_PARTIAL) as update:
            assert _handlers._handle_cache(self._args(update="all"), {"holdings_dir": "/x"}) == _handlers._EXIT_PARTIAL

        assert update.call_args.args[0] == "all"

    def test_no_action_returns_severe(self, capsys) -> None:
        with patch("src.python.cache.operations.cleanup_cache") as cleanup:
            assert _handlers._handle_cache(self._args(), {}) == _handlers._EXIT_SEVERE

        cleanup.assert_not_called()

    def test_unknown_update_type_returns_severe(self) -> None:
        reporter = MagicMock()
        holdings = [MagicMock(name="长江电力", code="600900", shares=1.0, cost_price=1.0, account="主账户")]
        with patch.object(_handlers, "_cli_read_holdings", return_value=holdings):
            assert _handlers._handle_cache_update("bogus", {}, reporter) == _handlers._EXIT_SEVERE
