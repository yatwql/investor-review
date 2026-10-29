# -*- coding: utf-8 -*-
"""错误尾巴与动作短语单源（`tui/error_tail.py` + `tui/action_hints.py`）。

守两件事：
  - ``[ERR]`` 行的上屏形状：原因与动作同处一行、建议缩进续行、缺动作时不留悬空箭头；
  - 动作短语的可执行性：每个短语的首个方括号键必须是主菜单顶层键，否则「下一步」
    指向一个不存在的入口。
"""

from __future__ import annotations

import pytest

from src.python.tui.action_hints import ACTION_TEMPLATES, action_phrase
from src.python.tui.error_tail import _ADVICE_INDENT, emit_error, format_error_lines

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestFormatErrorLines:
    """``[ERR]`` 行形状。"""

    def test_reason_and_action_on_one_line(self):
        """原因与动作短语同处首行（用户不必跨行拼读）。"""
        lines = format_error_lines("读取运行日志失败", "logs")
        assert len(lines) == 1
        assert "[ERR]" in lines[0]
        assert "读取运行日志失败" in lines[0]
        assert "→ [D]→L 看运行日志" in lines[0]

    def test_advice_is_indented_continuation(self):
        """补充建议缩进续行，与正文起始列对齐。"""
        lines = format_error_lines("系统自检执行失败", "logs", advice="详情见 logs/app.log")
        assert len(lines) == 2
        assert lines[1] == f"{_ADVICE_INDENT}详情见 logs/app.log"

    def test_missing_action_leaves_no_dangling_arrow(self):
        """未给动作键时不出现悬空箭头（无内容可指的箭头比没有箭头更糟）。"""
        assert "→" not in format_error_lines("读取失败", None)[0]
        assert "→" not in format_error_lines("读取失败", "no_such_action_key")[0]

    def test_advice_alone_still_indented(self):
        """只给建议不给动作键：仍按缩进续行渲染。"""
        lines = format_error_lines("读取失败", None, advice="请检查文件权限")
        assert lines[1].startswith(_ADVICE_INDENT)


class TestEmitError:
    """输出出口（可注入 echo：调用方按渠道替换）。"""

    def test_echo_receives_every_line(self):
        """echo 收到全部行（首行含动作短语），不直接写 stdout。"""
        seen: list[str] = []
        emit_error("写入失败", "config", advice="检查 config.json", echo=seen.append)
        assert len(seen) == 2
        assert "→ [G] 检查全局设置" in seen[0]
        assert seen[1].strip() == "检查 config.json"


class TestActionHintIntegrity:
    """动作短语的键位可执行性。"""

    def test_first_key_is_top_level_menu_key(self):
        """短语首个方括号键必须能在主菜单里按到（二级入口只校验首键）。"""
        from src.python.tui.tui_menu import MENU_ITEMS

        top_level = {key for key, _label, _cb, _is_exit in MENU_ITEMS}
        for name, phrase in ACTION_TEMPLATES.items():
            assert phrase.startswith("["), f"{name} 短语须以菜单键开头：{phrase}"
            assert phrase[1:2] in top_level, f"{name} 的首键不在主菜单：{phrase}"

    def test_phrases_have_no_whitespace_padding(self):
        """短语首尾不留空白（拼进错误行时会出现双空格）。"""
        for name, phrase in ACTION_TEMPLATES.items():
            assert phrase == phrase.strip(), name

    def test_action_phrase_unknown_key_is_empty(self):
        """未知键返回空串：调用方据此省略箭头，运行时不得抛错。"""
        assert action_phrase("no_such_action_key") == ""
        assert action_phrase(None) == ""
