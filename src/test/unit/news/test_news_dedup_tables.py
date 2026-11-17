"""新闻去重词表（`providers/_news_dedup_tables.py`）——数据表完整性与判定语义。

这三张表是去重的「业务知识」：模板词（去虚高重叠）、反向词对（防方向对立误合并）、
事件词组（bg=3 档的事件一致性）。表本身没有代码，坏掉不会抛异常，只会静默改变
合并结果——故用结构不变量 + 判定语义双向锁：

  - 结构不变量：成员非空、无空白、对/组内不重复、无反身对；
  - 判定语义：`_has_opposite_direction` 要求「一正一反分属两标题」，`share_event_group`
    要求「两标题各自命中同组词」——单成员事件组因此只在两侧都命中时成立。
"""

from __future__ import annotations

import pytest

from src.python.providers._news_dedup_tables import _EVENT_GROUPS, _OPPOSITE_PAIRS, _STOP_BIGRAMS
from src.python.providers.news_dedup_rules import _has_opposite_direction, share_event_group

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


class TestStopBigramsTable:
    def test_entries_are_meaningful_terms(self):
        assert all(len(term) >= 2 for term in _STOP_BIGRAMS)
        assert all(term == term.strip() for term in _STOP_BIGRAMS), "模板词不得含首尾空白"

    def test_stop_terms_are_masked_before_bigram_overlap(self):
        """模板词不进实体 bigram：两个标题只共享模板词时 overlap 为 0。"""
        from src.python.providers.news_dedup_rules import _overlap_of_norms

        sample = sorted(term for term in _STOP_BIGRAMS if len(term) == 2)[0]
        assert _overlap_of_norms(f"甲公司{sample}", f"乙公司{sample}") == 0


class TestOppositePairsTable:
    def test_pairs_are_distinct_two_tuples(self):
        assert all(len(pair) == 2 for pair in _OPPOSITE_PAIRS)
        assert all(pair[0] and pair[1] for pair in _OPPOSITE_PAIRS)
        assert all(pair[0] != pair[1] for pair in _OPPOSITE_PAIRS), "反身对永远不成立，属死条目"
        assert len(set(_OPPOSITE_PAIRS)) == len(_OPPOSITE_PAIRS)

    def test_direction_detection_needs_both_sides(self):
        w1, w2 = _OPPOSITE_PAIRS[0]
        assert _has_opposite_direction(f"某标的{w1}", f"某标的{w2}")
        assert not _has_opposite_direction(f"某标的{w1}", f"某标的{w1}"), "同向不判对立"
        assert not _has_opposite_direction("无关内容", f"某标的{w2}")


class TestEventGroupsTable:
    def test_groups_are_non_empty_with_distinct_members(self):
        assert all(len(group) >= 1 for group in _EVENT_GROUPS)
        assert all(len(set(group)) == len(group) for group in _EVENT_GROUPS), "组内词重复会虚增命中"
        assert len(set(_EVENT_GROUPS)) == len(_EVENT_GROUPS)

    def test_shared_group_member_is_required_on_both_sides(self):
        rich = max(_EVENT_GROUPS, key=len)
        word = rich[0]
        assert share_event_group(f"公司{word}进展", f"{word}公告")
        assert not share_event_group(f"公司{word}进展", "无关市场行情")

    def test_different_groups_do_not_share_event(self):
        """跨组词不构成同一事件（组间互斥是 bg=3 档判据的前提）。"""
        first, second = _EVENT_GROUPS[0][0], _EVENT_GROUPS[-1][0]
        assert not share_event_group(f"公司{first}", f"公司{second}")
