"""`[S]` 面板响应式排版单元测试（宽 / 中 / 窄三档 + 不越界不变式）。

排版的真值是终端列数：笔记本宽终端与手机 SSH 窄终端共用同一份条目数据，版面
必须逐档收敛——本文件对三档分别锁定「行数形态」「键名可见性」「不超内宽」三条
不变式，避免改文案时静态回归成某一档专属。
"""

from __future__ import annotations

import pytest

from src.python.tui.switch_panel import (
    MEDIUM_MIN_COLUMNS,
    WIDE_MIN_COLUMNS,
    format_heading,
    format_item,
    inner_width,
    layout_tier,
    legend_lines,
    terminal_columns,
    wrap_hanging,
)
from src.python.tui.text_layout import display_width

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_ITEM = dict(
    number=18,
    label="调仓纪律回放",
    key="rebalance_schedule_replay",
    enabled=False,
    star="*",
    marker="",
    notes="（启用 3 次 · 最近 10-18）",
    name_column=26,
    key_column=25,
    number_width=2,
)


class TestLayoutTier:
    """档位判定与内宽计算（阈值即真值，边界不重叠）。"""

    @pytest.mark.parametrize(
        ("columns", "expected"),
        [
            (WIDE_MIN_COLUMNS, "wide"),
            (WIDE_MIN_COLUMNS - 1, "medium"),
            (MEDIUM_MIN_COLUMNS, "medium"),
            (MEDIUM_MIN_COLUMNS - 1, "narrow"),
            (40, "narrow"),
        ],
    )
    def test_tier_boundaries(self, columns, expected):
        assert layout_tier(columns) == expected

    def test_inner_width_reserves_panel_chrome(self):
        """内宽 = 终端列数 − 面板边框与留白，且不小于可读下限。"""
        assert inner_width(120) == 114
        assert inner_width(60) == 54
        assert inner_width(20) >= 30  # 极窄终端也不压成不可读


class TestFormatItemTiers:
    """三档版面：宽=单行四列 / 中=两行 / 窄=单行压缩去键名。"""

    def test_wide_is_single_row_with_key(self):
        lines = format_item(columns=120, **_ITEM)
        assert len(lines) == 1
        assert "rebalance_schedule_replay" in lines[0]
        assert "[关闭]*" in lines[0]

    def test_medium_splits_into_two_rows_keeping_key(self):
        lines = format_item(columns=80, **_ITEM)
        assert len(lines) >= 2
        assert "调仓纪律回放" in lines[0]
        assert "rebalance_schedule_replay" in lines[1]
        assert lines[1].startswith("    ")  # 缩进续行

    def test_narrow_single_row_without_key(self):
        lines = format_item(columns=46, **_ITEM)
        assert len(lines) == 1
        assert "rebalance_schedule_replay" not in lines[0]
        assert "[关]*" in lines[0]  # 状态用短标签省列

    @pytest.mark.parametrize("columns", [40, 46, 60, 64, 80, 95, 96, 120, 200])
    def test_no_row_exceeds_inner_width(self, columns):
        """不变式：任何档位、任何宽度下每行都不超过内宽（窄终端不撑破右边框）。"""
        for lines in (
            format_item(columns=columns, **_ITEM),
            format_item(columns=columns, **{**_ITEM, "number": 7, "label": "财经新闻热点与持仓关联分析"}),
            [format_heading("🔍 分析增强·既有章内追加", 14, 16, columns)],
            legend_lines(7, columns),
        ):
            for line in lines:
                assert display_width(line) <= inner_width(columns), (columns, line)


class TestTerminalColumns:
    """终端宽度探测：显式 COLUMNS 优先，缺失时回落到实际尺寸/兜底值。"""

    def test_env_columns_wins(self, monkeypatch):
        monkeypatch.setenv("COLUMNS", "52")
        assert terminal_columns() == 52

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.delenv("COLUMNS", raising=False)
        monkeypatch.setattr("os.get_terminal_size", lambda *a, **k: (_ for _ in ()).throw(OSError()))
        assert terminal_columns(default=100) == 100

    def test_floor_is_readable_minimum(self, monkeypatch):
        monkeypatch.setenv("COLUMNS", "10")
        assert terminal_columns() == 40


class TestLegendAndHeading:
    """页脚图例与组标题：宽档给出完整口径，窄档只留操作必需信息。"""

    def test_legend_mentions_key_and_cost_in_wide(self):
        text = "\n".join(legend_lines(7, 120))
        assert "键名" in text and "近 7 日" in text and "恢复本组默认" in text

    def test_narrow_legend_drops_cost_wording(self):
        """窄档条目行不展示费用摘要 → 图例也不再解释费用口径（少一行噪声）。"""
        text = "\n".join(legend_lines(7, 46))
        assert "近 7 日" not in text
        assert "键名" in text  # 键名改由 `? 编号` 查看，仍要提示
        assert "恢复本组默认" in text

    def test_heading_carries_on_count(self):
        assert format_heading("⚙ 机制与诊断", 4, 5, 120) == "⚙ 机制与诊断（4/5 开）"

    def test_heading_truncated_on_narrow_terminal(self):
        long_head = "🔍 分析增强·既有章内追加与大量补充说明文字"
        out = format_heading(long_head, 14, 16, 46)
        assert display_width(out) <= inner_width(46)
        assert out.endswith("…")

    def test_wrap_hanging_indents_continuation(self):
        """成段文字折行后，续行带悬挂缩进而非顶到左边框。"""
        lines = wrap_hanging("  " + "很长的说明文字" * 8, 40)
        assert len(lines) > 1
        assert all(line.startswith("    ") for line in lines[1:])
