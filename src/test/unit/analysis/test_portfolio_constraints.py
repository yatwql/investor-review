"""集中度/相关性约束判定单元测试。

覆盖：开关关闭零行为（enabled=False）、单品种上限沿用 rebalance.threshold 且给出超限代码、
行业上限未配置/已配置缺数据两态、相关性样本期门槛「未评估」、已配置且窗口达标的正判与超限、
缺持仓市值时块不可用、阈值来源单一（profile 预设生效）。全部离线。
"""

from __future__ import annotations

import pytest

from src.python.analysis import portfolio_constraints as pc
from src.python.config.features import reset_feature_flags, set_feature_enabled

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis]


@pytest.fixture(autouse=True)
def _reset_features():
    reset_feature_flags()
    yield
    reset_feature_flags()


def _holdings(*pairs: tuple[str, float]) -> list[dict]:
    return [{"name": f"品种{code}", "code": code, "market_value": mv} for code, mv in pairs]


def _enable() -> None:
    set_feature_enabled(pc.FEATURE_FLAG, True)


@pytest.mark.parametrize("enabled", [False, True])
def test_flag_gate(enabled):
    """开关关闭 → 仅 enabled=False（调用方据此不渲染、不标注）。"""
    if enabled:
        _enable()
    out = pc.evaluate_constraints(_holdings(("000001", 600.0)), 1000.0, config={})
    assert out["enabled"] is enabled
    if not enabled:
        assert set(out) == {"enabled"}


def test_single_weight_uses_rebalance_threshold_and_lists_breached_codes():
    """单品种上限沿用 rebalance.threshold（默认 15%），超限品种列入 breached_codes。"""
    _enable()
    out = pc.evaluate_constraints(
        _holdings(("000001", 600.0), ("000002", 300.0), ("000003", 50.0)),
        1000.0,
        config={"rebalance": {"threshold": 0.15}},
    )
    single = out["items"][0]
    assert single["item"] == pc.ITEM_SINGLE
    assert single["limit_pct"] == pytest.approx(15.0)
    assert single["current_pct"] == pytest.approx(60.0)
    assert single["breached"] is True
    assert single["status_label"] == "超限"
    assert out["breached_codes"] == ["000001", "000002"]
    assert out["breached_count"] == 1


def test_single_weight_profile_preset_applies():
    """阈值来源单一：profile 预设（aggressive 25%）经 resolve_rebalance_config 生效。"""
    _enable()
    out = pc.evaluate_constraints(
        _holdings(("000001", 200.0), ("000002", 200.0), ("000003", 200.0), ("000004", 200.0), ("000005", 200.0)),
        1000.0,
        config={"rebalance": {"profile": "aggressive"}},
    )
    assert out["items"][0]["limit_pct"] == pytest.approx(25.0)
    assert out["items"][0]["breached"] is False


def test_industry_unconfigured_vs_configured_without_data():
    """行业上限：未配置 → 「未配置上限」；已配置但缺分类数据 → 「未评估」（都不拦截）。"""
    _enable()
    unconfigured = pc.evaluate_constraints(_holdings(("000001", 100.0)), 1000.0, config={})
    industry = unconfigured["items"][1]
    assert industry["limit_pct"] is None
    assert industry["limit_label"] == pc.UNCONFIGURED
    assert industry["breached"] is False

    configured = pc.evaluate_constraints(
        _holdings(("000001", 100.0)),
        1000.0,
        config={"constraints": {"industry_max_pct": 30.0}},
    )
    industry_cfg = configured["items"][1]
    assert industry_cfg["limit_pct"] == pytest.approx(30.0)
    assert industry_cfg["current_pct"] is None
    assert industry_cfg["status_label"] == "未评估"


def test_industry_configured_with_shares_breaches():
    _enable()
    out = pc.evaluate_constraints(
        _holdings(("000001", 100.0)),
        1000.0,
        config={"constraints": {"industry_max_pct": 30.0}},
        industry_shares={"半导体": 42.0, "银行": 20.0},
    )
    industry = out["items"][1]
    assert industry["current_pct"] == pytest.approx(42.0)
    assert industry["breached"] is True
    assert "半导体" in industry["note"]


def test_correlation_requires_configured_and_enough_window():
    """相关性：未配置不启用；样本期不足门槛 → 未评估不拦截；达标才判。"""
    _enable()
    base = {"constraints": {"correlation_max": 0.8, "correlation_min_window_days": 250}}
    unconfigured = pc.evaluate_constraints(_holdings(("000001", 100.0)), 1000.0, config={})
    assert unconfigured["items"][2]["limit_label"] == pc.UNCONFIGURED

    short = pc.evaluate_constraints(
        _holdings(("000001", 100.0)), 1000.0, config=base, correlation_value=0.9, correlation_window_days=90
    )
    corr = short["items"][2]
    assert corr["current_pct"] is None
    assert corr["breached"] is False
    assert corr["status_label"] == "未评估"

    long = pc.evaluate_constraints(
        _holdings(("000001", 100.0)), 1000.0, config=base, correlation_value=0.9, correlation_window_days=300
    )
    assert long["items"][2]["current_pct"] == pytest.approx(0.9)
    assert long["items"][2]["breached"] is True


def test_unavailable_without_holdings_or_market_value():
    _enable()
    assert pc.evaluate_constraints(None, 0)["available"] is False
    assert pc.evaluate_constraints(_holdings(("000001", 100.0)), 0)["reason"] == "缺少持仓市值"


def test_status_of_labels():
    assert pc.status_of(15.0, 60.0, True)[0] == "超限"
    assert pc.status_of(None, None, False)[0] == "未配置"
    assert pc.status_of(30.0, None, False)[0] == "未评估"
    assert pc.status_of(30.0, 10.0, False)[0] == "正常"
