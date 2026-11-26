"""TUI 报告追问（`tui/handlers_qa`）：HTML 纯文本化、报告列举降级、`[Q]` 入口门控。

锁住的契约：
  - 回答 HTML 转纯文本时块级标签换行、连续空行压成一空行（终端上不出现大段留白）；
  - 输出目录里某个报告文件读不到时间（并发删除/权限）只降级展示，不影响其余候选，
    选择屏仍可作答；
  - `[Q]` 入口的双重门控：开关关闭时明确告知开启途径并返回；选不到报告时静默返回；
    拿到报告才进追问循环。
"""

from __future__ import annotations

import os

import pytest

from src.python.tui import handlers_qa

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


@pytest.fixture
def two_reports(tmp_path):
    for name in ("主报告.html", "旧报告.html"):
        (tmp_path / name).write_text("<html></html>", encoding="utf-8")
    return tmp_path


class TestHtmlToTextLayout:
    def test_block_tag_after_inline_data_starts_new_line(self):
        """行内标签后紧跟块级标签 → 块级标签处断行（否则段落被粘在同一行）。"""
        assert handlers_qa._html_to_text("<b>x</b><p>y</p>") == "x\ny"

    def test_consecutive_blank_lines_collapse(self):
        """连续空块压成一空行：终端展示不留大段空白。"""
        assert handlers_qa._html_to_text("<div>a</div><div></div><div></div><div>b</div>") == "a\n\nb"

    def test_script_block_is_dropped(self):
        assert handlers_qa._html_to_text("<p>正文</p><script>var a=1;</script>") == "正文"


class TestResolveOutputDir:
    def test_uses_config_override(self, monkeypatch):
        """输出目录取 config 覆写值（与 Web 路由同口径），不硬编码 reports/。"""
        monkeypatch.setattr(handlers_qa, "resolve_output_dir", lambda cfg: f"resolved:{cfg['output_dir']}")
        monkeypatch.setattr("src.python.config.get_config", lambda: {"output_dir": "/data/out"})

        assert handlers_qa._resolve_output_dir() == "resolved:/data/out"


class TestListReportsDegrade:
    def test_unreadable_mtime_skips_only_that_file(self, monkeypatch, two_reports):
        """单个报告取不到 mtime（并发删除）→ 只跳过该文件，其余候选保留。"""
        real_getmtime = os.path.getmtime
        target = str(two_reports / "旧报告.html")

        def _getmtime(path):
            if str(path) == target:
                raise OSError("gone")
            return real_getmtime(path)

        monkeypatch.setattr("src.python.tui.handlers_qa.os.path.getmtime", _getmtime)

        assert handlers_qa._list_reports(str(two_reports)) == ["主报告.html"]


class TestSelectReportDegrade:
    def test_unknown_mtime_shown_as_placeholder(self, monkeypatch, two_reports, capsys):
        """列举期 mtime 正常、选择期取不到 → 该行标「时间未知」，不中断选择屏。"""
        real_getmtime = os.path.getmtime
        calls: list[int] = []

        def _getmtime(path):
            calls.append(1)
            if len(calls) > 1:  # 第 2 次起（选择屏逐行取时间）失败
                raise OSError("gone")
            return real_getmtime(path)

        monkeypatch.setattr("src.python.tui.handlers_qa.os.path.getmtime", _getmtime)
        monkeypatch.setattr(handlers_qa, "input_choice", lambda _prompt: "q")

        assert handlers_qa._select_report(str(two_reports)) is None
        assert "时间未知" in capsys.readouterr().out

    def test_esc_cancels_selection(self, monkeypatch, two_reports):
        """选择报告处按 Esc（`input_choice` 返回 None）→ 取消追问，不误选首项。"""
        monkeypatch.setattr(handlers_qa, "input_choice", lambda _prompt: None)

        assert handlers_qa._select_report(str(two_reports)) is None


class TestCmdReportQa:
    def test_switch_off_tells_how_to_enable(self, monkeypatch, capsys):
        """开关关闭时直调（菜单已裁剪，这里是竞态/直调兜底）→ 明确告知开启途径。"""
        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda _key: False)

        handlers_qa._cmd_report_qa()

        out = capsys.readouterr().out
        assert "报告追问功能未开启" in out
        assert "report_qa" in out and "[S]" in out

    def test_no_report_selected_returns_without_session(self, monkeypatch):
        """没选到报告（取消 / 目录空）→ 直接返回，不开会话、不调追问服务。"""
        started: list[str] = []
        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda _key: True)
        monkeypatch.setattr(handlers_qa, "_resolve_output_dir", lambda: "/tmp/reports")
        monkeypatch.setattr(handlers_qa, "_select_report", lambda _dir: None)
        monkeypatch.setattr(handlers_qa, "_qa_input_loop", started.append)

        handlers_qa._cmd_report_qa()

        assert started == []

    def test_selected_report_opens_input_loop(self, monkeypatch):
        """选到报告 → 进追问输入循环（会话入口唯一，业务全在同源服务里）。"""
        started: list[str] = []
        monkeypatch.setattr("src.python.config.features.is_feature_enabled", lambda _key: True)
        monkeypatch.setattr(handlers_qa, "_resolve_output_dir", lambda: "/tmp/reports")
        monkeypatch.setattr(handlers_qa, "_select_report", lambda _dir: "主报告.html")
        monkeypatch.setattr(handlers_qa, "_qa_input_loop", started.append)

        handlers_qa._cmd_report_qa()

        assert started == ["主报告.html"]
