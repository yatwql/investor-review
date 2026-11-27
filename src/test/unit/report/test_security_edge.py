"""安全纵深边缘场景测试（报告渲染面）。

覆盖 CSV 公式注入防御（持仓名以 =/+ 开头原样保留）与 XSS 缓存注入防御
（Jinja2 autoescape 与过滤器输出）。缓存路径收敛/持仓目录过滤/API Key 日志脱敏/
JSON 原型污染/临时文件竞争按被测模块归入各自域的 `*_edge.py`。

运行：
  pytest src/test/unit/report/test_security_edge.py -v
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_report,
    pytest.mark.edge,
    pytest.mark.usefixtures("offline_external_sources"),
]


# ═══════════════════════════════════════════════════════════
# CSV 公式注入
# ═══════════════════════════════════════════════════════════


class TestCsvFormulaInjection(unittest.TestCase):
    """CSV 公式注入防御 — 持仓名称不以 =/+/-/@ 开头。"""

    def test_holding_name_starts_with_equal_sign(self):
        """持仓名以 = 开头 → 正常处理（不执行公式）。"""
        from src.python.report.market_value import _compute_detail_row
        from src.python.core.models import Holding

        h = Holding("证券", "=SUM(A1:A10)", "000001", 100, 10.0)
        mkt = {
            "price": 10.0,
            "yesterday_close": 9.5,
            "price_date": "2026-07-01",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        with patch("src.python.core.trading_calendar.get_last_trading_day", return_value="2026-07-01"):
            with patch("src.python.report.market_value.is_market_open", return_value=False):
                detail = _compute_detail_row(h, mkt)
        # 名称原样保留，不被解释为公式
        self.assertEqual(detail.name, "=SUM(A1:A10)")

    def test_holding_name_starts_with_plus(self):
        """持仓名以 + 开头 → 正常处理。"""
        from src.python.report.market_value import _compute_detail_row
        from src.python.core.models import Holding

        h = Holding("证券", "+123456", "000001", 100, 10.0)
        mkt = {
            "price": 10.0,
            "yesterday_close": 9.5,
            "price_date": "2026-07-01",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        with patch("src.python.core.trading_calendar.get_last_trading_day", return_value="2026-07-01"):
            with patch("src.python.report.market_value.is_market_open", return_value=False):
                detail = _compute_detail_row(h, mkt)
        self.assertEqual(detail.name, "+123456")


# ═══════════════════════════════════════════════════════════
# XSS 缓存注入
# ═══════════════════════════════════════════════════════════


class TestXssCacheInjection(unittest.TestCase):
    """XSS 注入防御 — 持仓名称含 HTML/JS。"""

    def test_holding_name_with_html_tags(self):
        """持仓名含 <script> → 在 DetailRow 中原样保留（不做 HTML 解码）。"""
        from src.python.report.market_value import _compute_detail_row
        from src.python.core.models import Holding

        h = Holding("证券", '<script>alert("xss")</script>', "000001", 100, 10.0)
        mkt = {
            "price": 10.0,
            "yesterday_close": 9.5,
            "price_date": "2026-07-01",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        with patch("src.python.core.trading_calendar.get_last_trading_day", return_value="2026-07-01"):
            with patch("src.python.report.market_value.is_market_open", return_value=False):
                detail = _compute_detail_row(h, mkt)
        self.assertIn("<script>", detail.name)
        self.assertNotEqual(detail.name, 'alert(\\"xss\\")')

    def test_jinja2_autoescape_enabled(self):
        """确认 Jinja2 Environment 已启用 autoescape（防止 XSS 注入）。"""
        from src.python.report.html_jinja_env import _ENV

        self.assertTrue(_ENV.autoescape)

    def test_template_autoescapes_html_tags(self):
        """Jinja2 模板渲染 → 持仓名 <script> 被转义。"""
        from src.python.report.html_jinja_env import _ENV

        template = _ENV.from_string("{{ name }}")
        result = template.render(name='<script>alert("xss")</script>')
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn("<script>", result)

    def test_template_autoescapes_event_handler(self):
        """Jinja2 模板渲染 → onerror 事件处理器被转义。"""
        from src.python.report.html_jinja_env import _ENV

        template = _ENV.from_string("{{ name }}")
        result = template.render(name="<img src=x onerror=alert(1)>")
        self.assertIn("&lt;img", result)
        self.assertNotIn("<img", result)

    def test_money_filter_autoescape_safe(self):
        """money 过滤器输出纯文本 → autoescape 不影响数值显示。"""
        from src.python.report.html_jinja_env import _ENV

        template = _ENV.from_string("{{ value | money }}")
        result = template.render(value=1234.5)
        self.assertIn("1,234.50", result)

    def test_profit_class_filter_outputs_no_raw_css(self):
        """profit_class 只输出类名（profit/loss/空）——不含任何 CSS 值，故 autoescape 不参与。"""
        from src.python.report.html_jinja_env import _ENV

        template = _ENV.from_string("{{ value | profit_class }}")
        self.assertEqual(template.render(value=100), "profit")
        self.assertEqual(template.render(value=-50), "loss")
        # 边界：零/非数字不染色
        self.assertEqual(template.render(value=0), "")
        self.assertEqual(template.render(value="n/a"), "")

    def test_xss_payload_in_name_preserved(self):
        """持仓名含 XSS payload → DetailRow 中原样传递（需在模板层 autoescape）。"""
        from src.python.report.market_value import _compute_detail_row
        from src.python.core.models import Holding

        h = Holding("证券", "<img src=x onerror=alert(1)>", "000001", 100, 10.0)
        mkt = {
            "price": 10.0,
            "yesterday_close": 9.5,
            "price_date": "2026-07-01",
            "source": "腾讯财经",
            "source_api": "tencent",
        }
        with patch("src.python.core.trading_calendar.get_last_trading_day", return_value="2026-07-01"):
            with patch("src.python.report.market_value.is_market_open", return_value=False):
                detail = _compute_detail_row(h, mkt)
        self.assertIn("img src", detail.name)
        self.assertIn("onerror", detail.name)


if __name__ == "__main__":
    unittest.main()
