"""指纹组件级哈希（`fingerprint_components`）——连续报告缓存未命中的排障能力回归。

用途：连续两次同数据报告仍 miss 时，对比两次组件哈希即可定位「到底哪一块变了」，
不必再凭猜测调整指纹输入。
"""

from __future__ import annotations

import pytest

from src.python.llm.module_fingerprint import ModuleFingerprintInputs, fingerprint_components

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


def _inputs(**overrides) -> ModuleFingerprintInputs:
    base = {
        "total_mv": 100.0,
        "total_cost": 90.0,
        "total_profit": 10.0,
        "total_today_profit": 1.0,
        "holdings_details": [{"name": "长江电力", "code": "600900", "cost": 90.0}],
        "penetrated_assets": [{"name": "长江电力", "codes": ["600900"]}],
        "categories": {"equity": 1.0},
        "competitive_context": "组合 +1.00% vs 沪深300 +0.50%",
        "metrics": {"sharpe_ratio": 1.2},
        "data_quality_text": "数据源全部正常",
    }
    base.update(overrides)
    return ModuleFingerprintInputs(**base)


def test_returns_all_component_hashes():
    components = fingerprint_components(_inputs())
    for key in (
        "totals",
        "holdings",
        "penetration",
        "categories",
        "history_risk",
        "competitive_context",
        "metrics",
        "data_quality",
        "pipeline_blocks",
        "ledger_blocks",
        "generation_params",
    ):
        assert key in components
        assert components[key]


def test_stable_inputs_produce_stable_hashes():
    assert fingerprint_components(_inputs()) == fingerprint_components(_inputs())


@pytest.mark.parametrize(
    ("override", "changed_component"),
    [
        ({"total_today_profit": 2.0}, "totals"),
        ({"competitive_context": "组合 -1.00% vs 沪深300 -0.50%"}, "competitive_context"),
        ({"metrics": {"sharpe_ratio": 0.3}}, "metrics"),
        ({"data_quality_text": "行业资金流向不可用"}, "data_quality"),
    ],
)
def test_changed_input_changes_only_its_component(override, changed_component):
    base = fingerprint_components(_inputs())
    after = fingerprint_components(_inputs(**override))
    changed = {key for key in base if base[key] != after[key]}
    assert changed_component in changed
    assert changed == {changed_component}, f"非预期组件变化: {changed - {changed_component}}"


class TestDiffFingerprintComponents:
    """连续报告排障：只报真实变化的组件。"""

    def test_no_previous_returns_empty(self):
        from src.python.llm.module_fingerprint import diff_fingerprint_components

        assert diff_fingerprint_components(None, {"a": "1"}) == []
        assert diff_fingerprint_components({}, {"a": "1"}) == []

    def test_reports_only_changed_keys(self):
        from src.python.llm.module_fingerprint import diff_fingerprint_components

        previous = {"totals": "1", "metrics": "2"}
        current = {"totals": "1", "metrics": "3"}
        assert diff_fingerprint_components(previous, current) == ["metrics"]
