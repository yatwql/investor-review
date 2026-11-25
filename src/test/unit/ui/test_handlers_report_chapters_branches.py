"""``handlers_report_chapters`` 的支路：费用摘要、窄档备注行、帮助解析、实验子项与中断收尾。

面板把「无样本」「窄屏」「只读帮助」「实验子项」都收成静默分支——错一次的表现分别
是行尾费用消失、窄屏丢掉备注、``?键名`` 无反应、实验用量不显示，故逐条按其唯一
可观察产物断言。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.python.tui import handlers_report_chapters as chapters

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class _StubConfigHandlers:
    """``_ChaptersPanel`` 需要的 ``handlers_config`` 接口最小替身（记录会话收尾）。"""

    def __init__(self) -> None:
        self.closed = 0
        self.refreshed = 0

    def _read_llm_settings(self):
        return ({}, "/tmp/llm_settings.json")

    def reset_config_session(self):
        return object()

    def close_config_session(self) -> None:
        self.closed += 1

    def refresh_config(self) -> None:
        self.refreshed += 1

    def config_undo_footer(self, _session) -> None:
        return None

    def handle_config_undo(self, token, _session, _emit) -> bool:
        return token == "u"

    def input_choice(self, *_args, **_kwargs):
        return "0"


def _panel(monkeypatch) -> tuple[chapters._ChaptersPanel, _StubConfigHandlers]:
    """构造面板实例与它的 handlers_config 替身（费用摘要读取钉成空表）。"""
    monkeypatch.setenv("COLUMNS", "120")
    stub = _StubConfigHandlers()
    with patch("src.python.core.perf.module_cost_summary", return_value={}):
        return chapters._ChaptersPanel(stub), stub


def test_cost_notes_summarizes_runs_and_currency():
    """有样本时行尾费用摘要带次数与逐币种总额/均额。"""
    text = chapters._cost_notes(
        "expert_review",
        {"expert_review": {"runs": 3, "costs": {"USD": {"total": 0.5, "avg": 0.1666666}}}},
    )

    assert "3次" in text
    assert "0.5000" in text and "0.1667" in text, "总额与均额各保留四位"


def test_cost_notes_omits_when_no_cost_detail():
    """有运行次数但无逐币种金额时静默省略（不输出半截摘要）。"""
    assert chapters._cost_notes("expert_review", {"expert_review": {"runs": 2, "costs": {}}}) == ""


def test_narrow_row_keeps_notes_on_second_line():
    """窄档两行排版：备注拼在第二行的键名之后（键名恒可见）。"""
    layout = chapters._RowLayout(columns=60, name_column=12, key_column=8, number_width=2)
    row = chapters._ChapterRow(
        cursor=" ",
        number="7",
        label="智囊团深度复盘",
        key="expert_review",
        status="开",
        notes="（启用 2 次）",
    )

    lines = chapters._format_row(row, layout)

    assert len(lines) == 2, "窄档须折成两行"
    assert "（启用 2 次）" in lines[1]


def test_on_text_undo_is_consumed_without_invalid_hint(monkeypatch, capsys):
    """``u`` 已被撤回消费时不再追加「无效编号」提示。"""
    panel, _stub = _panel(monkeypatch)

    panel.on_text("u")

    assert "无效编号" not in capsys.readouterr().out


def test_help_blank_target_returns_false(monkeypatch):
    """空白帮助目标不打印任何详情（面板据此落回通用帮助一览）。"""
    panel, _stub = _panel(monkeypatch)

    assert panel.help("   ") is False


def test_help_accepts_sub_flag_name(monkeypatch, capsys):
    """``?<子项键名>`` 可直接命中子项详情（键名是稳定入口，编号会随注册表变）。"""
    panel, _stub = _panel(monkeypatch)

    from src.python.config.chapter_registry import chapter_numbers

    flag = next(f for _n, entry in chapter_numbers() for f in entry.sub_items)

    assert panel.help(flag) is True
    assert flag in capsys.readouterr().out


def test_render_prints_experimental_usage_for_subs(monkeypatch):
    """实验子项开启过时，行尾备注给出启用次数与最近日期。"""
    from src.python.config.chapter_registry import chapter_numbers
    from src.python.config.features import feature_switch_registry
    from src.python.tui.panel_runtime import NavState

    panel, _stub = _panel(monkeypatch)
    flag = next(f for _n, entry in chapter_numbers() for f in entry.sub_items)
    registry = dict(feature_switch_registry)
    base = registry[flag]
    registry[flag] = SimpleNamespace(label=base.label, default=base.default, experimental=True, desc=base.desc)
    usage = {flag: {"enabled_count": 3, "last_enabled_date": "2026-01-02T09:00:00"}}

    with (
        patch("src.python.config.features.feature_switch_registry", registry),
        patch("src.python.core.experiment_stats.load_experiment_usage", return_value=usage),
    ):
        rows = panel.render(NavState(count=len(panel.build_items())))

    frame = "\n".join(row for row in rows if row)
    assert "启用 3 次" in frame
    assert "最近 01-02" in frame


def test_run_collects_session_when_loop_interrupted(monkeypatch, capsys):
    """面板循环 EOF → 吞掉中断、收会话并刷新配置（不把异常抛回主菜单）。"""
    panel, stub = _panel(monkeypatch)

    with patch.object(chapters, "panel_loop", side_effect=EOFError("eof")):
        panel.run()

    assert stub.closed == 1, "退出路径必须收会话"
    assert stub.refreshed == 1, "退出后须刷新配置让菜单按新显隐裁剪"


def test_print_detail_prints_cost_line_for_chapter(monkeypatch, capsys):
    """章节详情在近 N 日有费用样本时给出费用行（无样本则整行省略）。"""
    from src.python.config.chapter_registry import chapter_numbers

    monkeypatch.setenv("COLUMNS", "120")
    chapter = next(entry for _n, entry in chapter_numbers() if entry.source == "llm_settings")
    cost_history = {chapter.key: {"runs": 2, "costs": {"USD": {"total": 0.25, "avg": 0.125}}}}

    assert chapters._print_detail(chapter, "", {}, cost_history) is True
    assert "费用" in capsys.readouterr().out
