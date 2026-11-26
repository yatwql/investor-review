"""新闻页签写入的两条降级路径（`report/excel_news_warning`）。

`news_correlation` 是可选 LLM 模块：模块缺失或数据取数失败时，页签仍要占位写空表并在
进度里留 [ERR]，不能整段跳过（否则报告缺页且用户不知道原因）。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from src.python.report import excel_news_warning as module

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]

_MODULE_NAME = "src.python.report.news_correlation"


class _Prog:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.oks: list[str] = []
        self.sheet_calls: list[tuple] = []

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def info(self, msg: str) -> None:
        self.infos.append(msg)

    def ok(self, msg: str) -> None:
        self.oks.append(msg)

    def call_sheet(self, name, fn, sheet, data, llm_meta=None) -> None:
        self.sheet_calls.append((name, fn, sheet, data, llm_meta))


@pytest.fixture()
def prog() -> _Prog:
    return _Prog()


@pytest.fixture()
def hidden_news_module(monkeypatch):
    """把可选模块从 sys.modules 置空 → 任何 `from ... import` 都抛 ImportError。"""
    monkeypatch.setitem(sys.modules, _MODULE_NAME, None)


def _run(prog, **overrides):
    kwargs = {
        "sheets": {"news_correlation": MagicMock()},
        "holdings": [],
        "pen_result": {"top10": [{"name": "腾讯"}]},
        "include_news": True,
        "news_data": None,
        "news_llm_meta": None,
        "news_top_count": 50,
        "prog": prog,
    }
    kwargs.update(overrides)
    module.write_news_sheet(**kwargs)


class TestSkips:
    def test_include_news_false_writes_nothing(self, prog):
        _run(prog, include_news=False)

        assert prog.sheet_calls == []
        assert prog.errors == []


class TestMissingModule:
    def test_missing_module_records_error_and_still_calls_sheet(self, prog, hidden_news_module):
        """模块缺失 → [ERR] 登记模块名 + 仍调用 call_sheet（页签占位，不留空页）。"""
        _run(prog)

        assert prog.errors, "模块缺失必须登记为错误"
        assert "news_correlation" in prog.errors[0]
        assert prog.sheet_calls, "页签仍须占位写入"
        assert prog.sheet_calls[0][1] is None, "写入函数缺失时传 None 由 call_sheet 跳过"


class TestPrefetchedNews:
    def test_prefetched_data_is_reused(self, prog):
        _run(prog, news_data=[{"title": "a"}], news_llm_meta={"provider": "mock"})

        assert prog.oks, "复用预取数据须给 [OK] 反馈"
        assert prog.sheet_calls[0][3] == [{"title": "a"}]
        assert prog.sheet_calls[0][4] == {"provider": "mock"}


class TestFetchPath:
    def test_fetch_failure_degrades_to_empty(self, prog, monkeypatch):
        """取数抛异常 → [ERR] 提示 + 空新闻 + 空 meta，页签照写。"""
        fake = MagicMock()
        fake.build_news_data.side_effect = RuntimeError("probe fault")
        monkeypatch.setitem(sys.modules, _MODULE_NAME, fake)

        _run(prog)

        assert any("新闻数据获取失败" in e for e in prog.errors)
        assert prog.sheet_calls[0][3] == []
        assert prog.sheet_calls[0][4] == {}

    def test_fetch_success_passes_penetrated_assets(self, prog, monkeypatch):
        fake = MagicMock()
        fake.build_news_data.return_value = ([{"title": "a"}], {"provider": "mock"})
        monkeypatch.setitem(sys.modules, _MODULE_NAME, fake)

        _run(prog)

        assert fake.build_news_data.call_args.kwargs["penetrated_assets"] == [{"name": "腾讯"}]
        assert prog.sheet_calls[0][3] == [{"title": "a"}]

    def test_data_builder_missing_records_distinct_error(self, prog, monkeypatch):
        """写入函数在、取数函数缺失 → 报「数据模块缺失」，与整体模块缺失区分开。"""
        fake = MagicMock(spec=["write_news_sheet"])
        fake.write_news_sheet = MagicMock()
        monkeypatch.setitem(sys.modules, _MODULE_NAME, fake)

        _run(prog)

        assert any("数据模块缺失" in e for e in prog.errors)
        assert prog.sheet_calls[0][3] == []
