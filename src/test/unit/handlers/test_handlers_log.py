"""TUI 运行日志查看器（[D]→[V]）着色规则单元测试。

覆盖：级别色（ERROR/CRITICAL 红、WARNING 黄）优先；其余命中 LLM 实际调用
前缀的行用品红——与运行期控制台日志同源判据（``core.logger.is_llm_call_message``），
保证同一次报告在滚屏日志与事后查看器里，LLM 调用行看起来一致。
"""

from __future__ import annotations

import pytest

from src.python.tui import handlers_log

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestLevelColor:
    """日志行着色：级别色优先，其次 LLM 调用品红，普通行无色。"""

    @staticmethod
    def _colors(monkeypatch) -> tuple[str, str, str, str]:
        monkeypatch.setattr(handlers_log, "MAGENTA", "<M>")
        monkeypatch.setattr(handlers_log, "RED", "<R>")
        monkeypatch.setattr(handlers_log, "YELLOW", "<Y>")
        return "<M>", "<R>", "<Y>", ""

    def test_llm_call_line_uses_magenta(self, monkeypatch):
        magenta, _, _, _ = self._colors(monkeypatch)
        assert handlers_log._level_color("INFO", "  [LLM] 全球政经局势: 输入 1,024 + 输出 512") == magenta

    def test_error_line_keeps_red_even_if_llm_call(self, monkeypatch):
        _, red, _, _ = self._colors(monkeypatch)
        assert handlers_log._level_color("ERROR", "[LLM] 调用失败") == red

    def test_warning_line_keeps_yellow(self, monkeypatch):
        _, _, yellow, _ = self._colors(monkeypatch)
        assert handlers_log._level_color("WARNING", "数据偏旧") == yellow

    def test_precheck_line_not_highlighted(self, monkeypatch):
        self._colors(monkeypatch)
        assert handlers_log._level_color("INFO", "[LLM 预检] 基础模块命中 4/4") == ""

    def test_plain_info_line_uncolored(self, monkeypatch):
        self._colors(monkeypatch)
        assert handlers_log._level_color("INFO", "正在获取行情数据...") == ""
