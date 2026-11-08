"""编排层在纯计算层依赖缺失时的降级边界（不阻塞主报告）。

本文件锁定契约：编排层的计算层导入必须落在 `try` **之内**——`ImportError` 若冒泡到
`generate_report`，整份 full 报告即失败。契约：须返回 available=False +
status=source_failed（§1.4.5 数据降级治理），章节显示占位而非中断生成。
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import cast

import pytest

from src.python.analysis.unavailable_contracts import factor_unavailable_result, industry_unavailable_result
from src.python.report import _report_factor_metrics as rfm
from src.python.report.progress import ProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report, pytest.mark.edge]

_FACTOR_KEYS = {
    "available",
    "status",
    "betas",
    "t_stats",
    "significant",
    "style_allocation",
    "baseline_betas",
    "factor_correlations",
    "correlation_note",
    "alpha",
    "window",
    "sample_count",
    "stale_factors",
}

_INDUSTRY_KEYS = {
    "available",
    "status",
    "exposure",
    "betas",
    "alphas",
    "t_stats",
    "significant",
    "correlations",
    "unmapped_industries",
    "window",
    "sample_count",
}


class _Reporter:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def info(self, msg: str, *a, **k) -> None:  # noqa: ARG002 —— 接口对齐
        pass

    def ok(self, msg: str, *a, **k) -> None:  # noqa: ARG002 —— 接口对齐
        pass

    def warn(self, msg: str, *a, **k) -> None:
        self.warnings.append(msg)


def _holding(code: str, name: str = "标的") -> SimpleNamespace:
    return SimpleNamespace(code=code, name=name, shares=100.0)


class TestCalcLayerMissingDependency:
    def test_factor_block_degrades_when_calc_module_unimportable(self, monkeypatch):
        """计算层模块不可导入 → 因子区块降级（available=False），不抛异常。"""
        monkeypatch.setattr("src.python.config.is_enable_fund_deep_analysis", lambda config: True)
        monkeypatch.setitem(sys.modules, "src.python.analysis.style_factor_regression", None)
        reporter = _Reporter()

        result = rfm.compute_factor_exposure_data(
            [_holding("600900", "长江电力")], {}, cast(ProgressReporter, reporter)
        )

        assert result is not None
        assert set(result) == _FACTOR_KEYS
        assert result["available"] is False
        assert result["status"] == "source_failed"
        assert reporter.warnings, "降级必须向用户可见（reporter.warn）"
        assert result == factor_unavailable_result("source_failed"), "降级契约须与共享工厂逐键一致"

    def test_industry_beta_degrades_when_calc_module_unimportable(self, monkeypatch):
        """行业 Beta 计算层不可导入 → 子表降级，不阻塞主报告。"""
        monkeypatch.setattr("src.python.config.is_enable_fund_deep_analysis", lambda config: True)
        monkeypatch.setattr("src.python.config.is_enable_industry_beta", lambda: True)
        monkeypatch.setitem(sys.modules, "src.python.analysis.industry_beta", None)
        reporter = _Reporter()

        result = rfm.compute_industry_beta_data(
            [_holding("600900", "长江电力")],
            [SimpleNamespace(code="600900", name="长江电力", market_value=1000.0)],
            {},
            cast(ProgressReporter, reporter),
        )

        assert result is not None
        assert set(result) == _INDUSTRY_KEYS
        assert result["available"] is False
        assert result["status"] == "source_failed"
        assert reporter.warnings, "降级必须向用户可见（reporter.warn）"
        assert result == industry_unavailable_result("source_failed"), "降级契约须与共享工厂逐键一致"
