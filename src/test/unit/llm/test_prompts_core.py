"""prompts_core 格式化函数与系统提示常量单元测试。"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestPromptsCore:
    """prompts_core 基础函数与常量测试。"""

    def test_system_global_macro_constant(self):
        """_SYSTEM_GLOBAL_MACRO 是非常字符串。"""
        from src.python.llm.prompts_core import _SYSTEM_GLOBAL_MACRO

        assert isinstance(_SYSTEM_GLOBAL_MACRO, str)
        assert len(_SYSTEM_GLOBAL_MACRO) > 50

    def test_system_expert_review_constant(self):
        """_SYSTEM_EXPERT_REVIEW 包含关键指令短语。"""
        from src.python.llm.prompts_core import _SYSTEM_EXPERT_REVIEW

        assert isinstance(_SYSTEM_EXPERT_REVIEW, str)
        assert "Phase" in _SYSTEM_EXPERT_REVIEW or "定音锤" in _SYSTEM_EXPERT_REVIEW
        assert "置信度指引" in _SYSTEM_EXPERT_REVIEW
        assert "竞争语境约束" in _SYSTEM_EXPERT_REVIEW

    def test_system_health_check_constant(self):
        """_SYSTEM_HEALTH_CHECK 是非常字符串。"""
        from src.python.llm.prompts_core import _SYSTEM_HEALTH_CHECK

        assert isinstance(_SYSTEM_HEALTH_CHECK, str)
        assert len(_SYSTEM_HEALTH_CHECK) > 50

    def test_fmt_wan_yi(self):
        """≥1亿 → 亿单位。"""
        from src.python.llm.prompts_core import _fmt_wan

        assert _fmt_wan(123_000_000) == "1.23亿"
        assert _fmt_wan(100_000_000) == "1.00亿"

    def test_fmt_wan_wan(self):
        """≥1万 → 万单位。"""
        from src.python.llm.prompts_core import _fmt_wan

        assert _fmt_wan(12_345) == "1.2万"
        assert _fmt_wan(99_999) == "10.0万"

    def test_fmt_wan_yuan(self):
        """<1万 → 元。"""
        from src.python.llm.prompts_core import _fmt_wan

        assert _fmt_wan(9999) == "9,999"
        assert _fmt_wan(0) == "0"
        assert _fmt_wan(-500) == "-500"

    def test_fmt_holding_line_basic(self):
        """_fmt_holding_line 基础格式。"""
        from src.python.llm.prompts_core import _fmt_holding_line

        h = {"code": "600519", "name": "贵州茅台", "market_value": 200_000, "profit": 5000, "profit_rate": 2.5}
        result = _fmt_holding_line(h)
        assert isinstance(result, str)
        assert "600519" in result
        assert "20.0万" in result

    def test_llm_module_failure_dict(self):
        """LLM_MODULE_FAILURE 是 dict。"""
        from src.python.llm.prompts_core import LLM_MODULE_FAILURE

        assert isinstance(LLM_MODULE_FAILURE, dict)


class TestInsufficientInfoEscape:
    """情景段「不操作」出口：与强制方向项并存，且仅在情景段出现时追加。"""

    _BUILDER_KWARGS = {
        "total_mv": 100_000.0,
        "total_cost": 80_000.0,
        "total_profit": 20_000.0,
        "total_today_profit": 1_000.0,
        "holdings_count": 1,
        "categories": {},
    }

    def _build(self, **overrides) -> str:
        from src.python.llm.prompts import _build_expert_review_prompt

        holdings = [{"name": "测试基金", "code": "000001", "market_value": 100_000.0, "cost": 80_000.0}]
        return _build_expert_review_prompt(**self._BUILDER_KWARGS, holdings_details=holdings, **overrides)

    def test_fallback_scenario_carries_escape_and_conditional_mandate(self):
        prompt = self._build()
        assert "### 情景分析" in prompt
        # 信息不足出口（增量）+ 条件化方向约束（替换后口径）并存
        assert "「不操作」" in prompt and "所缺的具体数据" in prompt
        assert "条件化动作与触发条件" in prompt

    def test_conditional_scenario_carries_escape(self, monkeypatch):
        from src.python.config import get_llm_config

        monkeypatch.setattr(
            get_llm_config,
            "__call__",
            None,
        ) if False else None
        monkeypatch.setattr(
            "src.python.config.get_llm_config",
            lambda: {"debate": {"conditional": {"scenarios": [{"name": "加息", "desc": "利率上行"}]}}},
            raising=True,
        )
        prompt = self._build(enable_conditional=True)
        assert "加息情景" in prompt
        assert "「不操作」" in prompt

    def test_no_scenario_section_means_no_escape(self):
        """条件推理模式但未配置情景 → 无情景段，也不追加无托的「不操作」句。"""
        prompt = self._build(enable_conditional=True)
        assert "### 情景分析" not in prompt
        assert "「不操作」" not in prompt

    def test_skip_scenarios_debate_mode_has_no_escape(self):
        prompt = self._build(skip_scenarios=True)
        assert "### 情景分析" not in prompt
        assert "「不操作」" not in prompt

    def test_default_mandate_is_conditional_not_directional(self):
        """默认口径：要求条件化动作 + 触发条件，强制方向句不出现。"""
        prompt = self._build()
        assert "条件化动作与触发条件" in prompt
        assert "必须给出方向性判断" not in prompt

    def test_strict_mandate_restored_when_block_disabled(self):
        """回退通道：判断依据块关闭 → 走强制方向口径（两套常量共存一版）。"""
        from src.python.config.features import reset_feature_flags, set_feature_enabled

        set_feature_enabled("decision_basis", False)
        try:
            prompt = self._build()
        finally:
            reset_feature_flags()
        assert "必须给出方向性判断" in prompt
        assert "条件化动作与触发条件" not in prompt

    def test_specific_holding_mandate_allows_no_position_action(self):
        """品种约束开口子：允许「不对具体品种动手 + 理由」而不勉强引用品种。"""
        prompt = self._build()
        assert "不对具体品种动手" in prompt
        # 原约束仍保留（只是开口子，不是取消）
        assert "每个建议必须引用具体品种的名称和代码" in prompt


class TestScenarioMandateCacheSuffix:
    """情景段口径变体的缓存后缀：回退口径换键，默认口径不加后缀。"""

    def test_default_has_no_suffix(self):
        from src.python.llm.prompts_action import scenario_mandate_cache_suffix

        assert scenario_mandate_cache_suffix() == ""

    def test_strict_variant_adds_suffix(self):
        from src.python.config.features import reset_feature_flags, set_feature_enabled
        from src.python.llm.prompts_action import scenario_mandate_cache_suffix

        set_feature_enabled("decision_basis", False)
        try:
            assert scenario_mandate_cache_suffix() == "_ms"
        finally:
            reset_feature_flags()


class TestBuildRebalanceBlock:
    """_build_rebalance_block — LLM 智囊团深度复盘再平衡段落。"""

    def _overweight_holdings(self) -> list[dict]:
        """构造一只超限持仓（25%）+ 7 只合规（各约 9.6%）。"""
        holdings = [
            {"code": "600001", "name": "重仓甲", "market_value": 2500.0},
        ]
        for n in range(2, 9):
            holdings.append({"code": f"6000{n:02d}", "name": f"分散{n}", "market_value": 1000.0})
        return holdings

    def test_output_includes_overweight(self):
        """超限品种出现在再平衡建议段落。"""
        from src.python.llm.prompts_core import _build_rebalance_block

        text = _build_rebalance_block(self._overweight_holdings(), 10000.0)
        assert "【再平衡建议】" in text
        assert "重仓甲" in text
        assert "600001" in text

    def test_empty_when_no_overweight(self):
        """全部合规 → 返回空串。"""
        from src.python.llm.prompts_core import _build_rebalance_block

        holdings = [{"code": f"6000{n:02d}", "name": f"品种{n}", "market_value": 1000.0} for n in range(1, 11)]
        assert _build_rebalance_block(holdings, 10000.0) == ""

    def test_not_suppressed_by_silence_state(self, tmp_path):
        """即使静默期文件已记录触发，LLM 段落仍输出当前超限信号（不写静默文件）。"""
        from src.python.llm.prompts_core import _build_rebalance_block
        from src.python.analysis import _silence
        import datetime

        silence_file = str(tmp_path / "rebalance_silence.json")
        _silence._save_silence_state({"600001": datetime.date.today().isoformat()}, silence_file)
        text = _build_rebalance_block(self._overweight_holdings(), 10000.0)
        assert "重仓甲" in text
        # 不读写共享静默文件（不新增/修改状态）
        assert not (tmp_path / "rebalance_silence.json").exists() or _silence._load_silence_state(silence_file).get(
            "600001"
        )


class TestFacadeReexports:
    """三域子模块下沉后 prompts_core 门面同一性（回归：旧导入面不得破坏）。"""

    def test_all_names_resolve_on_facade(self) -> None:
        """__all__ 每个名字在门面上均可解析（拆分后门面仍完整）。"""
        from src.python.llm import prompts_core

        for name in prompts_core.__all__:
            assert getattr(prompts_core, name, None) is not None, name

    def test_domain_symbols_are_same_objects(self) -> None:
        """三域符号与子模块对象同一（门面即子模块，非副本）。"""
        from src.python.llm import failure_reasons, prompts_core, prompts_data_blocks, prompts_review

        assert prompts_core._fmt_wan is prompts_data_blocks._fmt_wan
        assert prompts_core._is_valid_number is prompts_data_blocks._is_valid_number
        assert prompts_core.FAIL_REASON_API_ERROR is failure_reasons.FAIL_REASON_API_ERROR
        assert prompts_core.LLM_MODULE_FAILURE is failure_reasons.LLM_MODULE_FAILURE
        assert prompts_core._build_self_review_prompt is prompts_review._build_self_review_prompt
        # 未列入 __all__ 的域符号同样经门面可达（消费方旧导入面）
        assert prompts_core._build_holding_change_review_prompt is prompts_review._build_holding_change_review_prompt
        assert prompts_core._SYSTEM_SELF_REVIEW is prompts_review._SYSTEM_SELF_REVIEW
        assert prompts_core._build_rebalance_block is prompts_data_blocks._build_rebalance_block
