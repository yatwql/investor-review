"""市值核算的降级分支（report/market_value.py）。

测试场景：
  1. 溢价率参考净值不可比较（None）→ 占位符而非抛错
  2. 00 重叠区代码按基金特征归入场外
  3. CACHE_ONLY 命中陈旧缓存 → 降级实时获取
  4. 并行取价单条异常 → 该资产记空行情，不影响其余资产
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.python.report import market_value as mv
from src.python.core.models import Holding

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


def _h(name: str, code: str, account: str = "证券账户") -> Holding:
    return Holding(account=account, name=name, code=code, shares=100.0, cost_price=1.0)


def test_premium_placeholder_when_nav_not_comparable():
    """参考净值 None（无法比较）→ 占位符（不把 TypeError 冒给报告）。"""
    assert mv._compute_premium(1.25, None, "海外科技QDII") == mv._FUND_PREMIUM_PLACEHOLDER


def test_otc_fund_by_name_in_00_overlap_zone():
    """00 前缀且名称匹配基金特征 → 归入场外（不误判成 A 股）。"""
    categories = mv.classify_holdings([_h("华夏成长混合", "002943")])
    assert [h.code for h in categories["国内场外"]] == ["002943"]
    assert categories["场内股票"] == []


def test_cache_only_stale_cache_degrades_to_live_fetch():
    """CACHE_ONLY 命中陈旧缓存（价格日期早于允许日期）→ 丢弃缓存并回到实时取数。"""
    stale = {"price": 10.0, "price_date": "2000-01-03", "source": "缓存"}
    registry = MagicMock()
    registry.get_chain.return_value = ["tencent"]
    registry.get_effective_strategy.return_value = mv.FetchStrategy.CACHE_ONLY
    registry.fetch_cached_only.return_value = stale
    live = MagicMock(return_value={"price": 11.0, "price_date": "2025-01-02", "source": "腾讯财经"})
    holding = _h("贵州茅台", "600519")
    with (
        patch.object(mv, "get_registry", return_value=registry),
        patch.object(mv, "is_market_open", return_value=False),
        patch.object(mv, "fetch_market_data", live),
        patch.object(mv, "_price_cache_fresh", return_value=False),
    ):
        details = mv._generate_details([holding], today_str="2025-01-02")

    assert (details[0].price, details[0].source) == (11.0, "腾讯财经")
    live.assert_called_once()


def test_live_fetch_exception_marks_asset_without_price():
    """并行取价抛异常 → 该资产行情为空，其余资产照常出值。"""
    broken = _h("贵州茅台", "600519")
    healthy = _h("宁德时代", "300750")

    def _fetch(code: str, _name: str) -> dict:
        if code == "600519":
            raise RuntimeError("取价失败")
        return {"price": 200.0, "price_date": "2025-01-02", "source": "腾讯财经"}

    registry = MagicMock()
    registry.get_chain.return_value = ["tencent"]
    registry.get_effective_strategy.return_value = mv.FetchStrategy.LIVE_FETCH
    with (
        patch.object(mv, "get_registry", return_value=registry),
        patch.object(mv, "is_market_open", return_value=True),
        patch.object(mv, "fetch_market_data", side_effect=_fetch),
    ):
        details = mv._generate_details([broken, healthy], today_str="2025-01-02")

    assert details[0].price == 0.0
    assert details[1].price == pytest.approx(200.0)
