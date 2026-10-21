"""HTML 报告结构测试 — 正文内容块（交互图表/主题/数据质量块/页脚/期间标注）。

覆盖场景：
  - 交互图表（Chart.js）容器、降级与开关下的渲染结构
  - 亮暗主题 class 注入与图表容器主题一致性
  - 摘要日期时间数值样式（含条件着色）
  - 数据质量章节块（dqs）的可见性与内容结构
  - 页脚试验性功能提示与报告期间标注

运行：
  pytest src/test/unit/report/test_html_report_structure_content.py -v"""

from __future__ import annotations
import re
import unittest
from pathlib import Path
import pytest
from src.python.core.constants import PROJECT_ROOT
from bs4 import BeautifulSoup
from .test_html_report_structure import (
    _REPORT_SECTION_DEFAULT,
    _build_minimal_render_data,
    _render_template,
)

_DATASET_KEYS = (
    "portfolio_line",
    "drawdown",
    "category_doughnut",
    "industry_bar",
    "penetration_bar",
    "radar",
)


pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestHtmlTheme(unittest.TestCase):
    """HTML 暗色模式（主题切换）结构测试 — 按钮/脚本/CSS 变量/打印隐藏。

    主题元素为模板静态结构（不受章节可见性影响），用 _render_interactive
    渲染完整页面后断言：
      - 浮动切换按钮存在且带 aria-label
      - theme.js 脚本被引用
      - :root 页面级 CSS 变量（--bg/--surface/--text）
      - [data-theme="dark"] 深色覆盖块
      - @media print 隐藏切换按钮
    """

    def _render_theme_soup(self) -> BeautifulSoup:
        """渲染完整交互模板（主题元素为静态结构，与章节可见性无关）。"""
        order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        numbers = {sec["key"]: sec["number"] for sec in order}
        sv_dict = {sec["key"]: True for sec in order}
        data = _build_minimal_render_data(order, numbers, sv_dict)
        data["enable_interactive_charts"] = True
        data["chart_datasets"] = {k: {"labels": [], "datasets": []} for k in _DATASET_KEYS}
        return _render_template(data)

    def test_theme_toggle_button_present(self) -> None:
        """浮动右上角切换按钮存在，含 aria-label 与 title（可访问性）。"""
        soup = self._render_theme_soup()
        btn = soup.select_one("button.theme-toggle-btn")
        self.assertIsNotNone(btn, "应存在 theme-toggle-btn 浮动切换按钮")
        self.assertEqual(btn.get("aria-label"), "切换深色模式", "按钮 aria-label 应描述主题切换")
        self.assertIsNotNone(btn.get("title"), "按钮应含 title 提示")
        self.assertIn("🌙", btn.get_text(), "浅色默认态按钮应显示 🌙 图标（可切深色）")

    def test_theme_js_loaded(self) -> None:
        """模板引用 theme.js（主题切换 主题切换脚本）。"""
        soup = self._render_theme_soup()
        scripts = [s.get("src") for s in soup.select("script[src]")]
        self.assertIn("theme.js", scripts, "模板应加载 theme.js")

    def test_theme_js_loaded_after_toc(self) -> None:
        """theme.js 在 toc.js 之后加载（保证按钮可访问性逻辑不与 toc 冲突）。"""
        soup = self._render_theme_soup()
        srcs = [s.get("src") for s in soup.select("script[src]")]
        toc_idx = srcs.index("toc.js")
        theme_idx = srcs.index("theme.js")
        self.assertLess(toc_idx, theme_idx, "toc.js 应早于 theme.js 加载")

    def test_root_css_variables(self) -> None:
        """:root 定义页面级 CSS 变量（--bg/--surface/--text 等）。"""
        soup = self._render_theme_soup()
        style = soup.find("style").get_text()
        for var_name in ("--bg:", "--surface:", "--text:", "--profit:", "--loss:"):
            self.assertIn(var_name, style, f":root 应定义 {var_name} 页面级变量")

    def test_dark_theme_override_block(self) -> None:
        """存在 [data-theme="dark"] 深色覆盖块（含深色背景/提亮语义色）。"""
        soup = self._render_theme_soup()
        style = soup.find("style").get_text()
        self.assertIn('[data-theme="dark"]', style, 'style 应含 [data-theme="dark"] 覆盖块')
        self.assertIn("--bg: #121212", style, "深色块应定义深色背景")
        self.assertIn("--surface: #1e1e1e", style, "深色块应定义深色卡片表面")

    def test_theme_button_hidden_in_print(self) -> None:
        """@media print 隐藏切换按钮（打印不出现浮动控件）。"""
        soup = self._render_theme_soup()
        style = soup.find("style").get_text()
        self.assertIn("@media print", style, "模板应含打印媒体查询")
        self.assertIn(".theme-toggle-btn { display: none", style, "打印时应隐藏主题切换按钮")

    def test_css_variables_used_for_theme_aware_colors(self) -> None:
        """语义色使用 var(--xxx) 而非硬编码（暗色下自动适配）。"""
        soup = self._render_theme_soup()
        html = str(soup)
        # 盈利/亏损色应通过变量引用；不应再出现旧硬编码红绿
        self.assertNotIn("color: #CC0000", html, "盈利色不应硬编码 #CC0000")
        self.assertNotIn("color: #009900", html, "亏损色不应硬编码 #009900")


class TestSummaryDateTimeValueStyles(unittest.TestCase):
    """投资分析汇总：统计时间/所属交易日 值单元格样式（加粗 / 加粗+加大+蓝色）。"""

    @classmethod
    def setUpClass(cls):
        cls.order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        cls.numbers = {sec["key"]: sec["number"] for sec in cls.order}
        cls.sv_dict = {sec["key"]: True for sec in cls.order}
        cls.soup = _render_template(
            _build_minimal_render_data(cls.order, cls.numbers, cls.sv_dict),
        )

    def _value_td_style(self, label: str) -> str:
        """在投资分析汇总中按标签名找对应行的值单元格（第2列）内联 style。"""
        summary = self.soup.find(id="sec-summary")
        self.assertIsNotNone(summary, "未找到 #sec-summary")
        for tr in summary.select("table.kv-table tr"):
            tds = tr.find_all("td")
            if len(tds) == 2 and tds[0].get_text(strip=True) == label:
                return tds[1].get("style", "")
        self.fail(f"未找到「{label}」行")

    def test_stat_time_value_bold(self):
        """统计时间值加粗。"""
        style = self._value_td_style("统计时间")
        self.assertRegex(
            style,
            r"font-weight:\s*(?:700|bold)",
            f"统计时间值应加粗，style={style!r}",
        )

    def test_trading_day_value_bold_larger_blue(self):
        """所属交易日值加粗+加大+蓝色。"""
        style = self._value_td_style("所属交易日")
        self.assertRegex(
            style,
            r"font-weight:\s*(?:700|bold)",
            f"所属交易日值应加粗，style={style!r}",
        )
        self.assertRegex(
            style,
            r"font-size:\s*(?:1[5-9]px|var\(--fs-(?:h1|h2|h3|kpi)\))",
            f"所属交易日字号应在章节/数值大字档，style={style!r}",
        )
        self.assertRegex(
            style,
            r"color:\s*var\(--primary\)",
            f"所属交易日值应使用品牌色 token，style={style!r}",
        )

    def test_kv_label_style_unaffected(self):
        """标签列不新增内联样式（仅值列加样式）。"""
        summary = self.soup.find(id="sec-summary")
        for tr in summary.select("table.kv-table tr"):
            tds = tr.find_all("td")
            if len(tds) == 2 and tds[0].get_text(strip=True) in ("统计时间", "所属交易日"):
                self.assertEqual(
                    tds[0].get("style", ""),
                    "",
                    "标签列不应新增内联样式",
                )


class TestFooterExperimentalNotice(unittest.TestCase):
    """页脚须自述生成条件：本报告在哪些实验性功能开启下生成。

    HTML 报告可脱离本机流转，读者既看不到 features.json，也看不到生成时的
    控制台横幅；缺了这行，行动章「历史决策复盘」等实验产物会被误读为常驻功能。
    """

    def _render_footer(self, enabled_experiments=None) -> BeautifulSoup:
        order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        numbers = {sec["key"]: sec["number"] for sec in order}
        sv_dict = {sec["key"]: True for sec in order}
        data = _build_minimal_render_data(order, numbers, sv_dict)
        if enabled_experiments is not None:
            data["enabled_experiments"] = enabled_experiments
        footer = _render_template(data).select_one(".report-footer")
        self.assertIsNotNone(footer, "页脚容器应存在")
        return footer

    def test_lists_enabled_display_names(self):
        """启用项按显示名顿号相连列出，并给出总项数与一致性提示。"""
        text = self._render_footer(["辩论-正反辩论", "决策跨期反思闭环"]).get_text()

        self.assertIn("⚗ 本报告在 2 项实验性功能开启下生成：辩论-正反辩论、决策跨期反思闭环", text)
        self.assertIn("实验功能输出质量可能不稳定，结论请自行复核", text)

    def test_no_line_when_none_enabled(self):
        """零开关时页脚一字不提实验功能（既有输出不变）。"""
        self.assertNotIn("⚗", self._render_footer([]).get_text())

    def test_no_empty_shell_when_context_absent(self):
        """上下文未注入该变量时同样不出现空壳行（模板须判空而非只判存在）。"""
        self.assertNotIn("⚗", self._render_footer().get_text())

    def test_wording_matches_excel_landing(self):
        """HTML 页脚与 Excel 落点须同一句式——两处各写各的，措辞必然漂移。"""
        from src.python.config.features import enabled_experimental_features, set_feature_enabled
        from src.python.report.experimental_notice import enabled_notice_line

        set_feature_enabled("decision_reflection", True)
        line = enabled_notice_line()
        self.assertIsNotNone(line)

        text = self._render_footer([name for _flag, name in enabled_experimental_features()]).get_text()

        self.assertIn(line, text, "HTML 页脚句式应与 Excel 落点一致")

    def test_writer_injects_context_variable(self):
        """渲染上下文须注入该变量——漏传时模板判空而静默不显示，无任何报错。"""
        import inspect

        from src.python.report import html_writer

        source = inspect.getsource(html_writer._render_template)
        self.assertIn("enabled_experiments=", source, "_render_template 应将 enabled_experiments 载入模板上下文")


class TestChartCaptionContract(unittest.TestCase):
    """无障碍图注契约：每个 canvas 在同文件内须有 `.chart-caption` 附着（图注纪律）。

    图注纪律要求 `.chart-caption` 专属图表说明；表格/统计口径附注使用
    `.note-caption`，本契约据此类名分离做静态机检。
    """

    _TMPL_ROOT = Path(PROJECT_ROOT) / "src" / "static" / "tmpl"

    def _template_files(self) -> list[Path]:
        files = [self._TMPL_ROOT / "report_template.html", self._TMPL_ROOT / "whatif_template.html"]
        files += sorted((self._TMPL_ROOT / "partials").glob("*.html"))
        return [f for f in files if f.exists()]

    def test_every_canvas_has_caption_after_in_same_file(self) -> None:
        orphan = []
        for path in self._template_files():
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"<canvas", text):
                if 'class="chart-caption"' not in text[match.start() :]:
                    orphan.append(f"{path.name}:canvas@{match.start()}")
        assert orphan == [], f"canvas 缺图注（`.chart-caption` 须出现在其后）：{orphan}"

    def test_corr_rolling_chart_has_caption(self) -> None:
        partial = self._TMPL_ROOT / "partials" / "position_structure_section.html"
        text = partial.read_text(encoding="utf-8")
        canvas_at = text.index('id="chart_corr_rolling"')
        caption_at = text.index('class="chart-caption"', canvas_at)
        assert caption_at > canvas_at

    def test_chart_caption_not_reused_for_table_notes(self) -> None:
        partial = self._TMPL_ROOT / "partials" / "portfolio_history_drawdown_section.html"
        text = partial.read_text(encoding="utf-8")
        for inner in (
            "指数层：",
            "说明：阴影/高亮区间",
            "口径 {{ monthly.caliber_label }}",
            "口径：{{ risk_adjusted_excess_data.notes",
        ):
            inner_at = text.index(">" + inner)
            div_start = text.rfind("<div", 0, inner_at)
            div_tag = text[div_start : text.index(">", div_start) + 1]
            assert 'class="note-caption"' in div_tag, f"说明附注应使用 note-caption 类：{inner}"


if __name__ == "__main__":
    unittest.main()
