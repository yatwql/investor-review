"""TUI 菜单调度公共链路（`tui/tui_handlers`）：用量回显降级、持仓准备、报告收尾、文件选择。

锁住的契约：
  - 会话用量取不到（LLM 模块缺位/结构异常）只记 debug，不影响菜单交互；
  - 持仓准备把「读到几条 + 流水几条」如实回显并预热新标的缓存；读取失败统一走带提示的
    错误通道（不抛给主循环）；
  - 报告收尾先停状态条（恢复终端属性）再做落地输出，最后按产物清单询问是否打开；
  - 多文件选择时越界编号给 `无效编号` 并返回 None（不误选）。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.python.tui import tui_handlers as th

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestSessionUsageDegrade:
    @pytest.mark.parametrize("exc", [ImportError, TypeError, AttributeError])
    def test_broken_usage_reader_is_silent(self, monkeypatch, exc, capsys):
        """用量读取抛缺位类异常 → 静默返回（统计回显是辅助信息，不阻断任何操作）。"""
        monkeypatch.setattr("src.python.llm.get_session_usage", lambda: (_ for _ in ()).throw(exc("boom")))

        th.print_llm_session_usage()

        assert capsys.readouterr().out == ""


class TestPrepareHoldings:
    def test_cancel_file_selection_returns_none(self, monkeypatch):
        """文件选择处取消 → 不读文件、直接返回 None。"""
        monkeypatch.setattr(th, "refresh_config", lambda: None)
        monkeypatch.setattr(th, "select_holdings_file", lambda: None)

        assert th.prepare_holdings() is None

    def test_success_reports_flows_and_warms_caches(self, monkeypatch, capsys):
        """读取成功：回显持仓与流水条数，并用状态条预热新标的缓存。"""
        holdings = [object(), object()]
        parsed = SimpleNamespace(holdings=holdings, transactions=[1], dividends=[2, 3])
        warmed: list[tuple[list, object]] = []
        reporter = object()

        monkeypatch.setattr(th, "refresh_config", lambda: None)
        monkeypatch.setattr(th, "select_holdings_file", lambda: "/tmp/持仓.xlsx")
        monkeypatch.setattr(th, "read_holdings_with_flows", lambda _p: parsed)
        monkeypatch.setattr(th, "require_holdings", lambda _h, _p: None)
        monkeypatch.setattr(th, "TuiProgressReporter", lambda: reporter)
        monkeypatch.setattr(
            "src.python.cache.operations.warm_new_asset_caches",
            lambda rows, rep: warmed.append((rows, rep)),
        )

        assert th.prepare_holdings() == (holdings, [1], [2, 3])
        assert warmed == [(holdings, reporter)]
        out = capsys.readouterr().out
        assert "成功读取 2 条持仓记录" in out
        assert "含交易流水 1 条，分红流水 2 条" in out

    def test_no_flow_sheets_skips_flow_line(self, monkeypatch, capsys):
        """无流水页签时只回显持仓条数（不打「含交易流水 0 条」噪声）。"""
        parsed = SimpleNamespace(holdings=[object()], transactions=[], dividends=[])

        monkeypatch.setattr(th, "refresh_config", lambda: None)
        monkeypatch.setattr(th, "select_holdings_file", lambda: "/tmp/持仓.xlsx")
        monkeypatch.setattr(th, "read_holdings_with_flows", lambda _p: parsed)
        monkeypatch.setattr(th, "require_holdings", lambda _h, _p: None)
        monkeypatch.setattr(th, "TuiProgressReporter", lambda: object())
        monkeypatch.setattr("src.python.cache.operations.warm_new_asset_caches", lambda _rows, _rep: None)

        assert th.prepare_holdings() == (parsed.holdings, [], [])
        out = capsys.readouterr().out
        assert "成功读取 1 条持仓记录" in out
        assert "交易流水" not in out

    def test_read_failure_goes_through_hint_channel(self, monkeypatch, capsys):
        """读取抛异常 → 走带提示的错误通道（含日志指向）并返回 None，不冒泡到主循环。"""

        def _broken(_path: str):
            raise ValueError("页签结构异常")

        monkeypatch.setattr(th, "refresh_config", lambda: None)
        monkeypatch.setattr(th, "select_holdings_file", lambda: "/tmp/持仓.xlsx")
        monkeypatch.setattr(th, "read_holdings_with_flows", _broken)

        assert th.prepare_holdings() is None
        assert "读取持仓失败" in capsys.readouterr().out

    def test_empty_holdings_rejected_without_warming(self, monkeypatch, capsys):
        """空持仓（表头在但无行）→ 明确报错并返回 None，不做缓存预热。"""
        warmed: list[str] = []

        def _require(_holdings, _path):
            raise ValueError("持仓文件为空，请在文件中填写持仓后再运行")

        monkeypatch.setattr(th, "refresh_config", lambda: None)
        monkeypatch.setattr(th, "select_holdings_file", lambda: "/tmp/持仓.xlsx")
        monkeypatch.setattr(
            th,
            "read_holdings_with_flows",
            lambda _p: SimpleNamespace(holdings=[], transactions=[], dividends=[]),
        )
        monkeypatch.setattr(th, "require_holdings", _require)
        monkeypatch.setattr("src.python.cache.operations.warm_new_asset_caches", lambda *a: warmed.append("warm"))

        assert th.prepare_holdings() is None
        assert "持仓文件为空" in capsys.readouterr().out
        assert warmed == []


class TestFinishReport:
    def test_closes_reporter_then_offers_artifacts(self, monkeypatch):
        """收尾顺序：先关状态条 → 错误/耗时摘要 → 产物清单与「是否打开」询问。"""
        order: list[str] = []

        class _Reporter:
            def close(self) -> None:
                order.append("close")

            def print_error_summary(self) -> None:
                order.append("errors")

            def print_timing_summary(self) -> None:
                order.append("timing")

        seen: list[list[str]] = []
        monkeypatch.setattr(
            "src.python.tui.report_artifacts.collect_artifacts",
            lambda cfg: order.append("collect") or ["/tmp/报告.html"],
        )
        monkeypatch.setattr(
            "src.python.tui.report_artifacts.prompt_open_artifacts",
            lambda arts: order.append("prompt") or seen.append(arts),
        )
        monkeypatch.setattr(th, "get_config_cache", lambda: {"output_dir": "/tmp"})

        th.finish_report(_Reporter())

        assert order == ["close", "errors", "timing", "collect", "prompt"]
        assert seen == [["/tmp/报告.html"]]


class TestSelectHoldingsFileOutOfRange:
    def test_out_of_range_number_reports_invalid(self, monkeypatch, tmp_path, capsys):
        """多文件时输入越界编号 → 打印 `无效编号` 并返回 None（不误选任意一个）。"""
        files = [str(tmp_path / "a.xlsx"), str(tmp_path / "b.xlsx")]
        for path in files:
            (tmp_path / path).write_text("x", encoding="utf-8")

        monkeypatch.setattr(th, "refresh_config", lambda: None)
        monkeypatch.setattr(th, "get_config_cache", lambda: {"holdings_dir": str(tmp_path), "holdings_filename": ""})
        monkeypatch.setattr("src.python.config.resolve_holdings_path", lambda _cfg: str(tmp_path / "指定.xlsx"))
        monkeypatch.setattr(th, "list_xlsx_files", lambda _dir: files)
        monkeypatch.setattr(th, "get_xlsx_info", lambda _f: {"accounts": 1})
        monkeypatch.setattr(th, "input_choice", lambda _prompt: "9")

        assert th.select_holdings_file() is None
        assert "无效编号" in capsys.readouterr().out
