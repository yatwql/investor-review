"""行业/概念关键词扩展（`fetcher/news.py::expand_industry_keywords`）。

锁四条口径：
  - 行业名与概念名并入关键词，且「行业/概念部分」单独给出（下游据此放宽匹配门槛）；
  - 关键词按长度降序（长词优先匹配，避免短词先吃掉）；
  - 行业取数失败 → 回落原关键词（新闻聚合照常进行）；
  - 持仓过滤：只有 A 股个股进入行业链路（00 重叠区场外基金/ETF/港股一律不喂）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.python.core.models import Holding
from src.python.fetcher import news

pytestmark = [pytest.mark.unit, pytest.mark.unit_fetcher]


def _holding(name: str, code: str, account: str = "证券") -> Holding:
    return Holding(account=account, name=name, code=code, shares=100, cost_price=10.0)


class TestOnlyAShareCodesFedToIndustry:
    def test_only_a_share_stocks_fed_to_industry(self):
        """00 重叠区场外基金 / ETF / 港股均不进入行业关键词扩展（002943 回归）。"""
        holdings = [
            _holding("长江电力", "600900"),
            _holding("广发多因子灵活配置混合", "002943", account="支付宝-场外基金账户"),
            _holding("电池ETF", "561910"),
            _holding("腾讯控股", "00700"),
        ]

        fetch = MagicMock(return_value={})
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", fetch):
            news.expand_industry_keywords(holdings, None, [])

        assert fetch.call_args.args[0] == ["600900"]


class TestExpandIndustryKeywords:
    def test_keywords_expanded_with_industry_and_concepts(self):
        """行业名与概念名并入关键词，且行业/概念部分单独给出（下游据此放宽匹配门槛）。"""
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        industry = {
            "600900": {"industry": "电力行业", "concepts": ["水电", " 绿电 "]},
        }
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value=industry):
            keywords, data, lightweight = news.expand_industry_keywords(holdings, [], ["长江电力"])

        assert "电力行业" in keywords
        assert "水电" in keywords
        assert "绿电" in keywords, "概念名两侧空白须归一"
        assert lightweight == {"电力行业", "水电", "绿电"}
        assert data == industry

    def test_keywords_sorted_by_length_desc(self):
        """长词优先：保证「长江电力」不被短词先匹配走。"""
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        industry = {"600900": {"industry": "电力", "concepts": ["水力发电运营"]}}
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value=industry):
            keywords, _, _ = news.expand_industry_keywords(holdings, [], ["长江电力"])

        lengths = [len(k) for k in keywords]
        assert lengths == sorted(lengths, reverse=True)

    def test_fetch_failure_falls_back_to_original_keywords(self, caplog):
        """行业取数异常 → 原关键词 + 空数据 + 警告（新闻匹配照常进行）。"""
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", side_effect=RuntimeError("probe")):
            keywords, data, lightweight = news.expand_industry_keywords(holdings, [], ["长江电力"])

        assert keywords == ["长江电力"]
        assert (data, lightweight) == ({}, set())
        assert "行业/概念数据获取失败" in caplog.text

    def test_no_a_share_codes_skips_fetch(self):
        """无 A 股标的（纯 ETF/场外基金）→ 不发起行业取数。"""
        holdings = [Holding(account="证券", name="某ETF", code="511880", shares=100, cost_price=10.0)]
        fetch = MagicMock()
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", fetch):
            keywords, data, lightweight = news.expand_industry_keywords(holdings, [], ["某ETF"])

        fetch.assert_not_called()
        assert (keywords, data, lightweight) == (["某ETF"], {}, set())

    def test_empty_industry_payload_keeps_keywords(self):
        holdings = [Holding(account="证券", name="长江电力", code="600900", shares=100, cost_price=10.0)]
        with patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={}):
            assert news.expand_industry_keywords(holdings, [], ["长江电力"]) == (["长江电力"], {}, set())
