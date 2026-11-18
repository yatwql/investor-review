"""本轮降级汇总出口（`core/degradation.report_degradation_summary`）——去重计数与呈现口径。

口径约定：
  - 计数按「源 + 失败类型」去重（同一源 42 次未命中合并成一行，不是 42 行）；
  - 只统计 `degraded=True` 的事件（成功记录不算降级）；
  - 无降级时 `text` 为空串——报告侧据此不出该行（产物逐字节不变）；
  - 观测读取失败返回空汇总，绝不抛（摘要非关键）。
"""

from __future__ import annotations

import pytest

from src.python.core import degradation as degradation_mod
from src.python.core.degradation import report_degradation_summary

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class _StubTracker:
    def __init__(self, events: list[dict]) -> None:
        self._events = events

    def get_log(self) -> list[dict]:
        return self._events


def _event(source_key: str, failure_type: str = "unreachable", degraded: bool = True) -> dict:
    return {"source_key": source_key, "failure_type": failure_type, "degraded": degraded}


def _patch_tracker(monkeypatch, events: list[dict]) -> None:
    monkeypatch.setattr(degradation_mod, "get_tracker", lambda *a, **k: _StubTracker(events))


class TestSummaryShape:
    def test_no_degradation_yields_empty_text(self, monkeypatch):
        _patch_tracker(monkeypatch, [])
        summary = report_degradation_summary()
        assert summary == {"count": 0, "events": 0, "lines": [], "text": ""}

    def test_non_degraded_events_ignored(self, monkeypatch):
        _patch_tracker(monkeypatch, [_event("price_stock", degraded=False)])
        assert report_degradation_summary()["count"] == 0

    def test_same_source_and_type_collapse_into_one_item(self, monkeypatch):
        _patch_tracker(monkeypatch, [_event("price_stock") for _ in range(3)])
        summary = report_degradation_summary()
        assert summary["count"] == 1
        assert summary["events"] == 3
        assert summary["lines"] == ["price_stock（unreachable）×3"]
        assert "1 项 / 3 次" in summary["text"]

    def test_distinct_failure_types_are_separate_items(self, monkeypatch):
        _patch_tracker(monkeypatch, [_event("price_stock", "unreachable"), _event("price_stock", "empty")])
        summary = report_degradation_summary()
        assert summary["count"] == 2
        assert {line.split("（")[1] for line in summary["lines"]} == {"unreachable）×1", "empty）×1"}

    def test_items_ordered_by_frequency(self, monkeypatch):
        _patch_tracker(
            monkeypatch,
            [_event("rare")] + [_event("frequent") for _ in range(5)],
        )
        assert report_degradation_summary()["lines"][0].startswith("frequent")

    def test_overflow_is_summarized(self, monkeypatch):
        _patch_tracker(monkeypatch, [_event(f"src_{index}") for index in range(6)])
        summary = report_degradation_summary(max_items=2)
        assert len(summary["lines"]) == 6
        assert "等 6 项" in summary["text"]
        assert summary["text"].count("×1") == 2, "正文只列前 max_items 项"

    def test_reader_failure_degrades_to_empty_summary(self, monkeypatch):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("账本不可读")

        monkeypatch.setattr(degradation_mod, "get_tracker", _boom)
        assert report_degradation_summary() == {"count": 0, "events": 0, "lines": [], "text": ""}


class TestReportWiring:
    def test_render_context_carries_the_summary_line(self, monkeypatch):

        monkeypatch.setattr(
            degradation_mod,
            "report_degradation_summary",
            lambda *a, **k: {"count": 1, "events": 2, "lines": [], "text": "本轮降级：1 项 / 2 次"},
        )
        from src.test.unit.report.test_html_render_context import _data_source, _prepare, _visibility, deps  # noqa: F401

        ctx = _prepare(visibility=_visibility(), data_source=_data_source())
        assert ctx.degradation_line == "本轮降级：1 项 / 2 次"

    def test_template_renders_line_only_when_present(self):
        from pathlib import Path

        template = Path("src/static/tmpl/partials/summary_section.html").read_text(encoding="utf-8")
        assert "{% if degradation_line %}" in template
        assert "{{ degradation_line }}" in template


class TestChannelOutlets:
    def test_cli_artifact_listing_appends_line_only_when_present(self, monkeypatch, capsys):
        from src.python.cli import _handlers

        monkeypatch.setattr("src.python.core.artifacts.collect_artifacts", lambda *a, **k: ["/tmp/report.html"])
        monkeypatch.setattr(
            degradation_mod,
            "report_degradation_summary",
            lambda *a, **k: {"count": 0, "events": 0, "lines": [], "text": ""},
        )
        _handlers._print_artifact_paths({}, None)
        assert "本轮降级" not in capsys.readouterr().out

        monkeypatch.setattr(
            degradation_mod,
            "report_degradation_summary",
            lambda *a, **k: {"count": 2, "events": 5, "lines": [], "text": "本轮降级：2 项 / 5 次"},
        )
        _handlers._print_artifact_paths({}, None)
        assert "本轮降级：2 项 / 5 次" in capsys.readouterr().out
