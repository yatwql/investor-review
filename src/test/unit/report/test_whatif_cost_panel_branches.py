"""调仓成本面板（`report/whatif_cost_panel.py`）降级分支契约测试。

锁住的契约：
  - 基准日线里的畸形条目（非 dict / 空日期 / 非数值收盘）不参与对齐，全无效即取不到
  - 归一化锚点为非正值时取不到（不留伪精度）
  - 空代码与「不变」腿不参与费率装配
  - 交易日计数与基准取数缺省时回落到生产实现（可注入优先）
  - 费率索引取数失败、无基金腿、无注入时一律按费率未知降级
  - 基准映射的配置/文本/行情来源在缺注入时各自回落到生产实现

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_whatif_cost_panel_branches.py -v
"""

from __future__ import annotations

import pytest

from src.python.report import whatif_cost_panel as wcp

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


def _bars(pairs: list[tuple[str, float]]) -> list[dict]:
    return [{"date": d, "close": c} for d, c in pairs]


def _sell_leg(code: str, name: str) -> dict:
    """清仓腿（有份额差才会生成成本腿）。"""
    return {
        "code": code,
        "name": name,
        "action": "清仓",
        "base_shares": 2000.0,
        "cand_shares": 0.0,
        "shares_diff": -2000.0,
        "base_cost": 20000.0,
        "cand_cost": 0.0,
        "cost_diff": -20000.0,
    }


class TestAlignBenchmarkValues:
    """基准日线对齐与归一化的边界口径。"""

    def test_non_dict_bar_is_ignored(self):
        values = wcp._align_benchmark_values(
            ["2026-03-02", "2026-03-03"], [None, {"date": "2026-03-03", "close": 10.0}]
        )

        assert values == [None, 100.0], "畸形条目跳过后，前段留缺口、首个有效日作锚点"

    def test_no_valid_close_yields_none(self):
        assert wcp._align_benchmark_values(["2026-03-02"], _bars([("2026-03-02", float("nan"))])) is None

    def test_non_positive_anchor_yields_none(self):
        assert wcp._align_benchmark_values(["2026-03-02"], _bars([("2026-03-02", 0.0)])) is None


class TestBuildPanelDegrade:
    """成本本体的降级与缺省注入。"""

    def test_blank_and_unchanged_legs_are_ignored(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.fetcher.fund_fee.fetch_fee_index", lambda codes: pytest.fail("无基金腿不得取费率")
        )

        panel = wcp.build_whatif_cost_panel(
            {"changes": [{"code": "", "action": "买入"}, {"code": "600519", "action": "不变"}]},
            snapshots=[],
        )

        assert panel["available"] is False
        assert panel["trade_cost"]["legs"] == []

    def test_default_trading_day_counter_is_used(self, monkeypatch):
        import src.python.core.trading_calendar as cal
        from src.python.analysis.fee_schedule_model import parse_redemption_fee_schedule
        from src.python.schemas.history import AccountSnapshot, SnapshotData, SnapshotHolding

        calls: list[tuple[str, str]] = []

        def _count(start, end):
            calls.append((start, end))
            return 60  # 落在 [30,365) 档 → 0.50%

        monkeypatch.setattr(cal, "count_trading_days_elapsed", _count)
        snapshots = [
            SnapshotData(
                accounts=(
                    AccountSnapshot(
                        account_name="全部",
                        holdings=(
                            SnapshotHolding(
                                code="096001", name="某债券基金", shares=2000.0, cost_price=1.0, market_value=2000.0
                            ),
                        ),
                    ),
                ),
                total_value=0.0,
                total_cost=0.0,
                total_pnl=0.0,
                timestamp="20260701T090000",
            )
        ]
        fee_index = {
            "096001": {
                "redemption": parse_redemption_fee_schedule(
                    [
                        ["小于7天", "1.50%"],
                        ["大于等于7天，小于30天", "0.75%"],
                        ["大于等于30天，小于365天", "0.50%"],
                        ["大于等于365天", "0.00%"],
                    ]
                )
            }
        }

        panel = wcp.build_whatif_cost_panel(
            {"changes": [_sell_leg("096001", "某债券基金")]},
            "2026-10-01",
            snapshots=snapshots,
            fee_index=fee_index,
        )

        assert calls == [("2026-07-01", "2026-10-01")], "缺省注入必须回落到交易日历计数器"
        assert panel["trade_cost"]["redemption_total"] == pytest.approx(100.0), "60 交易日落 0.50% 档"

    def test_fee_index_fetch_failure_degrades_to_unknown(self, monkeypatch):
        def _boom(_codes):
            raise RuntimeError("fee boom")

        monkeypatch.setattr("src.python.fetcher.fund_fee.fetch_fee_index", _boom)

        panel = wcp.build_whatif_cost_panel(
            {"changes": [_sell_leg("005827", "易方达蓝筹精选混合")]},
            snapshots=[],
            count_trading_days=lambda start, end: 5,
        )

        assert panel["trade_cost"]["fees_complete"] is False, "费率取不到时不得冒充费率全知"
        assert panel["trade_cost"]["unknown_legs"] >= 1

    def test_no_fund_leg_and_no_injection_keeps_fee_index_empty(self):
        panel = wcp.build_whatif_cost_panel(
            {"changes": [_sell_leg("600519", "贵州茅台")]},
            snapshots=[],
            count_trading_days=lambda start, end: 5,
        )

        assert panel["trade_cost"]["unmodeled_legs"] == 1


class TestResolveBenchmarkDefaults:
    """基准解析的各来源缺省注入。"""

    def test_config_and_getters_fallback_resolve_benchmark(self, monkeypatch):
        monkeypatch.setattr(
            "src.python.config.get_config",
            lambda: {"comparison_indices": {"sh000300": "沪深300"}, "whatif_benchmark_index": ""},
        )
        monkeypatch.setattr("src.python.fetcher.fund.fetch_fund_benchmark", lambda code: "沪深300指数")
        monkeypatch.setattr(
            "src.python.fetcher.index.fetch_index_history",
            lambda code, days: _bars([("2026-03-02", 10.0), ("2026-03-03", 11.0)]),
        )

        resolved = wcp._resolve_benchmark(
            changes=[{"code": "005827", "name": "易方达蓝筹精选混合", "cand_cost": 1000.0}],
            effective_date="2026-03-02",
            labels=["2026-03-02", "2026-03-03"],
            benchmark_override=None,
            comparison_indices=None,
            benchmark_text_getter=None,
            index_history_getter=None,
        )

        assert resolved is not None
        assert resolved["code"] == "sh000300"
        assert resolved["source"] == "holdings", "持仓基准文本仍未命中宽基池时须回落默认级"
        assert resolved["status"] == "ok"
        assert resolved["values"] == [100.0, 110.0]

    def test_no_modelled_holding_falls_back_to_default_index(self):
        resolved = wcp._resolve_benchmark(
            changes=[{"code": "005827", "name": "易方达蓝筹精选混合", "cand_cost": 0}],
            effective_date=None,
            labels=["2026-03-02"],
            benchmark_override="",
            comparison_indices={},
            benchmark_text_getter=lambda code: "沪深300",
            index_history_getter=lambda code, days: None,
        )

        assert resolved is not None
        assert resolved["source"] == "default"
        assert resolved["status"] == "unavailable"
        assert resolved["values"] is None
