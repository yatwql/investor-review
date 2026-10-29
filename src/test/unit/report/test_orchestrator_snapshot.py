"""orchestrator 快照与历史走势单元测试 — capture_snapshot / fetch_history_data。

从 `test_orchestrator.py` 分出（按被测模块分片）：本文件只覆盖
`report/_snapshot.py` 两个入口，其余编排用例留在主分片。
"""

from __future__ import annotations

import pytest

from unittest.mock import MagicMock, patch

from src.python.report._snapshot import capture_snapshot, fetch_history_data

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.usefixtures("offline_external_sources")]


class TestCaptureSnapshot:
    """capture_snapshot 快照创建测试（8 用例覆盖 5 子步骤）。"""

    def _make_mock_detail(self, code="SH600001", name="测试", mv=1200.0, cost=1000.0, profit=200.0) -> MagicMock:
        d = MagicMock()
        d.code = code
        d.name = name
        d.market_value = mv
        d.cost = cost
        d.profit = profit
        d.profit_rate = profit / cost if cost else 0
        return d

    def _make_mock_holding(self, code="SH600001", name="测试", shares=100, cost_price=10.0) -> MagicMock:
        h = MagicMock()
        h.code = code
        h.name = name
        h.shares = shares
        h.cost_price = cost_price
        return h

    def test_capture_snapshot_holding_mapping(self):
        """从 details → SnapshotHolding 字段映射正确（份额/成本由持仓对象回填）。

        断言落在传给 save() 的快照对象上，而不是仅看返回值——
        首次运行返回值本就是 None，看不出字段映射是否正确。
        """
        mock_reporter = MagicMock()
        detail = self._make_mock_detail()
        config = {"history": {"snapshot_retention_days": 60, "snapshot_max_count": 365}}

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", return_value=None),
            patch("src.python.report.history_snapshot.save") as mock_save,
            patch("src.python.fetcher.history_diff.HistoryDiff") as mock_hd,
            patch("src.python.report.history_snapshot.prune"),
        ):
            mock_diff = MagicMock()
            mock_diff.is_first_check = True
            mock_hd.compute.return_value = mock_diff

            capture_snapshot(
                [self._make_mock_holding(code="SH600001", name="测试", shares=200, cost_price=12.0)],
                [detail],
                config,
                mock_reporter,
            )

        snapshot = mock_save.call_args.args[0]
        holding = snapshot.accounts[0].holdings[0]
        # 行情侧字段（来自 detail）
        assert holding.code == "SH600001"
        assert holding.market_value == 1200.0
        assert holding.total_pnl == 200.0
        assert holding.cost_total == 1000.0
        # 持仓侧字段（按 code 从 holdings 回填：detail 本身无份额/成本）
        assert holding.name == "测试"
        assert holding.shares == 200
        assert holding.cost_price == 12.0
        # 汇总字段与账户名
        assert snapshot.accounts[0].account_name == "全部"
        assert snapshot.total_value == 1200.0
        assert snapshot.total_cost == 1000.0
        assert snapshot.total_pnl == 200.0

    def test_capture_snapshot_holdings_lookup(self):
        """holdings 回查补充 shares/cost_price；无匹配时默认 0.0。"""
        mock_reporter = MagicMock()
        detail = self._make_mock_detail()
        config = {"history": {"snapshot_retention_days": 60, "snapshot_max_count": 365}}

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", return_value=None),
            patch("src.python.report.history_snapshot.save") as mock_save,
            patch("src.python.fetcher.history_diff.HistoryDiff") as mock_hd,
            patch("src.python.report.history_snapshot.prune"),
        ):
            mock_diff = MagicMock()
            mock_diff.is_first_check = True
            mock_hd.compute.return_value = mock_diff

            # 持仓列表不含 detail 的代码 → 走「无匹配」分支，份额/成本应回落默认值
            # （匹配分支的回填由 test_capture_snapshot_holding_mapping 覆盖）
            capture_snapshot(
                [self._make_mock_holding(code="SZ000001", shares=200, cost_price=12.0)],
                [detail],
                config,
                mock_reporter,
            )

        # 断言落在 save() 收到的快照对象上（只看 compute.called 无法证明默认值生效）
        holding = mock_save.call_args.args[0].accounts[0].holdings[0]
        assert holding.code == "SH600001"
        assert holding.shares == 0.0
        assert holding.cost_price == 0.0

    def test_capture_snapshot_data_creation(self):
        """SnapshotData 聚合计算正确（多明细求和 + 账户内持仓清单）。"""
        mock_reporter = MagicMock()
        details = [
            self._make_mock_detail(code="SH600001", mv=1200.0, cost=1000.0, profit=200.0),
            self._make_mock_detail(code="SH600002", mv=2400.0, cost=2000.0, profit=400.0),
        ]
        config = {"history": {"snapshot_retention_days": 60, "snapshot_max_count": 365}}

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", return_value=None),
            patch("src.python.report.history_snapshot.save") as mock_save,
            patch("src.python.fetcher.history_diff.HistoryDiff") as mock_hd,
            patch("src.python.report.history_snapshot.prune"),
        ):
            mock_diff = MagicMock()
            mock_diff.is_first_check = True
            mock_hd.compute.return_value = mock_diff

            capture_snapshot(
                [self._make_mock_holding(code="SH600001"), self._make_mock_holding(code="SH600002")],
                details,
                config,
                mock_reporter,
            )

        snapshot = mock_save.call_args.args[0]
        assert snapshot.accounts[0].account_name == "全部"
        assert [h.code for h in snapshot.accounts[0].holdings] == ["SH600001", "SH600002"]
        assert snapshot.total_value == 3600.0  # 1200 + 2400
        assert snapshot.total_cost == 3000.0  # 1000 + 2000
        assert snapshot.total_pnl == 600.0  # 200 + 400

    def test_capture_snapshot_diff_compute(self):
        """HistoryDiff.compute 被调用，diff 结果含四个子列表。"""
        mock_reporter = MagicMock()
        detail = self._make_mock_detail()
        details = [detail]
        config = {"history": {"snapshot_retention_days": 60, "snapshot_max_count": 365}}

        # 构造有 diff 数据的 mock
        mock_diff = MagicMock()
        mock_diff.is_first_check = False
        mock_diff.total_value_diff = 100.0
        mock_diff.total_value_diff_pct = 0.05
        mock_diff.total_pnl_diff = 50.0
        mock_diff.days_since_last_report = 1
        mock_diff.trimmed = False

        added_item = MagicMock()
        added_item.name = "新增股"
        added_item.code = "SH600003"
        added_item.action = "added"
        added_item.shares_diff = 100
        added_item.value_diff = 500.0
        mock_diff.added = [added_item]
        mock_diff.removed = []
        mock_diff.increased = []
        mock_diff.decreased = []

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", return_value=MagicMock()),
            patch("src.python.report.history_snapshot.save"),
            patch("src.python.fetcher.history_diff.HistoryDiff") as mock_hd_cls,
            patch("src.python.report.history_snapshot.prune"),
        ):
            mock_hd_cls.compute.return_value = mock_diff

            result = capture_snapshot(
                [self._make_mock_holding()],
                details,
                config,
                mock_reporter,
            )

        assert result is not None
        assert "diff" in result
        assert result["diff"]["is_first_check"] is False
        assert result["diff"]["total_value_diff"] == 100.0
        assert len(result["diff"]["added"]) == 1

    def test_capture_snapshot_prune_params(self):
        """prune 接收的 retention_days/max_count 来自 config 参数。"""
        mock_reporter = MagicMock()
        detail = self._make_mock_detail()
        config = {"history": {"snapshot_retention_days": 99, "snapshot_max_count": 200}}

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", return_value=None),
            patch("src.python.report.history_snapshot.save"),
            patch("src.python.fetcher.history_diff.HistoryDiff") as mock_hd,
            patch("src.python.report.history_snapshot.prune") as mock_prune,
        ):
            mock_diff = MagicMock()
            mock_diff.is_first_check = True
            mock_hd.compute.return_value = mock_diff

            capture_snapshot(
                [self._make_mock_holding()],
                [detail],
                config,
                mock_reporter,
            )

        # 验证 prune 参数来自 config 而非 get_config_cache()；默认 namespace=None（共享主目录）
        mock_prune.assert_called_once_with(retention_days=99, max_count=200, namespace=None)

    def test_capture_snapshot_pipeline_data(self):
        """pipeline_data 含 diff/diff_trimmed/days_since_last 三个顶层 key。"""
        mock_reporter = MagicMock()
        detail = self._make_mock_detail()
        config = {"history": {"snapshot_retention_days": 60, "snapshot_max_count": 365}}

        mock_diff = MagicMock()
        mock_diff.is_first_check = False
        mock_diff.total_value_diff = 0.0
        mock_diff.total_value_diff_pct = 0.0
        mock_diff.total_pnl_diff = 0.0
        mock_diff.days_since_last_report = 5
        mock_diff.trimmed = False
        mock_diff.added = []
        mock_diff.removed = []
        mock_diff.increased = []
        mock_diff.decreased = []

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", return_value=MagicMock()),
            patch("src.python.report.history_snapshot.save"),
            patch("src.python.fetcher.history_diff.HistoryDiff") as mock_hd_cls,
            patch("src.python.report.history_snapshot.prune"),
        ):
            mock_hd_cls.compute.return_value = mock_diff

            result = capture_snapshot(
                [self._make_mock_holding()],
                [detail],
                config,
                mock_reporter,
            )

        assert result is not None
        assert "diff" in result
        assert result["diff"]["days_since_last_report"] == 5

    def test_capture_snapshot_first_run(self):
        """首次运行（无旧快照）时返回 None。"""
        mock_reporter = MagicMock()
        detail = self._make_mock_detail()
        config = {"history": {"snapshot_retention_days": 60, "snapshot_max_count": 365}}

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", return_value=None),
            patch("src.python.report.history_snapshot.save"),
            patch("src.python.fetcher.history_diff.HistoryDiff") as mock_hd,
            patch("src.python.report.history_snapshot.prune"),
        ):
            mock_diff = MagicMock()
            mock_diff.is_first_check = True
            mock_hd.compute.return_value = mock_diff

            result = capture_snapshot(
                [self._make_mock_holding()],
                [detail],
                config,
                mock_reporter,
            )

        assert result is None

    def test_capture_snapshot_exception_safe(self):
        """异常时捕获到 logger，返回 None 不阻塞。"""
        mock_reporter = MagicMock()
        detail = self._make_mock_detail()
        config = {"history": {"snapshot_retention_days": 60, "snapshot_max_count": 365}}

        with (
            patch("src.python.report.history_snapshot.load_comparison_baseline", side_effect=ValueError("测试异常")),
            patch("src.python.report.history_snapshot.save"),
            patch("src.python.fetcher.history_diff.HistoryDiff"),
            patch("src.python.report.history_snapshot.prune"),
        ):
            result = capture_snapshot(
                [self._make_mock_holding()],
                [detail],
                config,
                mock_reporter,
            )

        assert result is None


@pytest.mark.unit
@pytest.mark.unit_report
class TestFetchHistoryData:
    """fetch_history_data 历史走势数据获取测试。"""

    def test_fetch_history_data_fetch_true(self):
        """fetch=True 返回 PortfolioHistoryCalculator 计算结果。"""
        mock_reporter = MagicMock()
        mock_holding = MagicMock()
        mock_holding.code = "SH600001"
        mock_holding.name = "测试"
        mock_holding.shares = 100

        mock_history_data = {
            "dates": ["2026-01-01", "2026-07-16"],
            "values": [1000.0, 1200.0],
            "status": "available",
        }

        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc.get_combined_timeseries.return_value = mock_history_data
            mock_cls.return_value = mock_calc

            result = fetch_history_data(
                [mock_holding],
                {"history": {"coverage_threshold": 0.9}},
                mock_reporter,
                fetch=True,
            )

        assert result is not None
        assert result["status"] == "available"
        assert len(result["dates"]) == 2
        mock_cls.assert_called_once_with(
            coverage_threshold=0.9,
            benchmark_indices={},
        )

    def test_fetch_history_data_fetch_false(self):
        """fetch=False 返回 None 并醒目提示 history 已关闭（回归守护）。

        防回退：history 关闭时必须通过 reporter.warn + logger 明确警示，
        不得静默跳过——否则下游只剩误导性的"尾部风险：无历史 bars"占位警告。
        """
        mock_reporter = MagicMock()

        result = fetch_history_data(
            [],
            {"history": {}},
            mock_reporter,
            fetch=False,
        )

        assert result is None
        mock_reporter.warn.assert_called_once()
        # 警示文案须点明 history 关闭与后果，避免与"无历史 bars"混淆
        warn_msg = mock_reporter.warn.call_args.args[0]
        assert "history off" in warn_msg
        assert "数据不可用" in warn_msg

    def test_fetch_history_data_unavailable(self):
        """status=unavailable 时返回数据但 reporter.warn 被调用。"""
        mock_reporter = MagicMock()
        mock_history_data = {"status": "unavailable"}

        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc.get_combined_timeseries.return_value = mock_history_data
            mock_cls.return_value = mock_calc

            result = fetch_history_data(
                [MagicMock()],
                {"history": {}},
                mock_reporter,
            )

        assert result is not None
        assert result["status"] == "unavailable"
        mock_reporter.warn.assert_called_once()

    def test_fetch_history_data_exception(self):
        """内部异常时返回 None 不阻塞。"""
        mock_reporter = MagicMock()

        with patch(
            "src.python.report.portfolio_history.PortfolioHistoryCalculator",
            side_effect=RuntimeError("测试异常"),
        ):
            result = fetch_history_data(
                [MagicMock()],
                {"history": {}},
                mock_reporter,
            )

        assert result is None

    def test_fetch_history_data_uses_lookback_days(self):
        """history.lookback_days 配置透传给 get_combined_timeseries 的 days 参数。

        回归防护：回撤分析需 ≥60 交易日（MIN_SPAN），若取数窗口未随配置放大，
        主报告回撤分析将一直判定数据不足。此处断言配置 → days 透传。
        """
        mock_reporter = MagicMock()
        mock_holding = MagicMock()
        mock_holding.code = "SH600001"
        mock_holding.name = "测试"
        mock_holding.shares = 100

        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc.get_combined_timeseries.return_value = {"status": "ok", "bars": []}
            mock_cls.return_value = mock_calc

            fetch_history_data(
                [mock_holding],
                {"history": {"lookback_days": 120}},
                mock_reporter,
                fetch=True,
            )

        mock_calc.get_combined_timeseries.assert_called_once_with(
            [("SH600001", "测试", 100)],
            latest_quotes=None,
            days=120,
        )

    def test_fetch_history_data_lookback_days_default_90(self):
        """未配置 lookback_days 时取数窗口默认 90。"""
        mock_reporter = MagicMock()
        mock_holding = MagicMock()
        mock_holding.code = "SH600001"
        mock_holding.name = "测试"
        mock_holding.shares = 100

        with patch("src.python.report.portfolio_history.PortfolioHistoryCalculator") as mock_cls:
            mock_calc = MagicMock()
            mock_calc.get_combined_timeseries.return_value = {"status": "ok", "bars": []}
            mock_cls.return_value = mock_calc

            fetch_history_data(
                [mock_holding],
                {"history": {}},
                mock_reporter,
                fetch=True,
            )

        mock_calc.get_combined_timeseries.assert_called_once_with(
            [("SH600001", "测试", 100)],
            latest_quotes=None,
            days=90,
        )
