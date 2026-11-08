"""不可用结果（``available=False``）契约工厂 —— 纯数据装配，无第三方依赖。

为什么要独立成一个模块：编排层在两个场景都需要同一份空契约——
① 计算层正常返回「数据不足 / 数据源故障」；② 计算层**导入本身失败**（pandas/numpy
缺失）。后一种情况下编排层不能再 import 计算模块，若自己另写一份字面量键集，
两份定义会各自漂移（加一个契约键就漏一处）。故键集在此单源定义，
`analysis.style_factor_regression` / `analysis.industry_beta` 与
`report._report_factor_metrics` 都从这里取。

本模块只依赖 ``core.constants``（窗口默认值的唯一来源），不得引入 numpy/pandas ——
它就是「重依赖坏掉时仍须可用」的那一层。
"""

from __future__ import annotations

from src.python.core.constants import DEFAULT_WINDOW


def factor_unavailable_result(
    status: str,
    sample_count: int = 0,
    stale_factors: list[str] | None = None,
) -> dict:
    """风格因子回归区块的空数据契约（available=False）。

    Args:
        status: "insufficient"（数据不足）或 "source_failed"（数据源/依赖故障）。
        sample_count: 对齐后有效样本数（数据不足时为实际值）。
        stale_factors: 本次剔除的停更/不可用因子。

    Returns:
        含全部风格因子契约键的空结果字典。
    """
    return {
        "available": False,
        "status": status,
        "betas": {},
        "t_stats": {},
        "significant": {},
        "style_allocation": {},
        "baseline_betas": {},
        "factor_correlations": {},
        "correlation_note": "",
        "alpha": 0.0,
        "window": DEFAULT_WINDOW,
        "sample_count": sample_count,
        "stale_factors": stale_factors or [],
    }


def industry_unavailable_result(status: str, sample_count: int = 0) -> dict:
    """行业 Beta 子表的空数据契约（available=False）。

    Args:
        status: "insufficient"（数据不足）或 "source_failed"（数据源/依赖故障）。
        sample_count: 对齐后有效样本数（数据不足时为实际值）。

    Returns:
        含全部行业 Beta 契约键的空结果字典。
    """
    return {
        "available": False,
        "status": status,
        "exposure": {},
        "betas": {},
        "alphas": {},
        "t_stats": {},
        "significant": {},
        "correlations": {},
        "unmapped_industries": [],
        "window": DEFAULT_WINDOW,
        "sample_count": sample_count,
    }
