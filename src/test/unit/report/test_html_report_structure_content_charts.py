"""test_html_report_structure_content 兄弟分片（charts）：交互图表（canvas / 数据集）。"""

from __future__ import annotations
import unittest
import pytest
from bs4 import BeautifulSoup
from .test_html_report_structure import (
    _REPORT_SECTION_DEFAULT,
    _build_minimal_render_data,
    _render_template,
)

from src.test.unit.report.test_html_report_structure_content import _DATASET_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestHtmlInteractiveCharts(unittest.TestCase):
    """交互图表模式下模板结构测试。"""

    _HISTORY = {
        "status": "ok",
        "bars": [{"date": "2026-01-01", "total_value": 100.0, "drawdown_pct": 0.0}],
        "total_return_pct": 0.1,
        "total_return": 1000.0,
        "data_start": "2026-01-01",
        "data_end": "2026-01-01",
        "max_drawdown_pct": -0.05,
        "max_drawdown": -500.0,
        "drawdown_start": "2026-01-01",
        "drawdown_end": "2026-01-01",
        "annualized_volatility": 0.18,
        "drawdown_available": True,  # 有效交易日 ≥ MIN_SPAN 才渲染回撤明细（上游计算）
        "drawdown_events": [
            {
                "peak_date": "2026-01-01",
                "trough_date": "2026-01-01",
                "recovery_date": "",
                "drawdown_pct": 5.0,
                "duration_days": 0,
                "recovery_days": None,
                "recovered": False,
            }
        ],
        "warnings": None,
        "failed_holdings": None,
        "successful_holdings": None,
    }

    # 最小穿透数据：触发 sec-penetration 渲染图表容器
    _PENETRATION = {
        "top10": [
            {
                "rank": 1,
                "name": "贵州茅台",
                "codes": ["600519"],
                "mv": 10000.0,
                "ratio_pct": 12.5,
                "sector": "白酒",
                "concepts": ["白酒"],
                "eps_text": "58",
                "dividend_text": "25.3",
                "sources": ["基金A"],
            },
            {
                "rank": 2,
                "name": "宁德时代",
                "codes": ["300750"],
                "mv": 8000.0,
                "ratio_pct": 10.0,
                "sector": "电池",
                "concepts": ["新能源"],
                "eps_text": "--",
                "dividend_text": "--",
                "sources": ["基金B"],
            },
        ],
        "summary": {
            "total_mv": 18000.0,
            "unknown_mv": 0,
            "total_funds": 2,
            "failed_funds": 0,
            "fund_breakdown": "2/2",
            "total_stocks": 0,
            "merged_count": 2,
            "top10_coverage_pct": 100.0,
            "failed_fund_details": [],
        },
    }

    def _render_interactive(
        self,
        chart_overrides: dict | None = None,
        penetration: dict | None = None,
    ) -> BeautifulSoup:
        """渲染 enable_interactive_charts=True 的模板。

        chart_overrides：覆盖默认空 dataset，用于验证各图 canvas 是否渲染。
        penetration：传入时 sec-penetration 章节渲染图表容器。
        """
        order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        numbers = {sec["key"]: sec["number"] for sec in order}
        sv_dict = {sec["key"]: True for sec in order}
        data = _build_minimal_render_data(order, numbers, sv_dict)
        data["enable_interactive_charts"] = True
        data["chart_datasets"] = {k: {"labels": [], "datasets": []} for k in _DATASET_KEYS}
        if chart_overrides:
            data["chart_datasets"].update(chart_overrides)
        if penetration is not None:
            data["penetration"] = penetration
        data["history_data"] = self._HISTORY
        return _render_template(data)

    def test_chart_box_wraps_canvases(self) -> None:
        """各图 canvas 被 .chart-box 包裹（§4.5 打印不跨页）。

        净值+回撤 + 资产构成 Doughnut 共 3 张图表。
        无穿透数据时，sec-penetration 不渲染图表容器（占位）。
        """
        overrides = {
            "category_doughnut": {"labels": ["股票"], "datasets": [{"data": [1.0]}]},
        }
        soup = self._render_interactive(chart_overrides=overrides)
        boxes = soup.select(".chart-box")
        # 净值+回撤+Doughnut+Radar 共 4 个 .chart-box（Radar 无 labels 时渲染占位容器）
        self.assertEqual(len(boxes), 4, "应恰好 4 个 .chart-box（净值+回撤+Doughnut+Radar）")
        canvas_ids = {c.get("id") for b in boxes for c in b.select("canvas")}
        self.assertIn("chart_portfolio_line", canvas_ids)
        self.assertIn("chart_drawdown", canvas_ids)
        self.assertIn("chart_category_doughnut", canvas_ids)

    def test_penetration_charts_rendered_when_data(self) -> None:
        """穿透数据存在时渲染行业分布 + 穿透 TOP10 两图。

        计划 §4.9：行业分布与穿透 TOP10 同属 sec-penetration 章节，
        有数据时图表容器渲染 canvas；穿透章节共 2 个 .chart-box。
        """
        overrides = {
            "category_doughnut": {"labels": ["股票"], "datasets": [{"data": [1.0]}]},
            "industry_bar": {"labels": ["白酒", "电池"], "datasets": [{"data": [10000.0, 8000.0]}]},
            "penetration_bar": {"labels": ["贵州茅台", "宁德时代"], "datasets": [{"data": [10000.0, 8000.0]}]},
        }
        soup = self._render_interactive(chart_overrides=overrides, penetration=self._PENETRATION)
        boxes = soup.select(".chart-box")
        # 净值+回撤+Doughnut+行业+穿透+Radar 共 6 个 .chart-box（Radar 无 labels 时渲染占位容器）
        self.assertEqual(len(boxes), 6, "应恰好 6 个 .chart-box（净值+回撤+Doughnut+行业+穿透+Radar）")
        canvas_ids = {c.get("id") for b in boxes for c in b.select("canvas")}
        for key in (
            "chart_portfolio_line",
            "chart_drawdown",
            "chart_category_doughnut",
            "chart_industry_bar",
            "chart_penetration_bar",
        ):
            self.assertIn(key, canvas_ids)
        # 行业分布 Vertical Bar 与穿透 TOP10 容器处于同一章节
        section = soup.find(id="sec-penetration")
        self.assertIsNotNone(section)
        section_canvases = {c.get("id") for c in section.select("canvas")}
        self.assertIn("chart_industry_bar", section_canvases)
        self.assertIn("chart_penetration_bar", section_canvases)

    def test_industry_and_penetration_bars_both_vertical(self) -> None:
        """行业分布与穿透 TOP10 柱状图风格统一为垂直（竖桩）。

        穿透模块两图并排：行业分布原为 indexAxis:'y' 水平条，穿透 TOP10 为
        垂直条，风格不一致。统一后两图 aria-label 均应描述"垂直柱状图"、
        不含"水平"字样。
        """
        overrides = {
            "industry_bar": {"labels": ["白酒", "电池"], "datasets": [{"data": [10000.0, 8000.0]}]},
            "penetration_bar": {"labels": ["贵州茅台", "宁德时代"], "datasets": [{"data": [10000.0, 8000.0]}]},
        }
        soup = self._render_interactive(chart_overrides=overrides, penetration=self._PENETRATION)
        for key in ("chart_industry_bar", "chart_penetration_bar"):
            label = soup.find(id=key).get("aria-label")
            self.assertIn("垂直柱状图", label, f"{key} aria-label 应描述垂直柱状图")
            self.assertNotIn("水平", label, f"{key} aria-label 不应残留「水平柱状图」描述")

    def test_industry_empty_note_when_no_data(self) -> None:
        """行业数据全不可用时显示"行业数据暂不可用"。

        §4.12 空值语义：dataset 无 labels 时模板渲染占位提示，不输出空 canvas。
        """
        overrides = {
            "category_doughnut": {"labels": ["股票"], "datasets": [{"data": [1.0]}]},
            "penetration_bar": {"labels": ["贵州茅台"], "datasets": [{"data": [10000.0]}]},
        }
        soup = self._render_interactive(chart_overrides=overrides, penetration=self._PENETRATION)
        section = soup.find(id="sec-penetration")
        note = section.select_one(".chart-empty-note")
        self.assertIsNotNone(note, "行业数据为空时应渲染占位提示")
        self.assertIn("行业数据暂不可用", note.get_text())
        self.assertIsNone(section.find(id="chart_industry_bar"), "空数据时不应输出 industry canvas")

    def test_penetration_none_shows_placeholder(self) -> None:
        """penetration=None 时显示"暂无穿透数据"占位，不渲染图表容器。"""
        soup = self._render_interactive()
        section = soup.find(id="sec-penetration")
        self.assertIsNotNone(section)
        self.assertIsNotNone(section.select_one(".empty-note"))
        self.assertIsNone(section.find(id="chart_industry_bar"))
        self.assertIsNone(section.find(id="chart_penetration_bar"))

    def test_all_charts_have_captions(self) -> None:
        """6 张图均在下方渲染图下说明（.chart-caption），标注该图是什么图表。

        用户需求：报告中每个图表下方标注图表说明（如「TOP 10 持仓资产」）。
        说明置于 .chart-box 容器外（避免固定高度溢出），跟随 canvas 渲染分支。
        """
        overrides = {
            "category_doughnut": {"labels": ["股票"], "datasets": [{"data": [1.0]}]},
            "industry_bar": {"labels": ["白酒", "电池"], "datasets": [{"data": [10000.0, 8000.0]}]},
            "penetration_bar": {"labels": ["贵州茅台", "宁德时代"], "datasets": [{"data": [10000.0, 8000.0]}]},
            "radar": {"labels": ["夏普比率"], "datasets": [{"label": "量化指标", "data": [1.2]}]},
        }
        soup = self._render_interactive(chart_overrides=overrides, penetration=self._PENETRATION)
        captions = soup.select(".chart-caption")
        self.assertEqual(len(captions), 6, "6 张图应恰好渲染 6 个图下说明")
        texts = [c.get_text(strip=True) for c in captions]
        for expected in (
            "组合净值走势",
            "历史回撤走势",
            "资产构成分布",
            "持仓行业分布",
            "TOP 10 持仓资产",
            "组合量化指标画像",
        ):
            self.assertIn(expected, texts, f"图下说明应包含「{expected}」")
        # 穿透 TOP10 图注位于其 canvas 之后
        pen_caption = soup.find("div", class_="chart-caption", string="TOP 10 持仓资产")
        self.assertIsNotNone(pen_caption)
        pen_canvas = soup.find(id="chart_penetration_bar")
        pen_box = pen_canvas.parent  # .chart-box
        box_next = pen_box.find_next_sibling()
        self.assertEqual(box_next, pen_caption, "穿透 TOP10 图注应紧跟其图表容器")

    def test_caption_not_rendered_when_chart_empty(self) -> None:
        """图表数据为空时对应图注不渲染（说明跟随 canvas 渲染分支）。

        净值/回撤 canvas 无条件渲染（无 labels 守卫）→ 图注仍出现；
        Doughnut/行业/穿透/Radar 空数据 → 渲染占位而非图注。
        """
        soup = self._render_interactive()  # chart_datasets 全空
        captions = soup.select(".chart-caption")
        texts = [c.get_text(strip=True) for c in captions]
        self.assertEqual(len(captions), 2, "仅净值+回撤两图有图注（其余四图空数据）")
        self.assertIn("组合净值走势", texts)
        self.assertIn("历史回撤走势", texts)
        for absent in ("资产构成分布", "持仓行业分布", "TOP 10 持仓资产", "组合量化指标画像"):
            self.assertNotIn(absent, texts, f"空数据时不应渲染图注「{absent}」")

    def test_radar_chart_rendered_when_labels(self) -> None:
        """量化指标 radar 有 labels 时渲染 canvas。"""
        overrides = {
            "radar": {
                "labels": ["夏普比率", "卡玛比率"],
                "datasets": [{"label": "量化指标", "data": [1.2, 0.8]}],
            },
        }
        soup = self._render_interactive(chart_overrides=overrides)
        section = soup.find(id="sec-portfolio_history_drawdown")
        self.assertIsNotNone(section)
        radar_canvas = section.find(id="chart_radar")
        self.assertIsNotNone(radar_canvas)
        # canvas 的直接父级即 .chart-box 容器
        self.assertIn("chart-box", radar_canvas.parent.get("class", []))

    def test_radar_empty_note_when_no_labels(self) -> None:
        """radar 无 labels 时显示"量化指标数据不足"占位，不渲染 canvas。"""
        soup = self._render_interactive()
        section = soup.find(id="sec-portfolio_history_drawdown")
        note = section.select_one(".chart-empty-note")
        self.assertIsNotNone(note)
        self.assertIn("量化指标数据不足", note.get_text())
        self.assertIsNone(section.find(id="chart_radar"))

    def test_radar_data_unavailable_placeholder(self) -> None:
        """data_unavailable=True 时显示降级占位（口径：数据不可用 + 原因）。"""
        overrides = {"radar": {"labels": ["夏普比率"], "datasets": [{"data": [1.2]}]}}
        order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        numbers = {sec["key"]: sec["number"] for sec in order}
        sv_dict = {sec["key"]: True for sec in order}
        data = _build_minimal_render_data(order, numbers, sv_dict)
        data["enable_interactive_charts"] = True
        data["data_unavailable"] = True  # 持仓有成本但市值全 0
        data["chart_datasets"] = {k: {"labels": [], "datasets": []} for k in _DATASET_KEYS}
        data["chart_datasets"].update(overrides)
        data["history_data"] = self._HISTORY
        soup = _render_template(data)
        section = soup.find(id="sec-portfolio_history_drawdown")
        note = section.select_one(".chart-empty-note")
        self.assertIsNotNone(note)
        self.assertIn("数据不可用：未获取持仓市值数据，量化指标暂停计算", note.get_text())
        self.assertIsNone(section.find(id="chart_radar"))

    def test_all_chart_canvases_have_a11y_attrs(self) -> None:
        """6 个 Chart.js canvas 均含可访问性属性（§4.8）。

        模板 6 处 canvas 补 aria-label + role="img" + 内嵌 fallback 文本：
        屏幕阅读器读出图表含义，降级环境（Canvas/JS 不可用）读 fallback
        指引用户看明细表格——与 test-chart.html 示范写法对齐。
        """
        overrides = {
            "category_doughnut": {"labels": ["股票"], "datasets": [{"data": [1.0]}]},
            "industry_bar": {"labels": ["白酒"], "datasets": [{"data": [10000.0]}]},
            "penetration_bar": {"labels": ["贵州茅台"], "datasets": [{"data": [10000.0]}]},
            "radar": {"labels": ["夏普比率"], "datasets": [{"data": [1.2]}]},
        }
        soup = self._render_interactive(chart_overrides=overrides, penetration=self._PENETRATION)
        for key in _DATASET_KEYS:
            canvas = soup.find(id=f"chart_{key}")
            self.assertIsNotNone(canvas, f"{key} canvas 应渲染（Flag ON + 数据存在）")
            label = canvas.get("aria-label")
            self.assertTrue(label, f"{key} canvas 应含 aria-label")
            self.assertIn("悬停查看", label, f"{key} aria-label 应描述图表含义")
            self.assertEqual(canvas.get("role"), "img", f"{key} canvas role 应为 img")
            self.assertTrue(
                canvas.get_text().strip(),
                f"{key} canvas 应含内嵌 fallback 文本（降级环境指引）",
            )

    def test_chart_scripts_loaded_in_order(self) -> None:
        """加载顺序：chart-print → chart-config → chart-export → chart-common → chart-init（登记/导出/公共 helper 先于初始化）。"""
        soup = self._render_interactive()
        chart_scripts = [s.get("src") for s in soup.select("script[src]") if (s.get("src") or "").startswith("chart-")]
        for fname in ("chart-print.js", "chart-config.js", "chart-export.js", "chart-common.js", "chart-init.js"):
            self.assertIn(fname, chart_scripts, f"{fname} 应被模板引用")
        self.assertLess(
            chart_scripts.index("chart-print.js"),
            chart_scripts.index("chart-config.js"),
            "chart-print.js 必须在 chart-config.js 之前加载",
        )
        self.assertLess(
            chart_scripts.index("chart-config.js"),
            chart_scripts.index("chart-export.js"),
            "chart-config.js 必须在 chart-export.js 之前加载",
        )
        self.assertLess(
            chart_scripts.index("chart-export.js"),
            chart_scripts.index("chart-common.js"),
            "chart-export.js 必须在 chart-common.js 之前加载",
        )
        self.assertLess(
            chart_scripts.index("chart-common.js"),
            chart_scripts.index("chart-init.js"),
            "chart-common.js 必须在 chart-init.js 之前加载（chart-init 依赖 ChartCommon）",
        )

    def test_print_css_forces_light_theme(self) -> None:
        """/media print 覆盖 --chart-* 为浅色 + .chart-box break-inside（§4.5）。"""
        soup = self._render_interactive()
        style = soup.find("style").get_text()
        # 打印覆盖只在 @media print 内出现（主 :root 是 #333333，这里是 #000）
        self.assertIn("--chart-text: #000", style)
        self.assertIn("--chart-grid", style)
        self.assertIn(".chart-box", style)
        self.assertIn("break-inside: avoid", style)

    def test_old_canvas_path_absent(self) -> None:
        """交互模式下旧 Canvas 兜底路径不输出。"""
        soup = self._render_interactive()
        self.assertIsNone(soup.find(id="portfolioChart"))
        self.assertIsNone(soup.find(id="drawdownChart"))

    def test_sole_chartjs_renderer_regression(self) -> None:
        """Chart.js 为唯一渲染器：历史章输出交互 canvas，旧 Canvas 路径零残留。

        enable_interactive_charts 开关已随 Canvas 回退分支移除（回归锚点）：
          - chart_portfolio_line / chart_drawdown / chart_radar canvas 均输出
          - 旧 portfolioChart / drawdownChart canvas 与 drawSimpleChart 定义不再出现
        """
        order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        numbers = {sec["key"]: sec["number"] for sec in order}
        sv_dict = {sec["key"]: True for sec in order}
        data = _build_minimal_render_data(order, numbers, sv_dict)
        data["history_data"] = self._HISTORY
        data["chart_datasets"] = {
            k: {"labels": ["a"], "datasets": [{"data": [1.0]}]}
            for k in ("portfolio_line", "drawdown", "category_doughnut", "industry_bar", "penetration_bar", "radar")
        }
        soup = _render_template(data)

        for key in ("chart_portfolio_line", "chart_drawdown", "chart_radar"):
            self.assertIsNotNone(soup.find(id=key), f"应输出 {key} canvas")
        self.assertIsNone(soup.find(id="portfolioChart"), "旧净值 Canvas 不应再出现")
        self.assertIsNone(soup.find(id="drawdownChart"), "旧回撤 Canvas 不应再出现")
        self.assertNotIn("drawSimpleChart", str(soup), "旧绘图函数不应再出现")
