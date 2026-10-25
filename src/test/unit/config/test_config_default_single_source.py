"""配置默认值单源收敛 — 取值入口、嵌套路径与默认表引用的回归用例。

覆盖：
  - 默认值表引用常量（报告深度档位）而非另写一份字面量
  - 嵌套默认值经点分路径取值（``a.b`` 与逐层传参等价）
  - debate 段默认值与 llm_settings 默认投影同源
  - provider 缺省优先级在各消费面一致

运行：pytest src/test/unit/config/test_config_default_single_source.py -v
"""

from __future__ import annotations

import pytest

from src.python.config import DEFAULT_PROVIDER_PRIORITY, get_default, get_llm_setting_default
from src.python.config._config_defaults import _DEFAULT_CONFIG
from src.python.config._llm_settings import _DEBATE_CONFIG_DEFAULTS
from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS
from src.python.core.constants import REPORT_DEPTH_DEFAULT, REPORT_DEPTH_LEVELS
from src.python.llm.depth_profile import REPORT_DEPTH_LEVELS as LLM_DEPTH_LEVELS

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


class TestDefaultAccessors:
    """默认值取值入口：嵌套路径与顶层键同源。"""

    def test_dotted_path_matches_nested_lookup(self) -> None:
        """点分路径与逐层取默认表结果一致（嵌套项不必在读取侧另写字面量）。"""
        assert get_default("history.lookback_days") == _DEFAULT_CONFIG["history"]["lookback_days"]
        assert get_default("history", "lookback_days") == get_default("history.lookback_days")

    def test_missing_path_returns_none(self) -> None:
        """路径任一层缺失返回 None（调用方可据此判断，而非抛 KeyError）。"""
        assert get_default("history.not_a_key") is None
        assert get_default("not_a_section.at_all") is None

    def test_llm_dotted_path(self) -> None:
        """llm_settings 默认值支持嵌套路径（debate/fact_check 等段内键）。"""
        expected = _DEFAULT_LLM_SETTINGS["debate"]["concentration_qa"]["threshold"]
        assert get_llm_setting_default("debate.concentration_qa.threshold") == expected
        assert get_llm_setting_default("debate.concentration_qa.threshold") == get_llm_setting_default(
            "debate", "concentration_qa", "threshold"
        )


class TestDebateDefaultsSingleSource:
    """debate 段默认值只保留一份（llm_settings 默认投影）。"""

    def test_debate_defaults_match_settings_projection(self) -> None:
        """辩论段默认值与 llm_settings 默认投影逐项一致（防止两份默认值漂移）。"""
        assert _DEBATE_CONFIG_DEFAULTS == _DEFAULT_LLM_SETTINGS["debate"]

    def test_procon_default_token_budget_present(self) -> None:
        """procon 单阶段输出上限有默认值（缺失会让预算守卫按 None 计算）。"""
        assert (
            _DEBATE_CONFIG_DEFAULTS["procon"]["per_call_max_tokens"]
            == _DEFAULT_LLM_SETTINGS["debate"]["procon"]["per_call_max_tokens"]
        )


class TestProviderPrioritySingleSource:
    """provider 缺省优先级：排序侧与展示侧取同一个常量。"""

    def test_priority_constant_is_default_table_value(self) -> None:
        """常量值即默认表缺省（不是另写一份数字）。"""
        from src.python.config._llm_providers_defaults import _DEFAULT_LLM_PROVIDERS

        assert DEFAULT_PROVIDER_PRIORITY not in {p["priority"] for p in _DEFAULT_LLM_PROVIDERS["providers"]}
        assert isinstance(DEFAULT_PROVIDER_PRIORITY, int)

    def test_module_info_uses_shared_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """模块信息映射对未声明优先级的线路取共享常量（不另用其它数字）。"""
        from src.python.llm import api as llm_api
        from src.python.report import llm_module_info

        # 端点解析在函数内导入，patch 须指向导入点所在模块
        monkeypatch.setattr(llm_api, "resolve_provider_endpoint", lambda *_a, **_k: "ep")
        mapping = llm_module_info._endpoint_priority_map({"_provider_list": [{"provider": "claude", "model": "m"}]})
        assert mapping == {"ep": float(DEFAULT_PROVIDER_PRIORITY)}


class TestReportDepthSingleSource:
    """报告深度档位：默认表与 llm 档位解析共用 core.constants 常量。"""

    def test_default_config_uses_constant(self) -> None:
        assert _DEFAULT_CONFIG["llm_report_depth"] == REPORT_DEPTH_DEFAULT

    def test_depth_profile_reexports_same_constant(self) -> None:
        assert REPORT_DEPTH_DEFAULT in REPORT_DEPTH_LEVELS
        assert LLM_DEPTH_LEVELS == REPORT_DEPTH_LEVELS

    def test_generated_template_uses_default_table(self) -> None:
        """首次生成的 config.json 模板取默认表的档位值（改常量即全链跟随）。"""
        from src.python.config._config_defaults import _get_default_config_template

        assert f'"llm_report_depth": "{REPORT_DEPTH_DEFAULT}"' in _get_default_config_template()
