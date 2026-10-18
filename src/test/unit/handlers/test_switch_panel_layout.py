"""`[S]` 面板响应式排版单元测试（宽 / 中 / 窄三档 + 不越界不变式）。

排版的真值是终端列数：笔记本宽终端与手机 SSH 窄终端共用同一份条目数据，版面
必须逐档收敛——本文件对三档分别锁定「行数形态」「键名可见性」「不超内宽」三条
不变式，避免改文案时静态回归成某一档专属。
"""

from __future__ import annotations

import re

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
        assert "功能开关（" in narrow

    def test_wide_keeps_box_and_key_column(self):
        wide = "\n".join(self._render(140))
        assert "┌──" in wide
        assert "global_macro" in wide

    def test_narrow_failed_write_stays_on_feedback_line(self):
        """窄终端失败路径（无效赋值）不重绘：一行报错即可，`p` 才重绘面板。"""
        lines = self._render(50, keys=("zzz=on", "0"))
        text = "\n".join(lines)
        assert text.count("功能开关（") == 1, "失败路径不应整屏重绘"
        assert "输入 p 重绘面板" in text


class TestRepaintAndHelpVisible:
    """写路径即时重绘 + `?` 说明留屏（人机交互反馈即时性契约，宽窄两档）。

    反馈契约三条：①切换成功后面板立即重绘且反馈行带编号（不需再按 `p`）；
    ②窄终端 `?` 说明不被重绘顶走；③只读查询不出现「状态已更新」类误导提示。
    """

    @staticmethod
    def _run(columns: int, keys: tuple[str, ...]) -> str:
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
            patch("src.python.tui.handlers_config._apply_edit", return_value=True),
            patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json")),
        ):
            with contextlib.redirect_stdout(buf):
                _cmd_config_llm_modules()
        return buf.getvalue()

    def test_narrow_write_repaints_with_numbered_feedback(self):
        """窄终端切换成功：反馈行带编号，且面板立即重绘（不需再按 `p`）。"""
        text = self._run(40, ("3", "0"))
        plain = re.sub(r"\x1b\[[0-9;]*m", "", text)  # 剥离颜色码后匹配反馈文案
        # 反馈长句在窄屏会折成多行（名称/状态词各占一行），只锚定「[OK] + 编号」前缀
        assert re.search(r"\[OK\] 3", plain), "反馈行应带被切换项的编号"
        assert "已关闭" in plain or "已开启" in plain
        assert text.count("功能开关（") == 2, "写路径成功后应立即重绘面板"
        assert "输入 p 重绘面板" not in text

    def test_narrow_question_mark_keeps_detail_on_screen(self):
        """窄终端 `?3` 说明：详情上屏后不被整屏重绘顶走，只给 `p` 重绘提示。"""
        text = self._run(40, ("?3", "0"))
        assert text.count("功能开关（") == 1, "只读查询不应整屏重绘"
        assert "输入 p 重绘面板" in text
        assert text.index("出厂默认") > text.index("功能开关（"), "详情应出现在面板之后而非被顶走"

    def test_esc_returns_to_main_menu_without_write(self):
        """子菜单 Esc（input_choice → None）即时返回主菜单：不重绘、不写配置。"""
        import contextlib
        import io
        from unittest.mock import patch

        from src.python.tui.handlers_config import _cmd_config_llm_modules

        buf = io.StringIO()
        with (
            patch.dict("os.environ", {"COLUMNS": "40"}),
            patch("os.get_terminal_size", side_effect=OSError()),
            patch("src.python.tui.handlers_config.input_choice", return_value=None),
            patch("src.python.tui.handlers_config.press_any_key"),
            patch("src.python.tui.handlers_config.refresh_config"),
            patch("src.python.tui.handlers_config._apply_edit") as mock_apply,
            patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json")),
        ):
            with contextlib.redirect_stdout(buf):
                _cmd_config_llm_modules()
        assert buf.getvalue().count("功能开关（") == 1, "Esc 直接返回，不应重绘面板"
        mock_apply.assert_not_called()

    def test_wide_question_mark_repaints_without_stale_hint(self):
        """宽终端 `?3` 说明：随后正常重绘，且不出现「状态已更新」误导提示。"""
        text = self._run(120, ("?3", "0"))
        assert text.count("┌──") == 2, "宽档只读查询后照常重绘面板"
        assert "状态已更新" not in text, "只读查询不得暗示状态被修改"
        assert "出厂默认" in text


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


class TestNarrowKeyReveal:
    """窄屏键名按需显示：默认不占版面（编号更易按），`k` 展开键名行。"""

    @staticmethod
    def _rows(keys, columns=50) -> list[str]:
        import contextlib
        import io
        from unittest.mock import patch

        from src.python.tui.handlers_config import _cmd_config_llm_modules

        buf = io.StringIO()
        with (
            patch.dict("os.environ", {"COLUMNS": str(columns)}),
            patch("os.get_terminal_size", side_effect=OSError()),
            patch("builtins.input", side_effect=keys),
            patch("src.python.tui.handlers_config.press_any_key"),
            patch("src.python.tui.handlers_config.refresh_config"),
            patch("src.python.tui.handlers_config._read_llm_settings", return_value=({}, "/fake/llm_settings.json")),
        ):
            with contextlib.redirect_stdout(buf):
                _cmd_config_llm_modules()
        return [ln for ln in buf.getvalue().splitlines() if ln.strip() and not ln.startswith("20")]

    def test_narrow_default_hides_key_names(self):
        """窄屏默认不显示键名（手机屏幕窄、编号更好按），图例提示可按 k 展开。"""
        lines = self._rows(("0",))
        text = "\n".join(lines)
        assert "global_macro" not in text
        assert "k 显示键名" in text
        # 条目行只有「编号 名称 [状态]」，不出现英文键名
        item_rows = [ln for ln in lines if "[开]" in ln or "[关]" in ln]
        assert item_rows and all("_" not in ln for ln in item_rows)

    def test_k_reveals_key_names_under_each_item(self):
        """按 k 后以缩进行显示键名，供需要时抄写/粘贴（再按 k 收起）。"""
        lines = self._rows(("k", "0"))
        text = "\n".join(lines)
        assert "global_macro" in text and "news_correlation" in text
        assert "k 隐藏键名" in text
        # 键名行缩进在名称行之下（不与编号行同列起始）
        key_line = next(ln for ln in lines if "global_macro" in ln)
        assert key_line.lstrip().startswith("global_macro")

    def test_key_input_still_accepted_without_reveal(self):
        """键名不显示但**不取消**键名输入：直接 `键名=on|off` 仍生效（兼容脚本/熟练用户）。"""
        lines = self._rows(("doctor_check=off", "? doctor_check", "0"))
        text = "\n".join(lines)
        assert "system_failure" not in text
        assert "系统自检上屏" in text  # `? doctor_check` 查到了说明
        assert "存储  : features.json → doctor_check" in text

    def test_k_is_noop_with_hint_on_wide_terminal(self):
        """宽/中档键名恒显，按 k 给出说明性提示且不改变版面。"""
        text = "\n".join(self._rows(("k", "0"), columns=120))
        assert "已直接显示键名列" in text
