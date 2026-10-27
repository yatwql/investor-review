"""功能开关注册表与名称解析单元测试。

覆盖 ``features.feature_switch_registry`` 注册表驱动的名称解析
（``resolve_experiment_flags`` / ``describe_experiment_flags`` /
``parse_switch_override``），该解析是 CLI ``--experiment`` / ``--feature`` 参数
与 TUI 菜单 S / Web 配置面板同源的保证。

另覆盖开关注册表自身的两条不变式：默认值表中每个开关都必须有消费者（声明即死
的开关会让用户照文档配置后毫无效果），以及 ``features.json`` 里出现无消费者开关
时必须告警而非静默忽略。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from src.python.config.features import (
    EXPERIMENT_ALL,
    FEATURE_FLAGS,
    GROUP_LABELS,
    GROUP_MECHANISM,
    GROUP_ORDER,
    FeatureSwitchDef,
    _FEATURE_FLAGS_DEFAULT,
    describe_experiment_flags,
    describe_switches,
    enabled_experimental_features,
    experimental_flags,
    feature_switch_registry,
    is_experimental_switch,
    load_feature_overrides,
    parse_switch_override,
    resolve_experiment_flags,
    resolve_switch_values,
    switches_in_group,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]

# 仓库根：src/test/unit/config/<本文件> → parents[4]
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_REGISTRY_FILE = _PROJECT_ROOT / "src" / "python" / "config" / "features.py"


def _experimental_flags() -> set[str]:
    """实验项开关名集合（注册表 `experimental` 字段是唯一来源，测试也不另写清单）。"""
    return {flag for flag, _d in experimental_flags()}


@pytest.mark.unit
class TestResolveExperimentFlags:
    """实验功能名解析测试。"""

    def test_resolve_by_flag_name(self):
        """按开关名解析。"""
        flags, unknown = resolve_experiment_flags(["decision_reflection"])
        assert flags == {"decision_reflection"}
        assert unknown == []

    def test_resolve_by_display_name(self):
        """按中文显示名解析（注册表驱动，无需维护第二份清单）。"""
        display_name = feature_switch_registry["decision_reflection"].label
        flags, unknown = resolve_experiment_flags([display_name])
        assert flags == {"decision_reflection"}
        assert unknown == []

    def test_promoted_flag_rejected_after_leaving_experiment_group(self):
        """已转正的开关不再被 ``--experiment`` 接受——它已不是实验项。

        转正的语义边界：``--experiment`` 的取值域取注册表 ``experimental`` 字段，转正后该开关
        改由 ``--feature NAME=VALUE``（全域双向）或 features.json 控制，若仍被
        ``--experiment`` 接受，用户会以为它还是实验开关。
        """
        for promoted in (
            "deterministic_signal",
            "module_quality_gate",
            "llm_debate_procon",
            "factor_catalog",
            "rebalance_schedule_replay",
        ):
            flags, unknown = resolve_experiment_flags([promoted])
            assert flags == set(), f"{promoted} 已转正，不应再被实验清单解析命中"
            assert unknown == [promoted]

    def test_resolve_every_registry_entry(self):
        """注册表中每个实验功能的开关名与显示名均可解析。"""
        for flag, definition in experimental_flags():
            by_flag, unknown_flag = resolve_experiment_flags([flag])
            by_name, unknown_name = resolve_experiment_flags([definition.label])
            assert by_flag == {flag}, f"开关名解析失败: {flag}"
            assert by_name == {flag}, f"显示名解析失败: {definition.label}"
            assert unknown_flag == [] and unknown_name == []

    def test_resolve_flag_name_case_insensitive(self):
        """开关名大小写不敏感。"""
        flags, unknown = resolve_experiment_flags(["DECISION_REFLECTION"])
        assert flags == {"decision_reflection"}
        assert unknown == []

    def test_resolve_all(self):
        """all 解析为全部实验功能。"""
        flags, unknown = resolve_experiment_flags([EXPERIMENT_ALL])
        assert flags == _experimental_flags()
        assert unknown == []

    def test_resolve_mixed_and_dedup(self):
        """多种写法混用并去重。"""
        display_name = feature_switch_registry["decision_reflection"].label
        flags, unknown = resolve_experiment_flags(["decision_reflection", "DECISION_REFLECTION", display_name, "all"])
        assert flags == _experimental_flags()
        assert unknown == []

    def test_unknown_reported_but_hits_kept(self):
        """未识别项进入 unknown，已识别项仍正常解析。"""
        flags, unknown = resolve_experiment_flags(["decision_reflection", "no_such_feature"])
        assert flags == {"decision_reflection"}
        assert unknown == ["no_such_feature"]

    def test_describe_lists_all_entries(self):
        """清单描述串覆盖全部开关名与显示名。"""
        text = describe_experiment_flags()
        for flag, definition in experimental_flags():
            assert flag in text
            assert definition.label in text

    def test_experiment_group_excludes_standard_switches(self):
        """非实验开关不得混进实验清单——否则会被当实验项写进产物自述。"""
        assert "cost_position" not in _experimental_flags()
        assert is_experimental_switch("cost_position") is False
        # 转正后的读侧增强同理：混进实验清单会被当成「非默认产物」写进自述
        assert "deterministic_signal" not in _experimental_flags()


@pytest.mark.unit
class TestEnabledExperimentalFeatures:
    """已启用清单（报告产物标注生成条件的唯一取数口）。"""

    def test_none_enabled_by_default(self):
        """实验开关默认全关 → 清单为空（报告不出现该行）。"""
        assert enabled_experimental_features() == []

    def test_returns_display_name_of_enabled_flag(self):
        """启用项返回 (开关名, 显示名)，显示名取自注册表而非另写一份。"""
        from src.python.config.features import set_feature_enabled

        set_feature_enabled("decision_reflection", True)

        assert enabled_experimental_features() == [
            ("decision_reflection", feature_switch_registry["decision_reflection"].label)
        ]

    def test_follows_registry_order(self):
        """按注册表顺序返回；已转正开关即使启用也不进清单。"""
        from src.python.config.features import set_feature_enabled

        # 故意先启用已转正的 llm_debate_procon（实验清单只收 experimental 项，此处只启用其一）
        set_feature_enabled("llm_debate_procon", True)
        set_feature_enabled("decision_reflection", True)

        assert [flag for flag, _name in enabled_experimental_features()] == [
            "decision_reflection",
        ]

    def test_only_experimental_flags_listed(self):
        """默认开启的非实验开关（如 cost_position）不进清单——清单只答「非默认产物」与否。"""
        from src.python.config.features import set_feature_enabled

        set_feature_enabled("cost_position", True)

        assert enabled_experimental_features() == []


@pytest.mark.unit
class TestReportAffectingClassification:
    """产物自述的准入口径：能否改变报告产物。

    实验注册表第三字段是该问题的书面答案。报告是脱离本机流转的文件，其自述
    只应列出可能改变内容的开关；列进一个不改报告任何字节的开关，读者会推断
    内容受其影响（系统自检曾如此，转正前它门控 TUI 菜单与 Web 卡片，产物零影响）。
    """

    def test_every_entry_declares_affects_report(self):
        """每项都必须显式回答——缺字段即注册表结构漂移，宣告声明不再被强制。"""
        for flag, definition in feature_switch_registry.items():
            assert isinstance(definition.affects_report, bool), f"{flag} 的 affects_report 须为布尔"

    def test_entry_only_feature_excluded_from_notice(self, monkeypatch):
        """只影响入口可见性的项不进清单（合成项验证，当前实验项恰无此类成员）。"""
        from src.python.config import features

        monkeypatch.setitem(
            features.feature_switch_registry,
            "ui_only_probe",
            FeatureSwitchDef("仅入口探针", "只改面板显隐", GROUP_MECHANISM, False, False, experimental=True),
        )
        monkeypatch.setitem(features.FEATURE_FLAGS, "ui_only_probe", True)
        monkeypatch.setitem(features.FEATURE_FLAGS, "decision_reflection", True)

        flags = [flag for flag, _name in features.enabled_experimental_features()]

        assert flags == ["decision_reflection"]

    def test_self_check_has_no_registry_switch(self):
        """系统自检恒上屏后不再有开关条目——产物自述在默认态为空。"""
        from src.python.config.features import feature_switch_registry
        from src.python.report.experimental_notice import enabled_notice_line

        assert "doctor_check" not in feature_switch_registry
        assert enabled_notice_line() is None


@pytest.mark.unit
class TestSelfCheckAlwaysOn:
    """系统自检恒上屏（无功能开关）。

    自检是只读诊断——不改产物、不写文件、联网检查每次显式确认；没有开关就没有
    「诊断入口被配置关掉」的失效路径。TUI `[T]`、Web 自检卡与 CLI `doctor` 三面同源。
    """

    def test_not_in_registry(self):
        from src.python.config.features import feature_switch_registry

        assert "doctor_check" not in feature_switch_registry

    def test_menu_has_no_gate(self):
        from src.python.tui import tui_menu

        assert "T" not in tui_menu.FEATURE_GATED_ITEMS

    def test_system_info_always_reports_enabled(self):
        from src.python.core.system_info import build_system_info

        assert build_system_info()["doctor_enabled"] is True


@pytest.mark.unit
class TestDatasourceAdapterBuiltinized:
    """数据源适配契约已内置（不可关闭）：默认链路即走适配器分支。

    适配器与既有手写转换函数逐源等价（唯一非等价处是东财源多出
    market_cap/pe 两个 None 键，下游一律 ``.get()`` 读取，语义不变，由
    ``test_quote_adapter_parity.py`` 逐源锁定）；适配器不可用时链路自动
    回退既有映射（回退用例由 parity 文件锁定）。
    """

    def test_default_config_runs_adapter_chain(self):
        """默认配置（无任何覆写）下链路即走适配器分支——内置的实际效果。"""
        from src.python.fetcher import price as price_module

        providers, _transforms = price_module._price_chain_slots()

        assert providers is not price_module._PRICE_PROVIDERS


@pytest.mark.unit
class TestReadSidePromotion:
    """读侧增强的转正：默认开、非实验项、关门仍有效、默认路径真的走新实现。

    这批开关会改变产物内容，但代价面为零：只改提示词或加标注，**不增 LLM 调用
    次数**。写账本的 ``decision_reflection`` 仍标 ``experimental=True``（真实账本
    积累待验证）；换调用次数的 ``llm_debate_procon`` 已转正入分析增强组（默认关，用户
    按需开启；同组相邻的 ``llm_debate_conditional`` 保持默认开）。信号沉淀账本
    （原实验开关 ``signal_ledger``）已并入 ``deterministic_signal`` 并转正：账本
    有真实数据积累验证，且写盘属幂等追加、开销可忽略。
    """

    PROMOTED = (
        "deterministic_signal",
        "module_quality_gate",
        "llm_debate_conditional",
    )

    def test_default_enabled(self):
        """出厂默认开——转正的实际效果（只 patch 取值的用例测不出默认值本身）。"""
        from src.python.config.features import get_feature_defaults

        defaults = get_feature_defaults()

        for flag in self.PROMOTED:
            assert defaults[flag] is True, f"{flag} 转正后出厂默认应为开"

    def test_not_in_experimental_registry(self):
        """非实验项：不进产物自述（面板可见性由作用域组承接，转正不丢入口）。"""
        for flag in self.PROMOTED:
            assert flag not in _experimental_flags()
            assert is_experimental_switch(flag) is False

    def test_switch_still_honored(self):
        """转正不等于不可关——关闭途径仍有效（features.json / ``--feature``）。"""
        from src.python.config.features import is_feature_enabled, set_feature_enabled

        for flag in self.PROMOTED:
            set_feature_enabled(flag, False)
            assert is_feature_enabled(flag) is False, f"{flag} 置 false 后仍未关闭"
            set_feature_enabled(flag, True)

    def test_prompt_affecting_defaults_live_in_production_path(self):
        """默认配置下提示词类增强的缓存后缀已生效——生产路径真的走新实现。

        后缀函数是「开关 → 缓存键」的唯一判定点（写侧指纹与预检侧共用），返回
        非空即证明默认配置下提示词确实带上了增强段；默认值若被改回关，本用例转红。
        """
        from src.python.core.decision_header import structured_header_cache_suffix
        from src.python.llm.module_fingerprint import debate_feature_cache_suffix

        assert structured_header_cache_suffix() == "_dh"
        assert debate_feature_cache_suffix() == "_c"

    def test_not_in_report_notice_after_promotion(self):
        """已转正项不进产物自述——非实验项不再是「非默认产物」的标记。"""
        from src.python.report.experimental_notice import enabled_notice_line

        assert enabled_notice_line() is None


@pytest.mark.unit
class TestRegistryLiveness:
    """开关注册表每一项都必须有消费者。

    缺陷场景：``_FEATURE_FLAGS_DEFAULT`` 曾声明 16 项全仓无任何代码读取的开关
    （LLM 模块启停、基金深度分析、新闻源、历史走势、匿名化总开关、缓存日清理）
    ——这些能力实际由 ``config.json`` / ``llm_settings.json`` 各自的键控制，开关
    声明了却从未接线（``git log -S`` 证实从未被任何提交消费过）。用户在
    ``features.json`` 里照文档配置后不产生任何效果，而文档仍按生效开关介绍。
    本类是该场景的回归防线。
    """

    # 已移出注册表的陈旧开关：能力各归其主，不得再回来（回来即意味着两处清单
    # 重新漂移，且多半又是声明即死）
    REMOVED_STALE_FLAGS = (
        # LLM 模块启停 → llm_settings.json 的 enabled_llm
        "llm_global_macro",
        "llm_expert_review",
        "llm_health_check",
        "llm_penetration_deep",
        "llm_news_correlation",
        # 基金深度分析模块 → config.json 的 enable_fund_deep_analysis
        "fund_deep_analysis_fund_manager",
        "fund_deep_analysis_fund_concentration",
        # 新闻源启停 → config.json 的 news_sources
        "news_sina",
        "news_eastmoney",
        "news_cls",
        "news_wallstreetcn",
        "news_akshare",
        # 历史走势与回撤 → config.json 的 enable_history
        "history_portfolio",
        "history_benchmark",
        # 匿名化 → config.json 的 anonymization.mode
        "anonymizer",
        # 启动缓存清理 → 无条件执行，无开关（见 cache/__init__.py）
        "cache_daily_cleanup",
        # 量化指标逐项开关 → 已删除（指标始终全量计算与渲染，无开关）
        "metrics_sharpe",
        "metrics_calmar",
        "metrics_hhi",
        "metrics_winrate",
        "metrics_turnover",
        "metrics_risk_contribution",
        "metrics_beta",
        # 联接基金穿透 → 内置恒开、无开关（穿透是真实口径而非可选口径）
        "feeder_penetration",
    )

    @staticmethod
    def _source_text_outside_registry() -> str:
        """拼接 ``src/python`` 下除注册表自身外的全部源码文本。

        不限于 ``is_feature_enabled`` 的直接实参：开关名也可能经模块常量、元组
        或映射表间接传入（如指标开关的元组、熔断特性开关的映射），因此按「开关名
        是否作为字符串字面量出现在消费方的源码里」判定。
        """
        chunks: list[str] = []
        for path in sorted((_PROJECT_ROOT / "src" / "python").rglob("*.py")):
            if path == _REGISTRY_FILE:
                continue
            chunks.append(path.read_text(encoding="utf-8"))
        return "\n".join(chunks)

    @pytest.mark.unit
    def test_every_flag_has_a_consumer(self):
        """默认值表中每个开关名都必须在注册表之外的源码里被引用。

        新增开关若只在 ``_FEATURE_FLAGS_DEFAULT`` 里加一行、却没接线到任何消费点，
        本用例即失败——那正是「用户照文档配置后毫无效果」的缺陷形态。
        """
        source = self._source_text_outside_registry()
        dead = [flag for flag in _FEATURE_FLAGS_DEFAULT if not re.search(rf"""["']{re.escape(flag)}["']""", source)]
        assert not dead, (
            f"以下开关在 src/python 内无任何消费者，声明即死（用户配置后不产生效果）：{dead}；"
            "请接线到消费点，或按其能力归属移到 config.json / llm_settings.json 并从注册表移除"
        )

    @pytest.mark.unit
    def test_removed_stale_flags_stay_out(self):
        """陈旧开关不得再回到默认值表（否则与各自的真实归属键重复且多半又无人读）。"""
        resurrected = [flag for flag in self.REMOVED_STALE_FLAGS if flag in _FEATURE_FLAGS_DEFAULT]
        assert not resurrected, (
            f"以下开关已被移除，不得回到 _FEATURE_FLAGS_DEFAULT：{resurrected}；"
            "对应能力分别归属 llm_settings.json 的 enabled_llm / config.json 的 "
            "enable_fund_deep_analysis、news_sources、enable_history、anonymization.mode，"
            "量化指标随指标全量渲染（无开关），联接基金穿透已内置恒开"
            "（fetcher/fund.py::with_feeder_penetration，无开关）"
        )

    @pytest.mark.unit
    def test_every_experimental_flag_is_registered(self):
        """实验项开关都必须在默认值表登记，否则用户开了也无效。"""
        unregistered = sorted(_experimental_flags() - set(_FEATURE_FLAGS_DEFAULT))
        assert not unregistered, f"实验开关未登记到 _FEATURE_FLAGS_DEFAULT（永远开不起来）：{unregistered}"


@pytest.mark.unit
class TestFeatureSwitchRegistryInvariants:
    """注册表的结构不变式（三渠道与文档清单一律由它派生）。"""

    def test_defaults_are_derived_projection(self):
        """默认值表是注册表的派生投影，不是第二份手写清单。"""
        assert _FEATURE_FLAGS_DEFAULT == {flag: d.default for flag, d in feature_switch_registry.items()}

    def test_registry_order_preserved_in_defaults(self):
        """投影保序——面板顺序即注册表顺序，重排注册表不得打乱取值表。"""
        assert list(_FEATURE_FLAGS_DEFAULT) == list(feature_switch_registry)

    def test_every_definition_complete(self):
        """每条声明字段齐备：显示名/说明非空，分组合法，默认值为布尔。"""
        for flag, d in feature_switch_registry.items():
            assert isinstance(d, FeatureSwitchDef), f"{flag} 不是 FeatureSwitchDef"
            assert d.label.strip(), f"{flag} 缺显示名"
            assert d.desc.strip(), f"{flag} 缺说明"
            assert d.group in GROUP_ORDER, f"{flag} 分组 '{d.group}' 非法"
            assert isinstance(d.default, bool), f"{flag} 默认值须为布尔"
            assert isinstance(d.affects_report, bool), f"{flag} 的 affects_report 须为布尔"

    def test_groups_partition_registry(self):
        """两个分组恰好划分全部开关——漏归组的开关将没有面板入口。"""
        grouped = [flag for group in GROUP_ORDER for flag, _d in switches_in_group(group)]
        assert sorted(grouped) == sorted(feature_switch_registry)
        assert len(grouped) == len(set(grouped)), "同一开关不得同时属两个分组"

    def test_experimental_items_default_off(self):
        """跨轴唯一不变式：实验项出厂关（experimental 与 default 解耦后的剩余约束）。

        作用域分组不再携带生命周期语义——机制与诊断组内既有默认开的机制项，
        也有默认关的实验项，故分组与默认值之间不再有恒定关系；但实验项若
        默认开，会被当非默认产物写进自述而它其实人人都在用。
        """
        for flag, d in experimental_flags():
            assert d.default is False, f"实验项 {flag} 出厂默认应为关"

    def test_labels_cover_all_groups(self):
        """每个分组都有面板标题（缺标题则分组块渲染为无名块）。"""
        assert set(GROUP_ORDER) <= set(GROUP_LABELS)

    def test_domain_mapping_is_total_and_valid(self):
        """组→域映射覆盖全部组，值域落在五域内（Web 五域编排的唯一取数口）。"""
        from src.python.config.features import DOMAIN_HINTS, DOMAIN_LABELS, DOMAIN_ORDER, GROUP_DOMAIN

        assert set(GROUP_DOMAIN) == set(GROUP_ORDER)
        assert set(GROUP_DOMAIN.values()) <= set(DOMAIN_ORDER)
        assert set(DOMAIN_ORDER) <= set(DOMAIN_LABELS) | set(DOMAIN_HINTS)

    def test_panel_groups_partition_all_groups(self):
        """面板编排覆盖全部组且每组恰属一个面板（漏组 = 该组没有入口）。"""
        from src.python.config.features import PANEL_GROUPS

        listed = [group for groups in PANEL_GROUPS.values() for group in groups]
        assert sorted(listed) == sorted(GROUP_ORDER)

    def test_needs_hint_is_boolean(self):
        """``needs_hint`` 显式声明（默认 False），面板据此决定是否常显副行。"""
        for flag, d in feature_switch_registry.items():
            assert isinstance(d.needs_hint, bool), f"{flag} 的 needs_hint 须为布尔"

    def test_no_retired_switch_remains(self):
        """已退役的自检开关不得回到注册表（否则面板多出无消费者入口）。"""
        assert "doctor_check" not in feature_switch_registry


@pytest.mark.unit
class TestSwitchOverrideParsing:
    """``--feature NAME=VALUE`` 取值解析（全注册表、双向、即时校验）。"""

    def test_parse_off_and_on(self):
        """off/on 双向均可解析——这是与 ``--experiment``（只开）的关键差异。"""
        assert parse_switch_override("cost_position=off") == ("cost_position", False)
        assert parse_switch_override("deterministic_signal=on") == ("deterministic_signal", True)

    def test_parse_value_case_insensitive(self):
        """取值大小写不敏感（开关名仍精确匹配）。"""
        assert parse_switch_override("cost_position=OFF") == ("cost_position", False)
        assert parse_switch_override("cost_position=TRUE") == ("cost_position", True)

    def test_parse_accepts_numeric_and_yes_no(self):
        """取值词表覆盖 1/0 与 yes/no。"""
        assert parse_switch_override("cost_position=1") == ("cost_position", True)
        assert parse_switch_override("cost_position=0") == ("cost_position", False)
        assert parse_switch_override("market_temperature=no") == ("market_temperature", False)

    def test_parse_tolerates_surrounding_spaces(self):
        """``NAME = VALUE`` 两侧空白可容忍（手输命令行常见）。"""
        assert parse_switch_override(" cost_position = off ") == ("cost_position", False)

    def test_unknown_name_raises_with_options(self):
        """未知开关名 → 报错并列出可选项，不静默失效。"""
        with pytest.raises(ValueError) as err:
            parse_switch_override("no_such_switch=on")
        assert "no_such_switch" in str(err.value)
        assert "cost_position" in str(err.value)

    def test_missing_equals_raises(self):
        """缺 ``=`` → 报错（不把整个串当开关名而报「未知开关」）。"""
        with pytest.raises(ValueError) as err:
            parse_switch_override("cost_position")
        assert "NAME=VALUE" in str(err.value)

    def test_unrecognized_value_raises(self):
        """取值不在词表内 → 报错（如误传 `cost_position=maybe`）。"""
        with pytest.raises(ValueError) as err:
            parse_switch_override("cost_position=maybe")
        assert "maybe" in str(err.value)

    def test_every_registry_flag_parsable(self):
        """全注册表开关名都能被 ``--feature`` 取到（含机制与诊断组，这正是本批次的缺口）。"""
        for flag in feature_switch_registry:
            assert parse_switch_override(f"{flag}=off") == (flag, False)

    def test_resolve_switch_values_last_wins(self):
        """同名重复以最后一次为准（命令行从左到右覆盖）。"""
        assert resolve_switch_values([("cost_position", False), ("cost_position", True)]) == [
            ("cost_position", True)
        ]

    def test_resolve_switch_values_empty(self):
        """未传参数（None / 空列表）→ 空覆写，不触碰运行时开关。"""
        assert resolve_switch_values(None) == []
        assert resolve_switch_values([]) == []

    def test_describe_switches_covers_all_registry(self):
        """帮助提示串覆盖全注册表（含四组全部开关），供报错时列出可选项。"""
        text = describe_switches()
        for flag, d in feature_switch_registry.items():
            assert flag in text
            assert d.label in text


@pytest.mark.unit
class TestUnknownOverrideWarning:
    """``features.json`` 中的无消费者开关必须告警，不静默忽略。"""

    @staticmethod
    def _rendered_warnings(mock_logger) -> list[str]:
        """返回该 mock logger 上全部 warning 渲染后的文本。"""
        rendered = []
        for call in mock_logger.warning.call_args_list:
            template = str(call.args[0]) if call.args else ""
            try:
                rendered.append(template % call.args[1:])
            except (TypeError, ValueError):
                rendered.append(template)
        return rendered

    @pytest.mark.unit
    def test_unknown_flags_warn_in_one_message(self, tmp_path):
        """无消费者开关 → 合并为一条 WARNING，且逐键列名（不刷屏、不静默）。"""
        fpath = tmp_path / "features.json"
        fpath.write_text(json.dumps({"no_such_switch": True, "another_ghost": False}), encoding="utf-8")

        # patch.dict 传空值：进入时不预置任何键（预置会让「未知开关」在加载时变成
        # 已知而绕过告警），退出时按快照还原，顺带清掉本次加载新增的键。
        with (
            patch("src.python.config.features.FEATURES_FILE", str(fpath)),
            patch("src.python.config.features.logger") as mock_logger,
            patch.dict(FEATURE_FLAGS, {}),
        ):
            load_feature_overrides()
            warnings = [text for text in self._rendered_warnings(mock_logger) if "无消费者" in text]

            assert len(warnings) == 1, "多个无消费者开关应合并为一条告警，而非逐键刷屏"
            assert "no_such_switch" in warnings[0]
            assert "another_ghost" in warnings[0]

    @pytest.mark.unit
    def test_known_flag_does_not_warn(self, tmp_path):
        """已登记开关不触发无消费者告警，且覆写照常生效（正常配置不被误报）。"""
        fpath = tmp_path / "features.json"
        fpath.write_text(json.dumps({"cost_position": False}), encoding="utf-8")

        with (
            patch("src.python.config.features.FEATURES_FILE", str(fpath)),
            patch("src.python.config.features.logger") as mock_logger,
            patch.dict(FEATURE_FLAGS, {}),
        ):
            load_feature_overrides()
            warnings = [text for text in self._rendered_warnings(mock_logger) if "无消费者" in text]

            assert warnings == []
            assert FEATURE_FLAGS["cost_position"] is False, "已登记开关的覆写仍须正常生效"

    @pytest.mark.unit
    def test_legacy_metrics_flags_warn_as_unknown(self, tmp_path):
        """旧 ``metrics_*`` 逐项键 → 按无消费者告警（不静默生效）。

        量化指标逐项开关已整体删除（指标始终全量渲染），用户 features.json 中残留的
        旧键必须可见地失效，否则「配置了却没效果」会以静默方式复现。
        """
        fpath = tmp_path / "features.json"
        fpath.write_text(json.dumps({"metrics_hhi": False, "metrics_beta": False}), encoding="utf-8")

        with (
            patch("src.python.config.features.FEATURES_FILE", str(fpath)),
            patch("src.python.config.features.logger") as mock_logger,
            patch.dict(FEATURE_FLAGS, {}),
        ):
            load_feature_overrides()
            warnings = [text for text in self._rendered_warnings(mock_logger) if "无消费者" in text]

            assert len(warnings) == 1
            assert "metrics_hhi" in warnings[0]
            assert "metrics_beta" in warnings[0]
            # 值仍加载（不报错），但没有任何消费点读取 → 告警是唯一反馈通道
            assert FEATURE_FLAGS["metrics_hhi"] is False


@pytest.mark.unit
class TestDeterministicSignalRegistry:
    """确定性信号模块的注册表口径（读侧注入 + 跨期沉淀双面单一开关）。"""

    @pytest.mark.unit
    def test_merged_switch_defaults_enabled(self):
        """确定性信号模块出厂默认开（实时注入侧原即为默认开，合并后延续）。"""
        from src.python.config.features import get_feature_defaults

        assert get_feature_defaults()["deterministic_signal"] is True


@pytest.mark.unit
class TestFactorCatalogSwitch:
    """因子目录开关（R-FCT-05 载体）：已转正入分析增强组、默认关、--experiment 不再接受。"""

    @pytest.mark.unit
    def test_registered_in_analysis_group_default_off(self):
        """已转正：注册于基金与风格组，出厂默认关，面板可见，开启影响产物自述。"""
        from src.python.config.features import GROUP_FUND_STYLE, feature_switch_registry

        switch = feature_switch_registry["factor_catalog"]
        assert switch.group == GROUP_FUND_STYLE
        assert switch.default is False
        assert switch.affects_report is True

    @pytest.mark.unit
    def test_experiment_token_rejected_after_promotion(self):
        """转正后 --experiment 不再接受——改由 --feature NAME=VALUE 或 features.json 控制。"""
        from src.python.config.features import resolve_experiment_flags

        on, unknown = resolve_experiment_flags(["factor_catalog"])
        assert on == set()
        assert unknown == ["factor_catalog"]

    @pytest.mark.unit
    def test_switch_label_present(self):
        """面板显示名登记（语义名与文档一致）。"""
        from src.python.config.features import feature_switch_registry

        assert feature_switch_registry["factor_catalog"].label == "因子目录"


class TestBannerLogLevel:
    """log_experimental_features 级别契约：INFO 提示，不占用 ERROR 统计。"""

    def test_banner_records_are_info_not_error(self, caplog):
        """横幅各行为 INFO 且零 ERROR——错误统计只保留真错误。"""
        import logging

        from src.python.config.features import (
            is_feature_enabled,
            log_experimental_features,
            set_feature_enabled,
        )

        flag = "decision_reflection"
        was_enabled = is_feature_enabled(flag)
        set_feature_enabled(flag, True)
        try:
            with caplog.at_level(logging.INFO, logger="invest"):
                log_experimental_features()
        finally:
            set_feature_enabled(flag, was_enabled)

        banner = [r for r in caplog.records if "⚗" in r.getMessage()]
        assert banner, "应产出 ⚗ 横幅日志"
        assert all(r.levelno == logging.INFO for r in banner)
        assert not any(r.levelno >= logging.ERROR for r in caplog.records), "横幅不得使用 ERROR 级别（会污染错误统计）"


class TestProsperityFrameworkPromotion:
    """景气度框架诊断实验转正锁定：摘除实验身份、作用域归市场与估值组且默认开（评分口径不变）。"""

    def test_promoted_to_analysis_default_on(self):
        from src.python.config.features import GROUP_MARKET

        sw = feature_switch_registry["prosperity_framework"]
        assert sw.group == GROUP_MARKET
        assert sw.default is True
        assert sw.affects_report is True
        assert not is_experimental_switch("prosperity_framework")


class TestHistoryAugmentedSwitches:
    """风险调整超额（risk_adjusted_excess）/ 危机回放（crisis_replay）注册断言。"""

    def test_registered_in_report_scope_groups_default_off(self):
        """注册于报告产物作用域（持仓与交易 / 市场与估值等组）、出厂默认关、声明影响报告产物、标签说明非空。"""
        from src.python.config import features

        expected_group = {
            "risk_adjusted_excess": features.GROUP_PORTFOLIO,
            "crisis_replay": features.GROUP_MARKET,
        }
        for flag, group in expected_group.items():
            definition = features.feature_switch_registry[flag]
            assert definition.group == group, f"{flag} 应属 {group}"
            assert definition.default is False, f"{flag} 出厂应默认关"
            assert definition.affects_report is True, f"{flag} 开启改变产物，须声明影响报告"
            assert definition.label.strip()
            assert definition.desc.strip()

    def test_defaults_projection_off(self):
        """出厂默认值投影读取 API 同步为关（features.json 未覆写时的行为）。"""
        from src.python.config.features import get_feature_defaults

        defaults = get_feature_defaults()
        assert defaults["risk_adjusted_excess"] is False
        assert defaults["crisis_replay"] is False


class TestPublicSwitchVocabulary:
    """公开开关词表与解析器：CLI 与 TUI 共用一份词表（渠道不引私有符号）。"""

    def test_parse_switch_value_uses_shared_vocabulary(self):
        """真值来源词表：词表内每个取值都能解析为对应布尔，词表外返回 None。"""
        from src.python.config.features import (
            SWITCH_FALSE_TOKENS,
            SWITCH_TRUE_TOKENS,
            parse_switch_value,
        )

        for token in SWITCH_TRUE_TOKENS:
            assert parse_switch_value(token) is True, token
            assert parse_switch_value(f"  {token.upper()}  ") is True, token
        for token in SWITCH_FALSE_TOKENS:
            assert parse_switch_value(token) is False, token
        for token in ("maybe", "", "onoff", "2"):
            assert parse_switch_value(token) is None, token

    def test_override_and_value_parser_agree(self):
        """`NAME=VALUE` 解析结果与单值解析器一致（同一词表，不会两处口径漂移）。"""
        from src.python.config.features import parse_switch_override, parse_switch_value

        for token in ("on", "yes", "0", "disable"):
            name, value = parse_switch_override(f"cost_position={token}")
            assert name == "cost_position"
            assert value is parse_switch_value(token)


class TestDefaultEnabledLlmAccessor:
    """公开 `default_enabled_llm()`：展示层取出厂默认不引私有模板。"""

    def test_returns_enabled_llm_defaults_copy(self):
        """返回值等于 enabled_llm 出厂默认，且是副本（改动不污染全局默认）。"""
        from src.python.config import default_enabled_llm
        from src.python.config._llm_settings_defaults import _DEFAULT_LLM_SETTINGS

        expected = _DEFAULT_LLM_SETTINGS["enabled_llm"]
        got = default_enabled_llm()
        assert got == expected
        got["__probe__"] = True
        assert "__probe__" not in default_enabled_llm()

    def test_covers_registered_llm_modules(self):
        """注册表 LLM 模块的后缀都出现在默认映射里（新增模块须同步默认值）。"""
        from src.python.config import default_enabled_llm
        from src.python.core.registry import get_llm_module_names

        assert set(get_llm_module_names()) <= set(default_enabled_llm())


class TestRenderOverrides:
    """覆写文件重建：逐项注释取自注册表，末项不带尾逗号且整体可解析。"""

    def test_each_line_carries_registry_note(self):
        from src.python.config.features import _render_overrides
        from src.python.core.json_comments import loads

        text = _render_overrides({"decision_reflection": True, "summary_highlights": False})
        assert "决策跨期反思闭环" in text
        assert "首页执行摘要卡" in text
        assert loads(text) == {"decision_reflection": True, "summary_highlights": False}

    def test_last_entry_has_no_trailing_comma(self):
        from src.python.config.features import _render_overrides

        text = _render_overrides({"report_qa": True, "cost_lots": True})
        entries = [line for line in text.splitlines() if line.strip().startswith('"')]
        assert len(entries) == 2
        assert not entries[-1].split("//")[0].rstrip().endswith(",")
        assert entries[0].split("//")[0].rstrip().endswith(",")

    def test_unknown_key_rendered_without_note(self):
        from src.python.config.features import _render_overrides
        from src.python.core.json_comments import loads

        text = _render_overrides({"not_a_registered_flag": True})
        entries = [line for line in text.splitlines() if line.strip().startswith('"')]
        assert len(entries) == 1
        assert "//" not in entries[0]
        assert loads(text) == {"not_a_registered_flag": True}
