"""历史增强契约装配接线测试 — 开关判定 / 子块长窗取数 / full 路径注入 / 取数 helper。

覆盖：
  - assemble_history_augmented_data 开关全关：仅写 crisis 关态契约、零长窗取数
  - 开关开启：子块长窗取数触发、回放态契约（replay=True + 指数层）、risk 键写入、
    两开关共享同一次长窗取数
  - full 路径（_prepare_full_risk_metrics）端到端注入 risk_adjusted_excess_data
  - _snapshot 取数 helper：长窗窗口参数、基准未配置降级、危机指数天数动态推算

设计约束：全部外部依赖 patch（Calculator / fetch_benchmarks / 开关读取），无网络。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.python.report._snapshot import (
    _crisis_index_days,
    assemble_history_augmented_data,
    fetch_crisis_index_series,
    fetch_extended_history,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]
pytestmark.append(pytest.mark.usefixtures("offline_external_sources"))


def _history(status: str = "ok") -> dict:
    """最小 history_data 契约（装配层仅判 status/bars）。"""
    return {
        "status": status,
        "bars": [{"date": "2026-01-01", "total_value": 100.0}],
        "daily_returns": [],
    }


def _run_assemble(flags: dict[str, bool], history, pipeline: dict | None = None) -> tuple:
    """在开关 patch 下调用装配函数，返回 (pipeline, fetch_extended, fetch_index)。"""
    pipeline = {} if pipeline is None else pipeline

    def _flag(name: str) -> bool:
        return bool(flags.get(name))

    with (
        patch("src.python.config.features.is_feature_enabled", side_effect=_flag),
        patch("src.python.report._snapshot.fetch_extended_history", return_value=None) as fetch_extended,
        patch("src.python.report._snapshot.fetch_crisis_index_series") as fetch_index,
        patch("src.python.analysis.crisis_annotation.build_crisis_annotation") as build_crisis,
    ):
        assemble_history_augmented_data(
            [MagicMock(code="SH600001", name="测试", shares=100.0)],
            {},
            MagicMock(),
            history,
            pipeline,
        )
    return pipeline, fetch_extended, fetch_index, build_crisis


class TestAssembleHistoryAugmented:
    """共享装配函数的开关行为。"""

    def test_off_by_default_writes_off_state_crisis_only(self):
        """开关全关（默认）→ crisis 关态契约写入、risk 键缺席、零新增取数。"""
        pipeline, fetch_extended, fetch_index, build_crisis = _run_assemble({}, _history())
        assert "crisis_annotation_data" in pipeline
        assert "risk_adjusted_excess_data" not in pipeline
        fetch_extended.assert_not_called()
        fetch_index.assert_not_called()
        # 关态调用：无 replay / index 参数（默认值语义）
        assert build_crisis.call_args.kwargs.get("replay", False) is False
        assert build_crisis.call_args.kwargs.get("index_series") is None

    def test_excess_on_fetches_extended_and_writes_contract(self):
        """风险调整超额开 → 子块长窗取数触发一次 + risk 键写入（crisis 仍关态）。"""
        pipeline, fetch_extended, fetch_index, build_crisis = _run_assemble({"risk_adjusted_excess": True}, _history())
        fetch_extended.assert_called_once()
        fetch_index.assert_not_called()
        assert "risk_adjusted_excess_data" in pipeline  # 输入不足 → available=False 降级契约
        assert pipeline["risk_adjusted_excess_data"]["available"] is False
        assert build_crisis.call_args.kwargs.get("replay", False) is False

    def test_replay_on_builds_replay_contract_with_index(self):
        """危机回放开 → 长窗取数 + 指数取数 + replay=True 传入契约构建。"""
        sentinel = {"available": True, "intervals": [], "replay": True}
        with (
            patch("src.python.config.features.is_feature_enabled", side_effect=lambda n: n == "crisis_replay"),
            patch("src.python.report._snapshot.fetch_extended_history") as fetch_extended,
            patch("src.python.report._snapshot.fetch_crisis_index_series", return_value={"bars": []}) as fetch_index,
            patch(
                "src.python.analysis.crisis_annotation.build_crisis_annotation",
                return_value=sentinel,
            ) as build_crisis,
        ):
            pipeline: dict = {}
            assemble_history_augmented_data(
                [MagicMock(code="SH600001", name="测试", shares=100.0)],
                {},
                MagicMock(),
                _history(),
                pipeline,
            )
        fetch_extended.assert_called_once()
        fetch_index.assert_called_once()
        assert pipeline["crisis_annotation_data"] is sentinel
        assert build_crisis.call_args.kwargs["replay"] is True
        assert build_crisis.call_args.kwargs["index_series"] == {"bars": []}
        assert "risk_adjusted_excess_data" not in pipeline

    def test_both_switches_share_single_extended_fetch(self):
        """两开关同开 → 长窗取数只发生一次（共享），两契约均构建。"""
        pipeline, fetch_extended, _fetch_index, build_crisis = _run_assemble(
            {"risk_adjusted_excess": True, "crisis_replay": True},
            _history(),
        )
        fetch_extended.assert_called_once()
        assert build_crisis.call_args.kwargs.get("replay") is True
        assert "risk_adjusted_excess_data" in pipeline

    def test_pipeline_none_is_noop(self):
        """pipeline_data=None → 跳过装配、不触发取数、不触发契约构建。"""
        with (
            patch("src.python.config.features.is_feature_enabled", return_value=True),
            patch("src.python.report._snapshot.fetch_extended_history") as fetch_extended,
            patch("src.python.analysis.crisis_annotation.build_crisis_annotation") as build_crisis,
        ):
            assemble_history_augmented_data([MagicMock(code="SH600001")], {}, MagicMock(), _history(), None)
        fetch_extended.assert_not_called()
        build_crisis.assert_not_called()

    def test_unavailable_history_skips_extended_fetch(self):
        """主历史不可用 → 不触发长窗取数；回放态契约退回关态占位（无 replay 键）。"""
        with (
            patch("src.python.config.features.is_feature_enabled", return_value=True),
            patch("src.python.report._snapshot.fetch_extended_history") as fetch_extended,
            patch("src.python.analysis.crisis_annotation.build_crisis_annotation") as build_crisis,
        ):
            pipeline: dict = {}
            assemble_history_augmented_data(
                [MagicMock(code="SH600001")], {}, MagicMock(), _history("unavailable"), pipeline
            )
        fetch_extended.assert_not_called()
        assert build_crisis.call_args.kwargs.get("replay") is True  # 回放开关开
        # extended 为 None → 传入主历史（unavailable）


class TestFullPathInjection:
    """full 路径（_prepare_full_risk_metrics）端到端注入。"""

    def test_full_path_injects_risk_key_when_on(self):
        """开关开 → full 路径 pipeline_data 同时含 crisis 与 risk 键。"""
        from src.python.report._full_risk_metrics import _prepare_full_risk_metrics

        pipeline: dict = {}
        with (
            patch(
                "src.python.report._snapshot.fetch_history_data",
                return_value=_history(),
            ),
            patch(
                "src.python.config.features.is_feature_enabled",
                side_effect=lambda n: n == "risk_adjusted_excess",
            ),
            patch("src.python.report._snapshot.fetch_extended_history", return_value=None),
        ):
            history, _metrics = _prepare_full_risk_metrics(
                [MagicMock(code="SH600001", name="测试", shares=100.0)],
                config={},
                reporter=MagicMock(),
                perf=MagicMock(),
                fetch_history=True,
                enable_history=True,
                prep={},
                pipeline_data=pipeline,
            )
        assert history is not None
        assert "risk_adjusted_excess_data" in pipeline
        assert "crisis_annotation_data" in pipeline

    def test_full_path_default_off_has_no_risk_key(self):
        """开关全关（默认）→ full 路径只写 crisis 关态契约。"""
        from src.python.report._full_risk_metrics import _prepare_full_risk_metrics

        pipeline: dict = {}
        with (
            patch(
                "src.python.report._snapshot.fetch_history_data",
                return_value=_history(),
            ),
            patch("src.python.config.features.is_feature_enabled", return_value=False),
        ):
            _prepare_full_risk_metrics(
                [MagicMock(code="SH600001", name="测试", shares=100.0)],
                config={},
                reporter=MagicMock(),
                perf=MagicMock(),
                fetch_history=True,
                enable_history=True,
                prep={},
                pipeline_data=pipeline,
            )
        assert "crisis_annotation_data" in pipeline
        assert "risk_adjusted_excess_data" not in pipeline


class TestSnapshotHelpers:
    """_snapshot 取数 helper。"""

    def test_crisis_index_days_covers_earliest_interval(self):
        """指数取数天数动态推算：覆盖最早危机区间至今（含缓冲）且不超源上限。"""
        from datetime import date

        from src.python.analysis.crisis_annotation import CRISIS_INTERVALS

        days = _crisis_index_days()
        earliest = min(date.fromisoformat(iv["start"]) for iv in CRISIS_INTERVALS)
        span_trading_days = int((date.today() - earliest).days * 252 / 365)
        assert span_trading_days <= days <= 3650

    def test_extended_history_empty_holdings_returns_none(self):
        assert fetch_extended_history([], {}, MagicMock()) is None

    def test_extended_history_uses_source_cap_window(self):
        """lookback_days 默认 90 → 子块窗口取源上限 365（独立于主窗）。"""
        calc = MagicMock()
        calc.get_combined_timeseries.return_value = {"status": "ok", "bars": []}
        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator", return_value=calc):
            out = fetch_extended_history(
                [MagicMock(code="SH600001", name="测试", shares=100.0)],
                {"history": {"lookback_days": 90}},
                MagicMock(),
            )
        assert out is not None
        _args, kwargs = calc.get_combined_timeseries.call_args
        assert kwargs.get("days", _args[1] if len(_args) > 1 else None) == 365

    def test_extended_history_respects_longer_configured_window(self):
        """配置窗口更长（如 500）→ 子块窗口取 max(lookback, 365)。"""
        calc = MagicMock()
        calc.get_combined_timeseries.return_value = {"status": "ok", "bars": []}
        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator", return_value=calc):
            fetch_extended_history(
                [MagicMock(code="SH600001", name="测试", shares=100.0)],
                {"history": {"lookback_days": 500}},
                MagicMock(),
            )
        _args, kwargs = calc.get_combined_timeseries.call_args
        days = kwargs.get("days", _args[1] if len(_args) > 1 else None)
        assert days == 500

    def test_extended_history_unavailable_returns_none(self):
        calc = MagicMock()
        calc.get_combined_timeseries.return_value = {"status": "unavailable", "bars": []}
        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator", return_value=calc):
            out = fetch_extended_history(
                [MagicMock(code="SH600001", name="测试", shares=100.0)],
                {},
                MagicMock(),
            )
        assert out is None

    def test_crisis_index_series_unconfigured_returns_none(self):
        """未配置业绩基准 → None，且不触发指数取数。"""
        with patch("src.python.report.benchmark.fetch_benchmarks") as fetch_benchmarks:
            out = fetch_crisis_index_series({})
        assert out is None
        fetch_benchmarks.assert_not_called()

    def test_crisis_index_series_returns_primary_benchmark(self):
        """配置了基准 → 返回第一个基准的长窗日线（dict 含 name/bars）。"""
        raw = {"sh000300": {"name": "沪深300", "bars": [{"date": "2015-06-12", "close": 100.0}]}}
        with patch("src.python.report.benchmark.fetch_benchmarks", return_value=raw) as fetch_benchmarks:
            out = fetch_crisis_index_series({"history": {"benchmark_indices": {"sh000300": "沪深300"}}})
        assert out == raw["sh000300"]
        assert fetch_benchmarks.call_args.args[0] == {"sh000300": "沪深300"}
        # 取数天数按静态危机表最早起点推算（≥ 2015 起跨度）
        assert fetch_benchmarks.call_args.kwargs["days"] >= 2800

    def test_crisis_index_series_fetch_failure_returns_none(self):
        with patch("src.python.report.benchmark.fetch_benchmarks", side_effect=RuntimeError("boom")):
            out = fetch_crisis_index_series({"history": {"benchmark_indices": {"sh000300": "沪深300"}}})
        assert out is None


class TestLatestQuotesFromDetailRows:
    """明细行 → 终点回填用的 {code: (价格, 估值日)}（无估值日不入表）。"""

    def test_detail_row_objects(self):
        from types import SimpleNamespace

        from src.python.report._snapshot import latest_quotes_from_detail_rows

        rows = [
            SimpleNamespace(code="022365", price=3.9825, nav_date="2026-10-29"),
            SimpleNamespace(code="017730", price=0.0, nav_date="2026-10-28"),  # 无有效价格
            SimpleNamespace(code="600900", price=29.99, nav_date=""),  # 无估值日
        ]
        assert latest_quotes_from_detail_rows(rows) == {"022365": (3.9825, "2026-10-29")}

    def test_detail_dict_rows(self):
        from src.python.report._snapshot import latest_quotes_from_detail_rows

        rows = [
            {"code": "011506", "price": 1.336, "nav_date": "2026-10-29"},
            {"code": "096001", "price": "2.8109", "nav_date": "2026-10-28"},  # 字符串价格不采信
        ]
        assert latest_quotes_from_detail_rows(rows) == {"011506": (1.336, "2026-10-29")}

    def test_none_input(self):
        from src.python.report._snapshot import latest_quotes_from_detail_rows

        assert latest_quotes_from_detail_rows(None) == {}
