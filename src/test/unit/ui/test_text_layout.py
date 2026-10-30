"""终端文本宽度与盒线面板排版单元测试。

缺陷场景：面板行原以 `len()` 按码点补白，中文/全角字符占 2 列却只算 1，
含中文的行因此比含英文的行短，盒线右边框参差不齐；同一面板的上下边框、
分隔线、内容行又各写各的补白数，右边框对不到同一列。本文件锁定
`text_layout` 的宽度口径与「一个面板内所有行等宽」这条不变式。
"""

from __future__ import annotations

import pytest

from src.python.tui.text_layout import (
    MIN_FIELD_WIDTH,
    display_width,
    pad_right,
    render_panel,
    truncate_display,
    wrap_prompt,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_ui]


class TestDisplayWidth:
    """display_width: 按东亚宽度计列，而非码点数。"""

    def test_ascii_counts_one_column_per_char(self):
        """半角字符每字符 1 列。"""
        assert display_width("abc123") == 6

    def test_cjk_counts_two_columns_per_char(self):
        """中文每字 2 列——`len()` 在此处会少算一半。"""
        assert display_width("配置") == 4
        assert display_width("配置支持") == 8

    def test_mixed_width(self):
        """中英混排按各自宽度累加。"""
        assert display_width("配置LLM章节") == 4 + 3 + 4

    def test_ansi_color_sequences_are_not_counted(self):
        """ANSI 颜色序列不占显示列（着色开启时若按可见字符计会把宽度算多）。"""
        assert display_width("\033[92m开启\033[0m") == 4

    def test_combining_marks_are_not_counted(self):
        """组合字符附着在前一字符上，不额外占列。"""
        assert display_width("é") == 1

    def test_empty_string(self):
        """空串宽度为 0。"""
        assert display_width("") == 0


class TestPadRight:
    """pad_right: 按显示宽度补白。"""

    def test_pads_cjk_to_column(self):
        """中文按 2 列计，补到 10 列时补 6 个空格。"""
        assert pad_right("中文", 10) == "中文" + " " * 6

    def test_does_not_truncate_overlong_text(self):
        """已超宽原样返回，不截断内容。"""
        assert pad_right("超长内容超长内容", 4) == "超长内容超长内容"

    def test_exact_fit_adds_nothing(self):
        """正好等宽时不补白。"""
        assert pad_right("中文", 4) == "中文"


class TestTruncateDisplay:
    """truncate_display: 截断超宽行时必须闭合 ANSI，避免下一行继承颜色。"""

    def test_truncation_closes_color_and_counts_width(self, monkeypatch):
        monkeypatch.setattr("src.python.core.ansi_colors.RESET", "\x1b[0m")
        text = "\x1b[94m" + "长" * 10 + "\x1b[0m"
        out = truncate_display(text, 5)
        assert out.startswith("\x1b[94m")
        assert out.endswith("\x1b[0m")
        assert display_width(out) == 5
        assert "\x1b[" not in out.replace("\x1b[94m", "").replace("\x1b[0m", "")

    def test_group_heading_truncation_does_not_leak_blue(self, monkeypatch):
        """窄档截断蓝色分组标题后，紧接着的普通行不得继承蓝色。"""
        monkeypatch.setattr("src.python.core.ansi_colors.RESET", "\x1b[0m")
        heading = "\x1b[1m\x1b[94m" + "── 默认关闭的整章（3/3 开）──" + "\x1b[0m"
        out = truncate_display(heading, 10)
        assert out.endswith("\x1b[0m")
        assert display_width(out) == 10

    def test_plain_text_unchanged_when_fits(self):
        assert truncate_display("abc", 3) == "abc"


class TestRenderPanel:
    """render_panel: 一个面板内所有行等宽，右边框对齐同一列。"""

    @staticmethod
    def _widths(lines: list[str]) -> set[int]:
        return {display_width(line) for line in lines}

    def test_all_lines_share_one_width(self):
        """上下边框、分隔线、内容行（含中文行与英文行）宽度一致。"""
        lines = render_panel(
            "配置报告可选章节",
            [
                "1. 基金深度分析 [启用]",
                "2. 财经热点关联分析 [禁用]",
                None,
                "6. 报告增强子模块（数据质量/行业Beta）",
                "0. 返回主菜单",
            ],
        )
        assert len(self._widths(lines)) == 1, f"面板各行宽度不一致：{self._widths(lines)}"

    def test_short_panel_still_uniform(self):
        """内容很短时面板不缩到标题以下，各行仍等宽。"""
        lines = render_panel("配置持仓匿名化", ["► 1. 关闭"])
        assert len(self._widths(lines)) == 1
        assert display_width(lines[0]) >= MIN_FIELD_WIDTH

    def test_field_grows_to_fit_longest_row(self):
        """最长行决定面板宽度——超宽行不被截断，也不撑破右边框。"""
        long_row = "6. " + "很长的章节说明" * 8
        lines = render_panel("配置报告可选章节", [long_row])
        assert len(self._widths(lines)) == 1
        assert display_width(lines[0]) > MIN_FIELD_WIDTH

    def test_none_row_renders_full_width_divider(self):
        """None 渲染为一条撑满内区的分隔线。"""
        lines = render_panel("标题", ["内容", None])
        divider = lines[2]
        assert divider.startswith("  │─") and divider.endswith("─│")
        assert len(self._widths(lines)) == 1

    def test_empty_row_pads_to_full_width(self):
        """空串渲染为空白内文行（左右边框仍在原位）。"""
        lines = render_panel("标题", ["内容", ""])
        blank = lines[2]
        assert blank.strip(" │") == ""
        assert display_width(blank) == display_width(lines[0])

    def test_title_alone_without_rows(self):
        """无内容行时只渲染上下边框。"""
        lines = render_panel("空面板")
        assert len(lines) == 2
        assert len(self._widths(lines)) == 1

    def test_every_line_is_box_shaped(self):
        """每行都以左边框起、右边框收（无半截行）。"""
        for line in render_panel("配置持仓匿名化", ["当前模式: off", None, "► 1. 关闭", "0. 返回主菜单"]):
            assert line.startswith("  ┌") or line.startswith("  │") or line.startswith("  └")
            assert line.endswith("┐") or line.endswith("│") or line.endswith("┘")


class TestWrapPrompt:
    """wrap_prompt: input() 提示窄屏折行助手（手机短屏提示与光标不脱节）。"""

    def test_short_prompt_returned_unchanged(self):
        """宽度内的提示原样返回（宽屏零开销，行形态不变）。"""
        prompt = "  确认继续？(y/N): "
        assert wrap_prompt(prompt, columns=100) == prompt

    def test_long_prompt_wraps_within_columns(self):
        """超宽提示按显示宽度折行，每行不超列宽。"""
        prompt = "  [!] 今日 LLM 费用已达日预算上限：y=降级走缓存继续 / N=中止 (y/N): "
        result = wrap_prompt(prompt, columns=40)
        for line in result.splitlines():
            assert display_width(line) <= 40

    def test_long_prompt_ends_with_input_caret_line(self):
        """折行后末行为「  >  」输入位短尾缀，光标与提示不再脱节。"""
        prompt = "  [!] 今日 LLM 费用已达日预算上限：y=降级走缓存继续 / N=中止 (y/N): "
        result = wrap_prompt(prompt, columns=40)
        assert result.endswith("\n  >  ")

    def test_wrapped_prompt_keeps_full_text(self):
        """折行只改排版不丢字：去尾缀后按显示宽度拼接 ≈ 原提示（去空白）。"""
        prompt = "  [!] 今日 LLM 费用已达日预算上限：y=降级走缓存继续 / N=中止 (y/N): "
        body = wrap_prompt(prompt, columns=40)[: -len("\n  >  ")]
        assert "".join(body.split()) == "".join(prompt.split())


class TestInputPromptNarrowContract:
    """input() 提示窄屏契约（机检）：裸字面量提示不得超窄屏基准宽度。

    窄屏基准 40 列与 `terminal_columns` 下限一致；超长提示必须经
    `wrap_prompt(...)` 折行（AST 上表现为 input 的参数是 wrap_prompt 调用），
    防止新增交互提示在手机竖屏上折行后光标脱节。
    """

    _NARROW_FLOOR = 40

    @staticmethod
    def _tui_sources():
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[4] / "src" / "python" / "tui"
        return sorted(root.glob("*.py"))

    def test_bare_literal_prompts_fit_narrow_floor(self):
        """tui/ 全部 input() 的裸字符串提示 ≤ 40 列；超长者必须走 wrap_prompt。"""
        import ast

        from src.python.tui.text_layout import display_width

        violations = []
        for path in self._tui_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "input"):
                    continue
                if not node.args:
                    continue
                arg = node.args[0]
                # 已经包了 wrap_prompt（任意宽度）→ 合规；变量/ f-string 运行时决定 → 另测锚定
                if isinstance(arg, ast.Call):
                    func = arg.func
                    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                    if name == "wrap_prompt":
                        continue
                    continue
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    width = display_width(arg.value)
                    if width > self._NARROW_FLOOR:
                        violations.append(f"{path.name}:{node.lineno} 宽 {width} 列未折行: {arg.value!r}")
        assert violations == [], "超窄屏基准的 input() 提示须经 wrap_prompt 折行:\n" + "\n".join(violations)

    def test_named_prompts_fit_narrow_floor(self):
        """已知具名提示（无法 AST 量宽的变量形态）显式锚定 ≤ 40 列。"""
        from src.python.tui.handlers_qa import _QA_PROMPT
        from src.python.tui.text_layout import display_width

        assert display_width(_QA_PROMPT) <= self._NARROW_FLOOR
