"""持仓明细行单一装配点（`report/_holding_detail_rows.py`）回归。

覆盖：两消费路径的共有字段逐项一致（编排路径 = 共有 10 字段 + 行情 3 字段）、
行动建议路径字段子集不变、`profit_rate` 百分号口径、`change_pct` 零昨收兜底、
`channel` 经 `classify_channel` 单源、`holding_days` 两侧一致附加。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.python.report._holding_detail_rows import (
    COMMON_DETAIL_FIELDS,
    MARKET_DETAIL_FIELDS,
    build_holding_detail_rows,
)
from src.python.report._report_helpers import _action_holdings_details
from src.python.report.market_value import DetailRow

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _row(**overrides) -> DetailRow:
    base = {
        "account": "证券账户",
        "name": "长江电力",
        "code": "600900",
        "price": 28.5,
        "yesterday_close": 28.0,
        "nav_date": "2026-01-05",
        "source_api": "sina",
        "shares": 100.0,
        "market_value": 2850.0,
        "cost": 2000.0,
        "profit": 850.0,
        "profit_rate": 0.425,
    }
    return DetailRow(**{**base, **overrides})


def _both_paths(details: list, transactions: list | None = None) -> tuple[list[dict], list[dict]]:
    """(编排路径行, 行动建议路径行)。"""
    orchestrated = build_holding_detail_rows(details, with_market_fields=True, transactions=transactions)
    action = build_holding_detail_rows(details, with_market_fields=False, transactions=transactions)
    return orchestrated, action


class TestPathParity:
    """两条路径必须来自同一构造点，共有字段逐项一致。"""

    def test_common_fields_identical_across_paths(self):
        details = [_row(), _row(code="110011", name="易方达中小盘", account="天天基金")]

        orchestrated, action = _both_paths(details)

        assert set(COMMON_DETAIL_FIELDS) == set(action[0])
        assert set(MARKET_DETAIL_FIELDS) == set(orchestrated[0]) - set(COMMON_DETAIL_FIELDS)
        for full, slim in zip(orchestrated, action, strict=True):
            assert {k: full[k] for k in COMMON_DETAIL_FIELDS} == slim

    def test_action_helper_delegates_to_same_builder(self):
        """`_action_holdings_details` 与 builder 的字段子集口径一致（不另起一份）。"""
        details = [_row()]

        assert _action_holdings_details(details) == build_holding_detail_rows(details, with_market_fields=False)

    def test_orchestrator_row_keeps_documented_order(self):
        """键序固定（下游快照/序列化按行字面量顺序的历史约定）。"""
        row = build_holding_detail_rows([_row()], with_market_fields=True)[0]

        assert list(row) == [
            "name",
            "code",
            "market_value",
            "cost",
            "profit",
            "profit_rate",
            "change_pct",
            "nav_date",
            "source_api",
            "shares",
            "price",
            "channel",
            "account",
        ]


class TestFieldContracts:
    """字段口径：百分号、零昨收、渠道单源。"""

    def test_profit_rate_is_percent_and_preserves_none(self):
        rows = build_holding_detail_rows(
            [_row(profit_rate=0.018712), _row(profit_rate=None)],
            with_market_fields=True,
        )

        assert rows[0]["profit_rate"] == pytest.approx(1.8712)
        assert rows[1]["profit_rate"] is None

    def test_change_pct_zero_when_yesterday_close_missing(self):
        rows = build_holding_detail_rows(
            [_row(yesterday_close=0.0), _row(yesterday_close=0.0, price=0.0)],
            with_market_fields=True,
        )

        assert rows[0]["change_pct"] == 0.0
        assert rows[1]["change_pct"] == 0.0

    def test_change_pct_uses_yesterday_close(self):
        row = build_holding_detail_rows([_row(price=30.0, yesterday_close=25.0)], with_market_fields=True)[0]

        assert row["change_pct"] == pytest.approx(20.0)

    def test_channel_and_account_come_from_account_field(self):
        """渠道判定单源：场外关键词 → 场外，缺失账户 → 场内；account 原值随行。"""
        rows = build_holding_detail_rows(
            [_row(account="天天基金"), _row(account=""), _row(account="证券账户")],
            with_market_fields=True,
        )

        assert [r["channel"] for r in rows] == ["场外", "场内", "场内"]
        assert [r["account"] for r in rows] == ["天天基金", "", "证券账户"]


class TestTradingDays:
    """holding_days 在两个路径上同样附加（再平衡观察期判据）。"""

    @pytest.fixture(autouse=True)
    def _fixed_trading_days(self, monkeypatch):
        import src.python.analysis.rebalance as rebalance

        monkeypatch.setattr(rebalance, "build_holding_trading_days", lambda _tx, _day: {"600900": 12})
        monkeypatch.setattr("src.python.report.market_value.get_last_trading_day", lambda: "2026-01-05")

    def test_both_paths_attach_holding_days(self):
        transactions = [SimpleNamespace(code="600900", date="2025-12-01", action="buy")]

        orchestrated, action = _both_paths([_row()], transactions)

        assert orchestrated[0]["holding_days"] == 12
        assert action[0]["holding_days"] == 12

    def test_no_transactions_leaves_key_absent(self):
        """无流水时不写该键：消费方按「未知」跳过观察期过滤。"""
        orchestrated, action = _both_paths([_row()], None)

        assert "holding_days" not in orchestrated[0]
        assert "holding_days" not in action[0]
