"""功能开关注册表（`config/_feature_registry.py`）——分组/面板/编号/实验项的派生一致性。

注册表是「开关长什么样」的唯一事实位：分组、面板归属、面板编号、实验生命周期都由
它派生。这里的用例只断言**结构关系**（集合相等/子集/连续序号/单向派生），不写死
开关条数——新增开关是良性变更，不该把用例打红。
"""

from __future__ import annotations

import pytest

from src.python.config._feature_registry import (
    DOMAIN_LABELS,
    DOMAIN_ORDER,
    GROUP_DOMAIN,
    GROUP_LABELS,
    GROUP_ORDER,
    PANEL_GROUPS,
    experimental_flags,
    feature_switch_registry,
    is_experimental_switch,
    panel_option_numbers,
    panel_switches,
    switches_in_group,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_config]


class TestGroupAndDomainTables:
    def test_group_order_covers_every_label(self):
        assert set(GROUP_ORDER) == set(GROUP_LABELS)

    def test_domain_order_covers_every_label_and_hints_are_known(self):
        """域序即域标签全集，且 Web 域提示词只引用已声明域。"""
        from src.python.config._feature_registry import DOMAIN_HINTS

        assert set(DOMAIN_ORDER) == set(DOMAIN_LABELS)
        assert set(DOMAIN_HINTS) <= set(DOMAIN_ORDER)

    def test_every_group_maps_to_a_known_domain(self):
        assert set(GROUP_DOMAIN) == set(GROUP_ORDER)
        assert set(GROUP_DOMAIN.values()) <= set(DOMAIN_LABELS)


class TestPanelDerivation:
    def test_every_panel_group_is_declared_and_not_listed_twice(self):
        for panel, groups in PANEL_GROUPS.items():
            assert set(groups) <= set(GROUP_LABELS), f"{panel} 引用了未登记分组"
            assert len(set(groups)) == len(groups), f"{panel} 的分组重复出现"

    def test_panels_cover_all_groups(self):
        """每个分组都必须落在某个面板里，否则该组开关在界面上无处可达。"""
        covered = set().union(*(set(groups) for groups in PANEL_GROUPS.values()))
        assert covered == set(GROUP_ORDER)

    def test_panel_switches_follow_group_order_within_panel(self):
        for panel, groups in PANEL_GROUPS.items():
            flags = [flag for flag, _definition in panel_switches(panel)]
            expected = [
                flag
                for group in groups
                for flag, definition in feature_switch_registry.items()
                if definition.group == group and definition.panel_visible
            ]
            assert flags == expected

    def test_panel_invisible_switches_never_reach_the_panel(self):
        """`panel_visible=False`（默认常开的机制项/自动项）不在任何面板上屏。"""
        hidden = {flag for flag, definition in feature_switch_registry.items() if not definition.panel_visible}
        shown = set().union(*(set(flag for flag, _definition in panel_switches(p)) for p in PANEL_GROUPS))
        assert not (hidden & shown)

    def test_panel_option_numbers_are_continuous_and_unique(self):
        for panel in PANEL_GROUPS:
            numbered = panel_option_numbers(panel)
            assert [number for number, _flag, _definition in numbered] == list(range(1, len(numbered) + 1))
            assert len({flag for _number, flag, _definition in numbered}) == len(numbered)
            assert [flag for _number, flag, _definition in numbered] == [
                flag for flag, _definition in panel_switches(panel)
            ]


class TestSwitchesInGroup:
    def test_returns_only_members_of_that_group(self):
        for group in GROUP_ORDER:
            members = switches_in_group(group)
            assert all(definition.group == group for _flag, definition in members)
            assert {flag for flag, _definition in members} == {
                flag for flag, definition in feature_switch_registry.items() if definition.group == group
            }

    def test_unknown_group_returns_empty(self):
        assert switches_in_group("不存在的分组") == []


class TestExperimentalLifecycle:
    def test_experimental_list_derives_from_registry_field(self):
        expected = [flag for flag, definition in feature_switch_registry.items() if definition.experimental]
        assert [flag for flag, _definition in experimental_flags()] == expected

    def test_is_experimental_switch_matches_registry_and_unknown_is_false(self):
        for flag, definition in feature_switch_registry.items():
            assert is_experimental_switch(flag) is definition.experimental
        assert is_experimental_switch("不存在的开关") is False
