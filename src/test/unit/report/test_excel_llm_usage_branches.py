"""LLM 章节与用量页签（`report/excel_llm_usage.py`）降级分支契约测试。

锁住的契约：
  - LLM 分析章节模块缺失 / 生成异常都不冒泡，只登记错误并继续写用量页签
  - 用量页签模块未就绪时静默跳过（非关键，不报错）
  - 会话无用量数据时不写页签
  - 页签未创建时不写用量（调用方未建页签属正常降级）
  - 页签写入异常只记 DEBUG，不影响报告其余部分

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_excel_llm_usage_branches.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.python.report import excel_llm_usage

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _prog() -> MagicMock:
    return MagicMock()


def test_llm_content_module_missing_is_reported(monkeypatch):
    import src.python.report.llm_content as llm_content

    monkeypatch.delattr(llm_content, "write_llm_sheets")
    monkeypatch.setattr(excel_llm_usage, "build_llm_usage_sheet", MagicMock())
    prog = _prog()

    excel_llm_usage.write_llm_section_and_usage({}, True, None, prog)

    prog.add_error.assert_called_once()
    assert "未就绪" in prog.add_error.call_args.args[0]


def test_llm_section_exception_is_reported(monkeypatch):
    def _boom(*_a, **_k):
        raise RuntimeError("llm boom")

    monkeypatch.setattr("src.python.report.llm_content.write_llm_sheets", _boom)
    monkeypatch.setattr(excel_llm_usage, "build_llm_usage_sheet", MagicMock())
    prog = _prog()

    excel_llm_usage.write_llm_section_and_usage({}, True, None, prog)

    prog.add_error.assert_called_once()
    assert "失败" in prog.add_error.call_args.args[0]


def test_section_skipped_when_llm_not_included(monkeypatch):
    writer = MagicMock()
    monkeypatch.setattr("src.python.report.llm_content.write_llm_sheets", writer)
    monkeypatch.setattr(excel_llm_usage, "build_llm_usage_sheet", MagicMock())

    excel_llm_usage.write_llm_section_and_usage({}, False, None, _prog())

    writer.assert_not_called()


class TestBuildUsageSheet:
    """用量页签构建的降级口径。"""

    def test_missing_usage_module_skips_silently(self, monkeypatch):
        import src.python.report.summary as summary

        monkeypatch.delattr(summary, "write_llm_usage_sheet")
        ws = MagicMock()

        excel_llm_usage.build_llm_usage_sheet({"llm_usage": ws}, _prog())

        assert not ws.cell.called, "模块未就绪时不得向页签写入任何单元格"

    def test_empty_formatted_usage_skips_sheet(self, monkeypatch):
        writer = MagicMock()
        monkeypatch.setattr("src.python.llm.get_session_usage", lambda: {})
        monkeypatch.setattr("src.python.llm.format_session_usage", lambda raw: {})
        monkeypatch.setattr("src.python.report.summary.write_llm_usage_sheet", writer)

        excel_llm_usage.build_llm_usage_sheet({"llm_usage": MagicMock()}, _prog())

        writer.assert_not_called()

    def test_missing_sheet_skips_usage_write(self, monkeypatch):
        writer = MagicMock()
        monkeypatch.setattr("src.python.llm.get_session_usage", lambda: {"per_module": {}})
        monkeypatch.setattr(
            "src.python.llm.format_session_usage",
            lambda raw: {"has_usage": True, "per_module": {"global_macro": {"cached": True}}},
        )
        monkeypatch.setattr("src.python.report.summary.write_llm_usage_sheet", writer)

        excel_llm_usage.build_llm_usage_sheet({}, _prog())

        writer.assert_not_called()

    def test_sheet_write_exception_is_swallowed(self, monkeypatch, caplog):
        import logging

        writer = MagicMock(side_effect=RuntimeError("write boom"))
        monkeypatch.setattr("src.python.llm.get_session_usage", lambda: {"per_module": {}})
        monkeypatch.setattr(
            "src.python.llm.format_session_usage",
            lambda raw: {"has_usage": True, "per_module": {"global_macro": {"cached": True}}},
        )
        monkeypatch.setattr("src.python.report.summary.write_llm_usage_sheet", writer)

        caplog.set_level(logging.DEBUG)
        excel_llm_usage.build_llm_usage_sheet({"llm_usage": MagicMock()}, _prog())

        # 异常须被转成可追溯的 DEBUG 日志（不是静默 pass）
        writer.assert_called_once()
        failures = [r for r in caplog.records if "创建 LLM API 用量页签失败" in r.getMessage()]
        assert failures, "写页签失败须留 DEBUG 日志，不得静默吞掉"
        assert failures[0].levelno == logging.DEBUG
        assert "write boom" in failures[0].getMessage(), "日志须带上原始异常信息"
