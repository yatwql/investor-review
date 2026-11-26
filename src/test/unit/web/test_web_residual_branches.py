"""web 域残余分支：非场外缺交易日回当天 / 场外缺价取官方净值 / 无匹配执行日返回 None。

三条都是「用户没填可选项」或「执行日集合为空」时的兜底，正常录入链路覆盖不到。
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.python.fetcher import nav_lookup
from src.python.web import holdings_edit, scheduler
from src.python.web.holdings_edit import PRICE_KIND_EXCHANGE, PRICE_KIND_OTC

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


class TestTradeDateDefault:
    def test_exchange_trade_without_date_defaults_to_today(self):
        assert holdings_edit._resolve_trade_date({}, PRICE_KIND_EXCHANGE, 1) == date.today().isoformat()


class TestOfficialPriceFromNav:
    def test_otc_price_falls_back_to_official_nav(self, monkeypatch):
        monkeypatch.setattr(nav_lookup, "resolve_nav_on_trade_date", lambda _code, _d: {"nav": 1.234})

        assert holdings_edit._official_price("005827", PRICE_KIND_OTC, "2026-01-05", 1) == 1.234


class TestNextFireAtWithoutWeekdays:
    def test_empty_weekday_set_has_no_next_fire(self):
        schedule = {"weekdays": [], "minutes": 9 * 60}

        assert scheduler.next_fire_at(datetime(2026, 1, 5, 8, 0), schedule) is None
