# -*- coding: utf-8 -*-
"""提示语模板单元测试（提示四成分与默认项标注口径）。"""

from __future__ import annotations

import pytest

from src.python.tui.panel_runtime import PanelItem
from src.python.tui.prompt_text import (
    item_detail_lines,
    keys_help_lines,
    panel_prompt,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestPanelPrompt:
    """panel_prompt：动作 · 默认项 · 帮助 · 返回 四成分。"""

    def test_full_form_has_four_components(self):
        prompt = panel_prompt("输入编号切换开关", example="3", default="全部模块", help_hint="?3 查看说明")
        assert "输入编号切换开关（如 3）" in prompt
        assert "回车=全部模块" in prompt
        assert "?3 查看说明" in prompt
        assert "0 返回" in prompt
        assert prompt.endswith(": ")

    def test_default_is_action_name_not_placeholder(self):
        """默认项必须写明动作名——「回车=确定」这类无信息量写法不得由模板产生。"""
        prompt = panel_prompt("选择报告", default="最新")
        assert "回车=最新" in prompt
        assert "回车=确定" not in prompt

    def test_optional_parts_can_be_disabled(self):
        """无帮助/无返回项的面板不强行拼成分（避免提示与实际能力不符）。"""
        prompt = panel_prompt("按级别筛选", example="如 ERROR", default="全部级别", help_hint=None, back=None)
        assert "?" not in prompt and "0 返回" not in prompt
        assert "回车=全部级别" in prompt


class TestHelpLines:
    """? 帮助与 ?N 详情文案。"""

    def _items(self):
        return [
            PanelItem("1", "基金深度分析"),
            PanelItem("2", "财经热点关联分析"),
            PanelItem("0", "返回主菜单", kind="return"),
        ]

    def test_keys_help_lists_items_and_navigation(self):
        lines = keys_help_lines(self._items(), columns=80)
        text = "\n".join(lines)
        assert "可用键：" in text
        assert "1 — 基金深度分析" in text
        assert "↑ ↓" in text, "帮助必须说明导航键"
        assert "返回主菜单 — " not in text, "返回项不重复占一行（导航行已说明）"

    def test_item_detail_with_and_without_hint(self):
        item = self._items()[0]
        with_hint = "\n".join(item_detail_lines(item, hint="当前开启", columns=80))
        assert "1. 基金深度分析" in with_hint and "当前开启" in with_hint
        without = "\n".join(item_detail_lines(item, columns=80))
        assert "1. 基金深度分析" in without and "说明" not in without
