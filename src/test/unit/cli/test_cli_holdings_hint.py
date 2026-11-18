"""CLI 持仓文件缺失提示：区分「旧路径残留」与「文件名对不上」，并给可执行修法。

两种缺失的修复动作完全不同（改 holdings_dir 还是改 holdings_filename），提示若只有
「文件不存在」，用户会在错误的配置键上来回试。
"""

from __future__ import annotations

import os

import pytest

from src.python.cli._handlers import _missing_holdings_hint

pytestmark = [pytest.mark.unit, pytest.mark.unit_cli]


@pytest.mark.unit
class TestMissingHoldingsHint:
    def test_missing_parent_dir_points_at_holdings_dir(self, tmp_path):
        """整条目录都不存在（路径在本机不成立）→ 点名 holdings_dir，而不是文件名。"""
        target = os.path.join(str(tmp_path), "no_such_dir", "持仓.xlsx")
        hint = _missing_holdings_hint(target)

        assert "holdings_dir" in hint
        assert "路径在本机不成立" in hint
        assert "no_such_dir" in hint

    def test_existing_dir_lists_candidates_and_points_at_filename(self, tmp_path):
        """目录在、文件名对不上 → 列出该目录现有的 xlsx，点名 holdings_filename。"""
        (tmp_path / "实盘持仓.xlsx").write_text("stub", encoding="utf-8")
        target = os.path.join(str(tmp_path), "旧名字.xlsx")
        hint = _missing_holdings_hint(target)

        assert "holdings_filename" in hint
        assert "实盘持仓.xlsx" in hint

    def test_empty_dir_asks_to_place_file(self, tmp_path):
        """目录存在但没有任何 xlsx → 明确说「没有文件」，避免误判成改名。"""
        target = os.path.join(str(tmp_path), "持仓.xlsx")
        hint = _missing_holdings_hint(target)

        assert "没有任何 .xlsx" in hint
        assert "holdings_dir" in hint
