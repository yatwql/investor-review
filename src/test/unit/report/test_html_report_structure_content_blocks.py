"""test_html_report_structure_content 兄弟分片（blocks）：数据质量块与报告期标注。"""

from __future__ import annotations
import unittest
import pytest
from bs4 import BeautifulSoup
from .test_html_report_structure import (
    _REPORT_SECTION_DEFAULT,
    _build_minimal_render_data,
    _render_template,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestHtmlDataQualityBlocks(unittest.TestCase):
    """数据质量仪表盘「品种覆盖/可信度」区块渲染回归测试。

    回归场景：`position_status.items` / `data_freshness.items` 若在模板中按属性访问，
    会命中 dict 内置 `items` 方法（bound method）而非契约键 `"items"`——
    `data_quality` 子模块开启且契约有数据时迭代 bound method 崩溃
    （TypeError: 'builtin_function_or_method' object is not iterable）。
    修复采用 `.get("items")`（与生产代码一致）。本类回归断言正常渲染不再崩溃且行内容正确。
    """

    @classmethod
    def setUpClass(cls):
        cls.order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        cls.numbers = {sec["key"]: sec["number"] for sec in cls.order}
        cls.sv_dict = {sec["key"]: True for sec in cls.order}

    def _render_dq(self, position_status, data_freshness):
        render_data = _build_minimal_render_data(self.order, self.numbers, self.sv_dict)
        # 数据质量区块嵌套于「数据源可用性矩阵」章节（registry 中 data_source_status
        # 为 always 类型，number=18）——渲染需使其可见
        render_data["section_visible_dict"] = {**self.sv_dict, "data_source_status": True}
        render_data["section_numbers"] = {**self.numbers, "data_source_status": 18}
        render_data["position_status"] = position_status
        render_data["data_freshness"] = data_freshness
        return _render_template(render_data)

    def test_position_status_items_rendered(self):
        """品种覆盖区块 items 正常渲染（逐品种行输出，不崩溃）。"""
        soup = self._render_dq(
            {
                "available": True,
                "items": [
                    {
                        "code": "000001",
                        "name": "平安银行",
                        "account": "全部",
                        "status": "ok",
                        "status_label": "正常",
                        "reason": "",
                    },
                    {
                        "code": "510300",
                        "name": "沪深300ETF",
                        "account": "全部",
                        "status": "stale",
                        "status_label": "过期",
                        "reason": "行情未更新",
                    },
                ],
            },
            None,
        )
        text = soup.get_text()
        self.assertIn("品种覆盖（逐品种数据状态）", text)
        self.assertIn("平安银行", text)
        self.assertIn("沪深300ETF", text)
        self.assertIn("过期", text)

    def test_data_freshness_items_rendered(self):
        """可信度区块 items 正常渲染（新鲜度 + 单日跳变列）。"""
        soup = self._render_dq(
            None,
            {
                "available": True,
                "abnormal_count": 0,
                "summary": "",
                "items": [
                    {
                        "code": "600519",
                        "name": "贵州茅台",
                        "account": "全部",
                        "freshness": "ok",
                        "freshness_label": "新鲜",
                        "change_pct": 0.5,
                        "jump": False,
                        "jump_label": None,
                    },
                    {
                        "code": "601318",
                        "name": "中国平安",
                        "account": "全部",
                        "freshness": "stale",
                        "freshness_label": "过期",
                        "change_pct": 23.4,
                        "jump": True,
                        "jump_label": "跳变",
                    },
                ],
            },
        )
        text = soup.get_text()
        self.assertIn("可信度（数据新鲜度 + 单日跳变）", text)
        self.assertIn("贵州茅台", text)
        self.assertIn("中国平安", text)
        self.assertIn("跳变", text)

    def test_empty_items_shows_fallback(self):
        """available=True 但 items 为空列表 → 显示降级占位而非崩溃。"""
        soup = self._render_dq(
            {"available": True, "items": []},
            {"available": True, "items": [], "abnormal_count": 0, "summary": ""},
        )
        text = soup.get_text()
        self.assertIn("未获取行情数据，品种覆盖无法判定", text)

    def test_header_alert_shows_when_abnormal(self):
        """数据异常时报告头部显示摘要告警行（summary + 详见第 N 章）。"""
        soup = self._render_dq(
            None,
            {
                "available": True,
                "abnormal_count": 1,
                "summary": "3 个品种，1 个数据异常",
                "items": [
                    {
                        "code": "600519",
                        "name": "贵州茅台",
                        "account": "全部",
                        "freshness": "stale",
                        "freshness_label": "过期",
                        "change_pct": 0.5,
                        "jump": False,
                        "jump_label": None,
                    }
                ],
            },
        )
        alert = soup.select_one(".report-header .data-status")
        self.assertIsNotNone(alert)
        self.assertIn("3 个品种，1 个数据异常", alert.get_text())
        self.assertIn("18", alert.get_text())  # 告警尾部引用 data_source_status 章节号

    def test_header_alert_hidden_when_all_normal(self):
        """无数据异常 → 头部不渲染摘要告警行。"""
        soup = self._render_dq(
            None,
            {
                "available": True,
                "abnormal_count": 0,
                "summary": "3 个品种，0 个数据异常",
                "items": [
                    {
                        "code": "600519",
                        "name": "贵州茅台",
                        "account": "全部",
                        "freshness": "fresh",
                        "freshness_label": "实时",
                        "change_pct": 0.5,
                        "jump": False,
                        "jump_label": None,
                    }
                ],
            },
        )
        self.assertIsNone(soup.select_one(".report-header .data-status"))

    def test_abnormal_rows_use_failed_class(self):
        """异常品种行用 src-matrix-failed 高亮，正常行用 src-matrix-ok。"""
        soup = self._render_dq(
            {
                "available": True,
                "items": [
                    {
                        "code": "600519",
                        "name": "贵州茅台",
                        "account": "全部",
                        "status": "ok",
                        "status_label": "正常",
                        "reason": "",
                    },
                    {
                        "code": "600900",
                        "name": "长江电力",
                        "account": "全部",
                        "status": "name_mismatch",
                        "status_label": "名称不匹配",
                        "reason": "名称不一致",
                    },
                ],
            },
            {
                "available": True,
                "abnormal_count": 1,
                "summary": "",
                "items": [
                    {
                        "code": "600519",
                        "name": "贵州茅台",
                        "account": "全部",
                        "freshness": "fresh",
                        "freshness_label": "实时",
                        "change_pct": 0.5,
                        "jump": False,
                        "jump_label": None,
                    },
                    {
                        "code": "600900",
                        "name": "长江电力",
                        "account": "全部",
                        "freshness": "stale",
                        "freshness_label": "过期",
                        "change_pct": 0.0,
                        "jump": False,
                        "jump_label": None,
                    },
                ],
            },
        )
        ok_texts = " ".join(s.get_text() for s in soup.select(".src-matrix-ok"))
        failed_texts = " ".join(s.get_text() for s in soup.select(".src-matrix-failed"))
        self.assertIn("正常", ok_texts)
        self.assertIn("实时", ok_texts)
        self.assertIn("名称不匹配", failed_texts)
        self.assertIn("过期", failed_texts)


class TestHtmlReportPeriodAnnotations(unittest.TestCase):
    """HTML 产物须与 Excel 同口径呈现报告期时效。

    重合度按市值加权，陈旧基金剔除后必须在产物中留痕；集中度保留但标注报告期，
    报告期未推进时标「无对比意义」而非报 0；候选比较标注其风格与重合度所依据的
    报告期。缺了这些行，读者会把跨年快照当成当期持仓。
    """

    def _render(self, **overrides) -> BeautifulSoup:
        order = [dict(sec) for sec in _REPORT_SECTION_DEFAULT]
        numbers = {sec["key"]: sec["number"] for sec in order}
        sv_dict = {sec["key"]: True for sec in order}
        data = _build_minimal_render_data(order, numbers, sv_dict)
        data.update(overrides)
        return _render_template(data)

    def _conc_result(self, **extra) -> dict:
        base = {
            "name": "易方达中小盘混合",
            "code": "110011",
            "report_period": "2026-06-30",
            "report_stale": False,
            "top3_pct": 24.5,
            "top5_pct": 35.5,
            "top10_pct": 35.5,
            "prev_top10_pct": None,
            "change_pct": None,
            "alert_level": "正常",
            "is_first_check": False,
            "period_unchanged": False,
        }
        base.update(extra)
        return base

    # ── 重合度：剔除留痕 ────────────────────────────────────────

    def test_stale_fund_exclusion_banner_rendered(self):
        """陈旧基金被剔除出矩阵 → 区块顶部留痕（否则读者以为矩阵算错了）。"""
        soup = self._render(
            overlap_matrix={
                "fund_names": {"a": "基金A", "b": "基金B"},
                "funds": ["a", "b"],
                "matrix": [[1.0, 0.5], [0.5, 1.0]],
                "pairs": [],
                "stale_fund_notes": ["陈年基金（报告期 2020-03-31，已过 20 个完整季度）"],
            }
        )
        text = soup.select_one("#sec-position_structure").get_text()
        self.assertIn("已从矩阵剔除", text)
        self.assertIn("陈年基金", text)
        self.assertIn("2020-03-31", text)

    def test_no_banner_without_stale_funds(self):
        """无陈旧基金 → 不出现剔除横幅（零噪声）。"""
        soup = self._render(
            overlap_matrix={"fund_names": {}, "funds": [], "matrix": [], "pairs": [], "stale_fund_notes": []}
        )
        text = soup.select_one("#sec-position_structure").get_text()
        self.assertNotIn("已从矩阵剔除", text)

    # ── 集中度：报告期列 + 环比语义 ─────────────────────────────

    def test_concentration_period_column_rendered(self):
        """「报告期」列随数据呈现，陈旧者带（陈旧）后缀。"""
        soup = self._render(
            concentration_analysis={"results": [self._conc_result(report_period="2020-03-31", report_stale=True)]}
        )
        text = soup.select_one("#sec-position_structure").get_text()
        self.assertIn("报告期", text)
        self.assertIn("2020-03-31（陈旧）", text)

    def test_concentration_unchanged_period_marked(self):
        """报告期未推进 → 环比「无对比意义」+ 标识「报告期未推进」。"""
        soup = self._render(
            concentration_analysis={"results": [self._conc_result(period_unchanged=True, prev_top10_pct=35.5)]}
        )
        text = soup.select_one("#sec-position_structure").get_text()
        self.assertIn("无对比意义", text)
        self.assertIn("报告期未推进", text)

    def test_concentration_advanced_period_shows_change(self):
        """报告期推进 → 照常呈现环比（闸门不可误伤正常对比）。"""
        soup = self._render(
            concentration_analysis={
                "results": [self._conc_result(prev_top10_pct=30.0, change_pct=5.5, alert_level="正常")]
            }
        )
        # 取表格内文本：区块脚注本就含「无对比意义」四字
        text = soup.select_one("#sec-position_structure table").get_text()
        self.assertIn("+5.50%", text)
        self.assertNotIn("无对比意义", text)

    # ── 候选比较：报告期标注 ────────────────────────────────────

    def _candidate_data(self, **extra) -> dict:
        row = {
            "code": "000001",
            "name": "候选基金A",
            "available": True,
            "rating": "优秀",
            "syl_近1月": "1.23%",
            "syl_近3月": "5.67%",
            "syl_近6月": "11.01%",
            "syl_近1年": "-2.01%",
            "rank_text": "159/358",
            "max_drawdown": "-18.50%",
            "style": "大盘成长",
            "overlap_name": "",
            "overlap_jaccard": "--",
            "report_label": "候选基金A（报告期 2026-06-30，已过 0 个完整季度）",
        }
        base = {"available": True, "exceed_limit": False, "invalid": [], "rows": [row]}
        base.update(extra)
        return base

    def test_candidate_report_period_note_rendered(self):
        """候选的风格与重合度基于定期报告快照 → 须标注报告期。"""
        soup = self._render(candidate_data=self._candidate_data())
        text = soup.select_one("#sec-fund_performance").get_text()
        self.assertIn("持仓报告期", text)
        self.assertIn("2026-06-30", text)

    def test_candidate_stale_baseline_note_rendered(self):
        """现有持仓陈旧未计入重合度基准 → 提示读者重合度分母不含它。"""
        soup = self._render(
            candidate_data=self._candidate_data(
                stale_baseline_notes=["陈年基金（报告期 2020-03-31，已过 20 个完整季度）"]
            )
        )
        text = soup.select_one("#sec-fund_performance").get_text()
        self.assertIn("未计入重合度基准", text)
        self.assertIn("陈年基金", text)

    def test_no_notes_when_nothing_to_annotate(self):
        """无可标注项 → 不写空壳备注行。"""
        data = self._candidate_data()
        data["rows"][0]["report_label"] = ""
        soup = self._render(candidate_data=data)
        text = soup.select_one("#sec-fund_performance").get_text()
        self.assertNotIn("持仓报告期", text)
        self.assertNotIn("未计入重合度基准", text)
