"""图表数据集构建的降级分支契约测试。

锁住的契约：
  - 单图构建抛异常时只跳过该图（drawdown / category_doughnut 缺席），
    radar 失败回落空占位数据集
  - 基准指数无 K 线 / K 线无 value 时不产出数据集
  - 基准回撤跳过缺 value 的 bar；全部缺 value 时不产出数据集
  - 相关性滚动图在无可对齐序列 / 公共起点不足 2 点时返回空字典

运行：
  .venv/bin/python -m pytest src/test/unit/report/test_chart_data_builder_branches.py -v
"""

from __future__ import annotations

import pytest

from src.python.report import chart_data_builder as cdb

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


def _history() -> dict:
    return {
        "status": "ok",
        "bars": [
            {"date": "2026-01-05", "value": 100.0, "total_value": 100000.0},
            {"date": "2026-01-06", "value": 102.0, "total_value": 102000.0},
        ],
    }


class TestBuildChartDatasetsDegrade:
    """单图失败只跳过该图，不影响其余数据集。"""

    def test_drawdown_failure_only_skips_that_chart(self, monkeypatch):
        def _boom(_history_data):
            raise RuntimeError("drawdown boom")

        monkeypatch.setattr(cdb, "_build_drawdown_dataset", _boom)

        datasets = cdb.build_chart_datasets(history_data=_history(), details=None)

        assert "drawdown" not in datasets
        assert datasets["portfolio_line"]["labels"] == ["2026-01-05", "2026-01-06"]

    def test_category_failure_only_skips_that_chart(self, monkeypatch):
        def _boom(_details, _cat=None):
            raise RuntimeError("category boom")

        monkeypatch.setattr(cdb, "_build_category_doughnut_dataset", _boom)

        datasets = cdb.build_chart_datasets(history_data=_history(), details=None)

        assert "category_doughnut" not in datasets
        assert "radar" in datasets

    def test_radar_failure_falls_back_to_empty_dataset(self, monkeypatch):
        def _boom(*_args, **_kwargs):
            raise RuntimeError("radar boom")

        monkeypatch.setattr(cdb, "_build_radar_dataset", _boom)

        datasets = cdb.build_chart_datasets(history_data=_history(), all_metrics={"sharpe_ratio": 1.2})

        assert datasets["radar"] == cdb._empty_dataset()


class TestBenchmarkDatasets:
    """基准数据集对残缺输入的取舍。"""

    def test_benchmark_without_bars_is_dropped(self):
        assert cdb._build_benchmark_datasets([{"name": "沪深300"}]) == []

    def test_benchmark_bars_without_value_are_dropped(self):
        assert cdb._build_benchmark_datasets([{"name": "沪深300", "bars": [{"date": "2026-01-05"}]}]) == []

    def test_benchmark_drawdown_without_bars_is_dropped(self):
        assert cdb._build_benchmark_drawdowns([{"name": "沪深300"}]) == []

    def test_benchmark_drawdown_skips_missing_values(self):
        result = cdb._build_benchmark_drawdowns(
            [
                {
                    "name": "沪深300",
                    "bars": [{"value": None}, {"value": 100.0}, {"value": 90.0}],
                }
            ]
        )

        assert len(result) == 1
        assert result[0]["data"] == [pytest.approx(0.0), pytest.approx(-10.0)]

    def test_benchmark_drawdown_all_missing_values_is_dropped(self):
        assert cdb._build_benchmark_drawdowns([{"name": "沪深300", "bars": [{"value": None}]}]) == []


class TestRadarDataset:
    """Radar 数据集的空输入占位。"""

    def test_all_metric_sources_empty_yields_empty_dataset(self):
        assert cdb._build_radar_dataset(None, None, None) == cdb._empty_dataset()


class TestCorrRollingDataset:
    """持仓重合度滚动图的入图门槛。"""

    def test_base_axis_below_two_points_yields_empty(self):
        assert cdb._build_corr_rolling_dataset({"rolling": {"portfolio": {"60": []}}}) == {}

    def test_focus_pair_starting_off_axis_is_dropped(self):
        data = {
            "rolling": {
                "portfolio": {
                    "60": [
                        {"date": "2026-01-05", "value": 0.1},
                        {"date": "2026-01-06", "value": 0.2},
                    ]
                },
                "focus_pairs": [
                    {
                        "name_a": "甲",
                        "name_b": "乙",
                        "series": {"60": [{"date": "2026-02-01", "value": 0.9}]},
                    }
                ],
            }
        }

        chart = cdb._build_corr_rolling_dataset(data)

        assert chart["labels"] == ["2026-01-05", "2026-01-06"]
        assert [ds["label"] for ds in chart["datasets"]] == ["组合平均 60日"]
