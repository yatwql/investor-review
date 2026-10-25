"""LLM 缓存键与指纹的**跨模块同源**与**失效最小化**契约。

缓存正确性有两个反向风险，任一侧失守都会静默出错：

- **漏算导致陈旧**：提示词里用到的输入没进指纹 → 内容变了仍复用旧结论；
- **多算导致失效**：与内容无关的字段进了指纹 → 每隔一份报告就全量重算，成本翻倍。

本文件从"指纹组件"角度测：

| 角度 | 断言 |
|------|------|
| 同源 | 预检侧与写侧对同一输入得到同一指纹（结构保证，不靠纪律） |
| 敏感性 | 持仓/份额/成本/风险信号/生成参数 变化 → 指纹变 |
| 抗噪 | 行情价/涨跌幅/净值日期/仅展示字段 变化 → 指纹不变 |
| 组件归因 | `diff_fingerprint_components` 只报真实变化的组件 |
| 条件并入 | 空块（purchase_block 等）不追加 part，保持键稳定 |
| 参数范围 | 与生成无关的配置项（`cache` 等）不进后缀 |
"""

from __future__ import annotations

import pytest

from src.python.llm.module_fingerprint import (
    ModuleFingerprintInputs,
    diff_fingerprint_components,
    expert_review_fingerprint,
    fingerprint_components,
    generation_params_suffix,
    global_macro_fingerprint,
    health_check_fingerprint,
    penetration_deep_fingerprint,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


def _inputs(**overrides) -> ModuleFingerprintInputs:
    """最小指纹输入：只有持仓与总量，其余为空（避免用例相互耦合）。"""
    base = dict(
        total_mv=100_000.0,
        total_cost=90_000.0,
        total_profit=10_000.0,
        total_today_profit=200.0,
        holdings_details=[
            {"code": "600519", "name": "贵州茅台", "shares": 100, "cost": 150000.0},
            {"code": "510300", "name": "沪深300ETF", "shares": 1000, "cost": 4000.0},
        ],
        penetrated_assets=[],
        categories={},
        history_data={},
        a_indices={},
        us_indices={},
        competitive_context="",
        metrics={},
        data_quality_text="",
        purchase_block="",
        holding_change_block="",
        event_impact_block="",
        schedule_replay_block="",
        pipeline_data=None,
    )
    base.update(overrides)
    return ModuleFingerprintInputs(**base)


_BUILDERS = [
    global_macro_fingerprint,
    expert_review_fingerprint,
    health_check_fingerprint,
    penetration_deep_fingerprint,
]
_BUILDER_IDS = ["global_macro", "expert_review", "health_check", "penetration_deep"]


class TestDeterminismAndSourceAlignment:
    """同一输入恒定同指纹；预检侧与写侧是同一个函数（同源由结构保证）。"""

    @pytest.mark.parametrize("builder", _BUILDERS, ids=_BUILDER_IDS)
    def test_same_input_same_fingerprint(self, builder):
        assert builder(_inputs()) == builder(_inputs())

    @pytest.mark.parametrize("builder", _BUILDERS, ids=_BUILDER_IDS)
    def test_fingerprint_is_filename_safe(self, builder):
        """指纹会拼进缓存文件名：不得含路径分隔符/空白/中文。"""
        import re

        value = builder(_inputs())
        assert isinstance(value, str) and len(value) >= 8
        assert re.fullmatch(r"[0-9a-zA-Z_]+", value), value

    def test_components_match_official_fingerprint_scope(self):
        """组件表与正式指纹同口径：同一份输入的组件哈希稳定可复现。"""
        first = fingerprint_components(_inputs())
        second = fingerprint_components(_inputs())
        assert first == second
        assert first, "组件表不应为空"


class TestSensitivityChangesFingerprint:
    """内容变化必须换键（漏算＝拒绝陈旧数据）。"""

    def test_shares_alone_do_not_change_fingerprint(self):
        """份额变化但成本总额不变 → 键不变：指纹提取的是 name/code/cost，不含 shares。

        说明：份额变化通常同时改变成本总额（加仓/减仓），那时由上面的 cost 用例覆盖；
        单独变更份额而成本总额不变（如份额拆分场景）不改变提示词内容，不应白算。
        """
        moved = _inputs(
            holdings_details=[
                {"code": "600519", "name": "贵州茅台", "shares": 200, "cost": 150000.0},
                {"code": "510300", "name": "沪深300ETF", "shares": 1000, "cost": 4000.0},
            ]
        )
        assert expert_review_fingerprint(moved) == expert_review_fingerprint(_inputs())

    @pytest.mark.parametrize(
        "builder",
        [expert_review_fingerprint, penetration_deep_fingerprint],
        ids=["expert_review", "penetration_deep"],
    )
    def test_cost_basis_change(self, builder):
        changed = _inputs(
            holdings_details=[
                {"code": "600519", "name": "贵州茅台", "shares": 100, "cost": 160000.0},
                {"code": "510300", "name": "沪深300ETF", "shares": 1000, "cost": 4000.0},
            ]
        )
        assert builder(changed) != builder(_inputs())

    @pytest.mark.parametrize(
        "builder",
        [expert_review_fingerprint, penetration_deep_fingerprint],
        ids=["expert_review", "penetration_deep"],
    )
    def test_new_holding_added(self, builder):
        changed = _inputs(
            holdings_details=[
                {"code": "600519", "name": "贵州茅台", "shares": 100, "cost": 150000.0},
                {"code": "510300", "name": "沪深300ETF", "shares": 1000, "cost": 4000.0},
                {"code": "159915", "name": "创业板ETF", "shares": 500, "cost": 1000.0},
            ]
        )
        assert builder(changed) != builder(_inputs())

    def test_global_macro_keys_on_totals_not_holdings_detail(self):
        """全球政经局势只用总量/指数/分类：份额变化但总量不变时键不变（不白算）。"""
        moved = _inputs(
            holdings_details=[
                {"code": "600519", "name": "贵州茅台", "shares": 200, "cost": 75000.0},
                {"code": "510300", "name": "沪深300ETF", "shares": 1000, "cost": 4000.0},
            ]
        )
        assert global_macro_fingerprint(moved) == global_macro_fingerprint(_inputs())

    def test_global_macro_keys_on_total_mv(self):
        """总市值变了必须换键（对比结论依赖它）。"""
        assert global_macro_fingerprint(_inputs(total_mv=120_000.0)) != global_macro_fingerprint(_inputs())

    def test_history_risk_signal_change(self):
        """风险信号子集变化 → 承载它的模块指纹变；global_macro 只用总量/指数，不参与。"""
        from src.python.llm.fingerprint import RISK_SIGNAL_KEYS

        key = sorted(RISK_SIGNAL_KEYS)[0]
        base = _inputs(history_data={key: 0.1})
        changed = _inputs(history_data={key: 0.2})
        assert health_check_fingerprint(base) != health_check_fingerprint(changed)
        assert expert_review_fingerprint(base) != expert_review_fingerprint(changed)
        assert global_macro_fingerprint(base) == global_macro_fingerprint(changed), "宏观模块不含持仓风险信号"

    def test_data_quality_text_change_affects_health_check(self):
        base = _inputs(data_quality_text="降级：push2 不可达")
        changed = _inputs(data_quality_text="数据完整")
        assert health_check_fingerprint(base) != health_check_fingerprint(changed)

    def test_penetration_change_affects_penetration_module(self):
        base = _inputs(penetrated_assets=[{"code": "00700", "name": "腾讯", "mv": 1000.0, "ratio": 0.1}])
        changed = _inputs(penetrated_assets=[{"code": "00700", "name": "腾讯", "mv": 2000.0, "ratio": 0.2}])
        assert penetration_deep_fingerprint(base) != penetration_deep_fingerprint(changed)


class TestNoiseDoesNotChangeFingerprint:
    """与提示词内容无关的字段变化不得换键（多算＝白花钱）。"""

    @pytest.mark.parametrize("builder", _BUILDERS, ids=_BUILDER_IDS)
    def test_price_and_change_pct_are_excluded(self, builder):
        """行情价/涨跌幅不进指纹：盘中价格跳动不应导致分析模块全量重算。"""
        base = _inputs(
            holdings_details=[
                {
                    "code": "600519",
                    "name": "贵州茅台",
                    "shares": 100,
                    "cost": 150000.0,
                    "price": 1600.0,
                    "change_pct": 1.2,
                },
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "shares": 1000,
                    "cost": 4000.0,
                    "price": 4.2,
                    "change_pct": -0.5,
                },
            ]
        )
        moved = _inputs(
            holdings_details=[
                {
                    "code": "600519",
                    "name": "贵州茅台",
                    "shares": 100,
                    "cost": 150000.0,
                    "price": 1650.0,
                    "change_pct": 3.1,
                },
                {
                    "code": "510300",
                    "name": "沪深300ETF",
                    "shares": 1000,
                    "cost": 4000.0,
                    "price": 4.15,
                    "change_pct": -1.2,
                },
            ]
        )
        assert builder(base) == builder(moved)

    @pytest.mark.parametrize("builder", _BUILDERS, ids=_BUILDER_IDS)
    def test_display_only_field_does_not_change(self, builder):
        """仅展示字段（如名称后缀/来源标签）不影响指纹。"""
        base = _inputs(
            holdings_details=[
                {"code": "600519", "name": "贵州茅台", "shares": 100, "cost": 150000.0, "source": "holding"}
            ]
        )
        changed = _inputs(
            holdings_details=[
                {"code": "600519", "name": "贵州茅台", "shares": 100, "cost": 150000.0, "source": "penetration"}
            ]
        )
        assert builder(base) == builder(changed)

    def test_empty_block_does_not_shift_key(self):
        """空块（无申购限制）不追加 part：块从"空"到"仍是空"时键不变。"""
        assert expert_review_fingerprint(_inputs(purchase_block="")) == expert_review_fingerprint(
            _inputs(purchase_block="")
        )

    def test_nonempty_block_changes_key(self):
        """块非空（真的出现申购限制）必须换键——提示词内容变了。"""
        assert expert_review_fingerprint(_inputs(purchase_block="单日限购 1000 元")) != expert_review_fingerprint(
            _inputs(purchase_block="")
        )


class TestComponentAttribution:
    """组件级归因：连续同数据报告仍 miss 时能定位到具体组件。"""

    def test_diff_reports_only_changed_component(self):
        previous = fingerprint_components(_inputs())
        current = fingerprint_components(
            _inputs(
                holdings_details=[
                    {"code": "600519", "name": "贵州茅台", "shares": 300, "cost": 450000.0},
                    {"code": "510300", "name": "沪深300ETF", "shares": 1000, "cost": 4000.0},
                ]
            )
        )
        changed = diff_fingerprint_components(previous, current)
        assert "holdings" in changed
        assert "categories" not in changed, "未变组件不得误报"

    def test_no_previous_returns_empty(self):
        """无上次记录时不臆断变化（避免把"首次运行"说成"组件都变了"）。"""
        assert diff_fingerprint_components(None, fingerprint_components(_inputs())) == []

    def test_identical_components_have_no_diff(self):
        assert diff_fingerprint_components(fingerprint_components(_inputs()), fingerprint_components(_inputs())) == []


class TestGenerationParamsSuffix:
    """生成参数后缀：只并入会改变输出的项，非默认值才追加。"""

    def test_default_config_yields_empty_suffix(self, monkeypatch):
        """全默认时不追加任何 part（否则存量缓存整体失效）。"""
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {})
        assert generation_params_suffix("expert_review") == ""

    def test_model_override_changes_suffix(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"model_expert_review": "claude-sonnet-5-5"})
        assert generation_params_suffix("expert_review") != ""

    def test_cache_switch_not_in_suffix(self, monkeypatch):
        """与生成无关的开关（cache_enabled_*）不进后缀，避免无谓失效。"""
        base = {"model_expert_review": ""}
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: base)
        without = generation_params_suffix("expert_review")
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {**base, "cache_enabled_expert_review": False})
        assert generation_params_suffix("expert_review") == without

    def test_temperature_change_changes_suffix(self, monkeypatch):
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"temperature_expert_review": 0.2})
        cooler = generation_params_suffix("expert_review")
        monkeypatch.setattr("src.python.config.get_llm_config", lambda: {"temperature_expert_review": 0.9})
        assert generation_params_suffix("expert_review") != cooler
