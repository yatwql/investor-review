"""风格因子回归的降级/边界分支单元测试。

本文件锁定三类契约：
  - 停更剔除的边界输入（空映射、空 K 线、非法参考日）；
  - 系列对齐的否弃（组合序列缺列、因子全空、无可用因子帧）与基准 left join；
  - 回归前置下限（无可用因子、有效样本不足）与基准对照回归的启用条件。
"""

from __future__ import annotations

import numpy as np
import pytest

from src.python.analysis.style_factor_regression import (
    _align_series,
    _ols_regression,
    asif_portfolio_daily_returns,
    compute_factor_exposure,
    filter_stale_factor_klines,
    klines_to_returns,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis, pytest.mark.usefixtures("offline_external_sources")]


def _returns(n: int, scale: float = 0.01) -> list[dict]:
    """n 期等比日收益（升序日期），用于对齐/回归边界。"""
    return [{"date": f"2026-01-{i + 1:02d}", "return": scale * ((i % 5) - 2)} for i in range(n)]


class TestAsifRejection:
    """as-if 序列的空输入：无份额/无 K 线/无有效价格均不产出收益。"""

    def test_holdings_without_shares_or_bars_dropped(self):
        out = asif_portfolio_daily_returns(
            {
                "A": {"shares": 0.0, "bars": [{"date": "2026-01-01", "close": 10.0}]},
                "B": {"shares": 100.0, "bars": []},
            }
        )

        assert out == []

    def test_all_prices_invalid_returns_empty(self):
        out = asif_portfolio_daily_returns(
            {
                "A": {
                    "shares": 100.0,
                    "bars": [{"date": "2026-01-01", "close": 0.0}, {"date": "2026-01-02", "nav": -1.0}],
                }
            }
        )

        assert out == [], "无有效价格即无可计算样本"


class TestKlinesInvalidDay:
    """K 线无效日不产出收益，但上次有效值继续参与链式计算。"""

    def test_non_positive_close_skipped_without_breaking_chain(self):
        bars = [
            {"date": "2026-01-01", "close": 10.0},
            {"date": "2026-01-02", "close": 0.0},
            {"date": "2026-01-05", "close": 11.0},
        ]

        out = klines_to_returns(bars)

        assert [r["date"] for r in out] == ["2026-01-05"], "无效日不产出收益"
        assert out[0]["return"] == pytest.approx(0.1), "无效日不打断链路：仍以 10.0 为前值"


class TestStaleFilterBoundaries:
    """停更剔除的边界输入：空映射 / 空 K 线 / 非法参考日。"""

    def test_empty_mapping_returns_empty_pair(self):
        assert filter_stale_factor_klines({}, "2026-01-05") == ({}, [])

    def test_factor_without_bars_is_stale(self):
        fresh, stale = filter_stale_factor_klines(
            {"value": [], "growth": [{"date": "2026-01-05", "close": 1.0}]}, "2026-01-05"
        )

        assert stale == ["value"], "无末根 K 线即无新鲜度证据，按停更剔除"
        assert list(fresh) == ["growth"]

    def test_invalid_reference_date_falls_back_to_now(self, monkeypatch):
        """参考日非法时退化为当前时间，仍能判定新鲜度而不抛异常。"""
        import pandas as pd

        monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls: pd.Timestamp("2026-01-06")))
        fresh, stale = filter_stale_factor_klines({"value": [{"date": "2026-01-05", "close": 1.0}]}, "非日期")

        assert stale == [] and list(fresh) == ["value"]


class TestOlsPrerequisite:
    """OLS 的样本/秩前置：不足即返回 None 系数，绝不硬算。"""

    def test_samples_not_exceeding_params_returns_none(self):
        x = np.column_stack([np.ones(2), np.array([0.1, 0.2]), np.array([0.3, 0.4])])
        y = np.array([0.1, 0.2])

        out = _ols_regression(y, x)

        assert out["beta"] is None and out["t_stats"] is None
        assert out["df"] == 2 - 3

    def test_singular_matrix_zeroes_t_stats(self, monkeypatch):
        """伪逆失败时标准误置 NaN（不抛异常），t 值随之归零。"""

        def _raise(_mat):
            raise np.linalg.LinAlgError("奇异矩阵")

        monkeypatch.setattr(np.linalg, "pinv", _raise)
        x = np.column_stack([np.ones(6), np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])])
        y = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])

        out = _ols_regression(y, x)

        assert out["t_stats"] == [0.0, 0.0], "标准误不可解时 t 值须归零而非虚构数值"


class TestAlignSeriesRejection:
    """对齐序列的否弃路径：不可对齐即返回空 DataFrame。"""

    def test_empty_portfolio_returns_empty_frame(self):
        assert _align_series([], {"value": _returns(3)}, None).empty

    def test_portfolio_missing_return_column_returns_empty(self):
        assert _align_series([{"date": "2026-01-01"}], {"value": _returns(3)}, None).empty

    def test_all_factors_empty_returns_empty_frame(self):
        assert _align_series(_returns(3), {"value": []}, None).empty

    def test_baseline_joined_on_the_left(self):
        """基准以 left join 并入：基准缺日不丢样本，缺处留 NaN。"""
        factor = [{"date": "2026-01-01", "return": 0.01}, {"date": "2026-01-02", "return": 0.02}]
        baseline = [{"date": "2026-01-01", "return": 0.03}]

        df = _align_series(_returns(2), {"value": factor}, baseline)

        assert list(df.columns) == ["value", "portfolio", "baseline"]
        assert len(df) == 2, "基准缺日不缩小对齐结果"
        assert df["baseline"].isna().sum() == 1


class TestComputeFactorExposurePrerequisites:
    """主入口前置下限：无可用因子 / 有效样本不足都降级为 available=False。"""

    def test_no_active_factor_reports_insufficient(self):
        out = compute_factor_exposure(_returns(40), {"value": []})

        assert out["available"] is False and out["status"] == "insufficient"
        assert out["sample_count"] == 0

    def test_sample_below_minimum_reports_actual_count(self):
        factor = [{"date": r["date"], "return": 0.01} for r in _returns(5)]

        out = compute_factor_exposure(_returns(5), {"value": factor}, min_samples=36)

        assert out["available"] is False
        assert out["sample_count"] == 5, "数据不足时须回显真实有效期数"

    def test_rank_deficient_design_reports_insufficient(self):
        """样本未超过待估参数个数时不能硬算 β，降级为 insufficient。"""
        port = _returns(2)
        factors = {
            name: [{"date": r["date"], "return": 0.01 * (i + 1)} for i, r in enumerate(port)]
            for name in ("value", "growth", "quality")
        }

        out = compute_factor_exposure(port, factors, min_samples=1)

        assert out["available"] is False and out["status"] == "insufficient"
        assert out["sample_count"] == 2

    def test_baseline_regression_runs_when_enough_baseline_samples(self):
        """基准样本达下限时执行对照回归，输出 baseline_betas。"""
        port = _returns(12)
        factor = [{"date": r["date"], "return": 0.02 * ((i % 4) - 1)} for i, r in enumerate(port)]
        baseline = [{"date": r["date"], "return": 0.01 * ((i % 3) - 1)} for i, r in enumerate(port)]

        out = compute_factor_exposure(port, {"value": factor}, baseline, window=12, min_samples=6)

        assert out["available"] is True
        assert list(out["baseline_betas"]) == ["value"], "基准同窗口对照回归须产出逐因子 β"
