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


class TestDataQualityBlockCountsOnlyFailures:
    """数据质量块只统计失败事件：成功取用不得被写成「连接失败」。"""

    def _events(self):
        return [
            {
                "source_key": "price_600900",
                "tier": "T2",
                "success": True,
                "failure_type": "ok",
                "degraded": False,
                "count": 0,
            },
            {
                "source_key": "ff_sector_flow",
                "tier": "T4",
                "success": False,
                "failure_type": "unreachable",
                "degraded": False,
                "count": 1,
            },
        ]

    def test_success_events_are_not_counted_as_failures(self):
        from src.python.llm.prompts_tables import _build_data_quality_detail_block

        text = _build_data_quality_detail_block(self._events())
        assert "连接失败: ff_sector_flow" in text
        assert "price_600900" not in text

    def test_block_stable_when_failure_multiplicity_differs(self):
        """同一源失败**事件条数**与累计次数不同 → 质量文本一致。

        条数由重试轮次/网络抖动决定（akshare 失败 1 次 vs 3 次），累计次数是跨
        会话计数——两者都与模型要判断的「哪些源本次不可用」无关，却每轮都变，
        若进文本会让 health_check 缓存键每份报告翻新。
        """
        from src.python.llm.prompts_tables import _build_data_quality_detail_block

        one = self._events()
        many = (
            one
            + [
                {
                    "source_key": "ff_sector_flow",
                    "tier": "T4",
                    "success": False,
                    "failure_type": "unreachable",
                    "degraded": False,
                    "count": 9,
                }
            ]
            * 3
        )
        assert _build_data_quality_detail_block(one) == _build_data_quality_detail_block(many)

    def test_block_stable_when_success_count_differs(self):
        """同一份失败集合 + 不同数量的成功取用 → 质量文本一致（缓存键不受缓存冷热影响）。"""
        from src.python.llm.prompts_tables import _build_data_quality_detail_block

        base = self._events()
        warm = base + [
            {"source_key": f"industry_{i}", "tier": "T3", "success": True, "failure_type": "ok", "degraded": False}
            for i in range(5)
        ]
        assert _build_data_quality_detail_block(base) == _build_data_quality_detail_block(warm)


class TestMarkDataUsedFailureType:
    """成功取用事件不得携带失败类型（否则下游按 failure_type 统计会误报）。"""

    def test_success_event_uses_neutral_failure_type(self, tmp_path, monkeypatch):
        from src.python.report import data_status as ds

        tracker = ds.DegradationTracker(persist_path=str(tmp_path / "degradation.json"))
        monkeypatch.setattr(ds, "get_tracker", lambda: tracker)
        ds.mark_data_used("price_600900", "T2")
        event = tracker.get_log()[-1]
        assert event["success"] is True
        assert event["failure_type"] == "ok"


class TestHistoryRiskComponentScope:
    """history_risk 组件只反映风险信号子集，不受 bars 等载荷变化影响。"""

    def test_bars_change_does_not_change_history_risk(self):
        base = {"max_drawdown_pct": -15.75, "annualized_volatility": 0.1751, "total_return_pct": -10.07}
        noisy = dict(base, bars=[{"date": "2026-10-24", "close": 1.0}])
        first = fingerprint_components(_inputs(history_data=base))
        second = fingerprint_components(_inputs(history_data=noisy))
        assert first["history_risk"] == second["history_risk"]

    def test_risk_signal_change_changes_component(self):
        first = fingerprint_components(_inputs(history_data={"max_drawdown_pct": -15.75}))
        second = fingerprint_components(_inputs(history_data={"max_drawdown_pct": -18.2}))
        assert first["history_risk"] != second["history_risk"]


class TestSnapshotCountNotInPrompt:
    """快照原始文件数不得进入提示词/指纹（每跑一次报告就 +1，属观测计数）。"""

    def test_window_line_uses_period_count_not_raw_file_count(self):
        from src.python.report.holding_change_panel import build_holding_change_view

        contract = {
            "available": True,
            "period_count": 45,
            "event_count": 106,
            "window_start": "20260806T100000",
            "window_end": "20261024T100000",
            "snapshot_count": 999,
            "retention_days": 180,
            "sample": {"min_periods": 12, "min_events": 10, "sufficient": True},
        }
        view = build_holding_change_view(contract)
        joined = "\n".join(view["window_lines"])
        assert "999" not in joined
        assert "45 个观察期" in joined

    def test_pipeline_blocks_component_ignores_contract_display_fields(self):
        """审计组件与生产同口径：契约里的 snapshot_count 变化不算组件变化。"""
        from src.python.llm.module_fingerprint import _pipeline_blocks_text

        base = {"diff": {"is_first_check": True}}
        noisy = {"diff": {"is_first_check": True}, "snapshot_diff_data": {"snapshot_count": 999}}
        assert _pipeline_blocks_text(base) == _pipeline_blocks_text(noisy)


class TestDegradationBlockNoCrossSessionCounts:
    """【数据质量降级】段不得带跨会话累计次数（否则 expert_review 键每轮翻新）。"""

    def _pipeline(self, count: int) -> dict:
        return {
            "data_degradation": [
                {
                    "source_key": "industry",
                    "tier": "T3",
                    "failure_type": "unreachable",
                    "degraded": True,
                    "count": count,
                }
            ]
        }

    def test_count_change_does_not_change_block(self):
        from src.python.llm.prompts_data_blocks import _build_data_degradation_block

        assert _build_data_degradation_block(self._pipeline(3)) == _build_data_degradation_block(self._pipeline(9))

    def test_source_still_reported(self):
        from src.python.llm.prompts_data_blocks import _build_data_degradation_block

        text = _build_data_degradation_block(self._pipeline(3))
        assert "industry" in text and "unreachable" in text
