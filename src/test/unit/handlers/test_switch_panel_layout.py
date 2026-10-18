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


class TestPanelWidthSweep:
    """面板端到端宽度扫描：40~200 列任意宽度都不越界、窄档不画盒线。"""

    def _render(self, columns: int, keys=("0",)) -> list[str]:
        import contextlib
        import io
        from unittest.mock import patch

        from src.python.tui.handlers_config import _cmd_config_llm_modules

        buf = io.StringIO()
        with (
            patch.dict("os.environ", {"COLUMNS": str(columns)}),
            patch("os.get_terminal_size", side_effect=OSError()),
            patch("builtins.input", side_effect=list(keys)),
            patch("src.python.tui.handlers_config.press_any_key"),
            patch("src.python.tui.handlers_config.refresh_config"),
            patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json")),
        ):
            with contextlib.redirect_stdout(buf):
                _cmd_config_llm_modules()
        return [ln for ln in buf.getvalue().splitlines() if ln.strip() and not ln.startswith("20")]

    @pytest.mark.parametrize("columns", [40, 44, 52, 60, 64, 80, 95, 96, 120, 160, 200])
    def test_no_line_exceeds_terminal_width(self, columns):
        """任何宽度下（含 `?` 详情与错误提示）所有行都不超过终端列数。"""
        for lines in (
            self._render(columns),
            self._render(columns, keys=("? 3", "? news_correlation", "r 3", "zzz=on", "0")),
        ):
            for line in lines:
                assert display_width(line) <= columns, (columns, line)

    def test_narrow_drops_box_borders(self):
        """窄终端不画盒线：省下边框列宽给内容，也避免右边框随换行错位。"""
        narrow = "\n".join(self._render(50))
        assert "┌──" not in narrow and "│" not in narrow
        assert "键名用 ? 编号 查看" in narrow

    def test_wide_keeps_box_and_key_column(self):
        wide = "\n".join(self._render(140))
        assert "┌──" in wide
        assert "global_macro" in wide

    def test_narrow_does_not_repaint_after_action(self):
        """窄终端一次操作只回反馈行（`p` 才重绘）——纵向空间是手机最稀缺资源。"""
        lines = self._render(50, keys=("zzz=on", "0"))
        text = "\n".join(lines)
        assert text.count("键名用 ? 编号 查看") == 1, "操作后不应整屏重绘"
        assert "输入 p 重绘面板" in text


class TestStatusColoring:
    """状态着色：开启绿 / 关闭红（面板 34 项靠颜色一眼辨状态，不靠读字）。"""

    @staticmethod
    def _item(enabled: bool, columns: int = 120) -> str:
        return format_item(
            number=9,
            label="因子目录",
            key="factor_catalog",
            enabled=enabled,
            star="",
            marker="",
            notes="",
            columns=columns,
            name_column=26,
            key_column=25,
            number_width=2,
        )[0]

    def test_enabled_is_green_disabled_is_red(self, monkeypatch):
        """强制着色下：开启用 GREEN、关闭用 RED（ANSI 码落在方括号内）。"""
        import src.python.tui.switch_panel as sp

        monkeypatch.setattr(sp, "GREEN", "<G>", raising=True)
        monkeypatch.setattr(sp, "RED", "<R>", raising=True)
        monkeypatch.setattr(sp, "RESET", "</>", raising=True)
        assert "[<G>开启</>]" in self._item(True)
        assert "[<R>关闭</>]" in self._item(False)

    def test_narrow_short_labels_are_colored_too(self, monkeypatch):
        """窄档用「开/关」短标签，颜色同样保留（手机上一眼可辨）。"""
        import src.python.tui.switch_panel as sp

        monkeypatch.setattr(sp, "GREEN", "<G>", raising=True)
        monkeypatch.setattr(sp, "RED", "<R>", raising=True)
        monkeypatch.setattr(sp, "RESET", "</>", raising=True)
        assert "[<G>开</>]" in self._item(True, columns=50)
        assert "[<R>关</>]" in self._item(False, columns=50)

    def test_no_color_env_keeps_plain_brackets(self):
        """非 TTY / NO_COLOR：颜色常量为空 → 只剩纯文本方括号（宽度不受影响）。"""
        import src.python.tui.switch_panel as sp

        if sp.GREEN or sp.RED:  # 仅在无颜色环境下才有意义
            pytest.skip("当前环境启用了颜色（TTY）")
        assert self._item(True).count("[开启]") == 1
        assert self._item(False).count("[关闭]") == 1
