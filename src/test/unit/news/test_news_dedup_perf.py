"""新闻去重的比较成本约束 —— 判定不变，只减少无望比较的代价。

「去重与关联」是报告耗时的主项之一：`_dedup_by_title` 对已保留项逐对做
相似度比较（O(n²)），而绝大多数对远低于门槛。这里锁两条契约：

1. **判定等价**：字符多重集上界预筛 + 比较串缓存不得改变任何合并结果
   （与「无预筛、无缓存」的参考实现对同一语料输出逐条相同）；
2. **上界有效性**：`_multiset_upper_bound` 必须是真实 ratio 的上界（判定安全的
   前提），且明显低于门槛的对应被预筛拦下（保证优化真的生效）。
"""

from __future__ import annotations

import random
from difflib import SequenceMatcher

import pytest

from src.python.providers import news_dedup_rules as rules
from src.python.providers.news_dedup import _dedup_by_title

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


def _corpus(n: int = 120) -> list[dict]:
    words = (
        "证监会 央行 美联储 英伟达 比亚迪 沪深 北向 新能源 半导体 光伏 医药 白酒 券商 地产 出口 CPI PPI 国债".split()
    )
    rng = random.Random(7)
    items = []
    for _ in range(n):
        title = "".join(rng.sample(words, rng.randint(3, 5))) + str(rng.randint(100, 9999))
        items.append({"title": title, "_source": rng.choice(["sina", "eastmoney", "cls"])})
    return items


def _legacy_dedup(items: list[dict], monkeypatch) -> list[dict]:
    """对照组：不经多重集预筛与比较串缓存，直接用完整 ratio 判定跑同一流程。

    直接替换模块级 `_ratio_of_norms_bounded` / `_overlap_of_norms`，不重写判定规则
    ——重写规则必然与生产实现漂移，对照就失去意义。
    """
    from src.python.providers import news_dedup as dedup_mod

    def legacy_bounded(a: str, b: str, threshold: float) -> float:
        x = rules._ENG_PLACEHOLDER.sub(rules._eng_len_placeholder, rules._RATIO_CLEAN.sub("", a))
        y = rules._ENG_PLACEHOLDER.sub(rules._eng_len_placeholder, rules._RATIO_CLEAN.sub("", b))
        upper = max(
            SequenceMatcher(None, x, y).quick_ratio(),
            SequenceMatcher(None, y, x).quick_ratio(),
        )
        return upper if upper < threshold else rules._ratio_of_norms(a, b)

    monkeypatch.setattr(dedup_mod, "_ratio_of_norms_bounded", legacy_bounded)
    monkeypatch.setattr(
        dedup_mod,
        "_overlap_of_norms",
        lambda a, b: len(rules._extract_entity_bigrams(a) & rules._extract_entity_bigrams(b)),
    )
    return _dedup_by_title(items)


class TestDecisionEquivalence:
    def test_prefilter_does_not_change_merge_result(self, monkeypatch):
        """同一语料，上界预筛版与完整 ratio 判定版的保留集合逐条一致。"""
        monkeypatch.setenv("INVEST_DEDUP_COLLECT_ANCHORS", "0")
        items = _corpus(150)
        optimized = [it["title"] for it in _dedup_by_title(items)]
        legacy = [it["title"] for it in _legacy_dedup(items, monkeypatch)]
        assert optimized == legacy

    def test_cached_paths_return_same_values(self):
        """缓存包装与直算结果一致（避免缓存键/返回值污染判定）。"""
        a = "英国央行如期维持利率不变"
        b = "英国央行以6比3票数维持利率不变"
        assert rules._ratio_ready(a) == rules._ratio_ready(a)
        assert rules._ratio_of_norms(a, b) == pytest.approx(rules._ratio_of_norms(a, b), abs=1e-12)
        assert rules._extract_entity_bigrams_cached(a) == frozenset(rules._extract_entity_bigrams(a))


class TestMultisetUpperBound:
    @pytest.mark.parametrize(
        "a,b",
        [
            ("英国央行如期维持利率不变", "英国央行以6比3票数维持利率不变"),
            ("英伟达发布新一代芯片", "某公司宣布回购股份"),
            ("沪深300指数上涨", "沪深300指数下跌"),
            ("", "非空标题"),
        ],
    )
    def test_bound_is_not_below_real_ratio(self, a, b):
        real = rules._ratio_of_norms(a, b) if (a and b) else 0.0
        bound = rules._multiset_upper_bound(a, b)
        assert bound + 1e-12 >= real

    def test_disparate_pair_skipped_by_bound(self):
        """上界低于门槛 → `_ratio_of_norms_bounded` 直接返回上界，不构造 SequenceMatcher。"""
        a = "英伟达发布新一代GPU架构与算力平台"
        b = "白酒板块午后走弱消费股承压"
        threshold = rules._CROSS_CANDIDATE_RATIO
        assert rules._multiset_upper_bound(a, b) < threshold
        assert rules._ratio_of_norms_bounded(a, b, threshold) < threshold

    def test_bound_matches_quick_ratio_order(self):
        """上界应不小于 quick_ratio（后者本身是 ratio 上界），二者量级一致。"""
        a = rules._ratio_ready("证监会发布新规支持科技企业上市")
        b = rules._ratio_ready("证监会发布新规支持科技创新企业上市")
        quick = max(
            SequenceMatcher(None, a, b).quick_ratio(),
            SequenceMatcher(None, b, a).quick_ratio(),
        )
        bound = rules._multiset_upper_bound("证监会发布新规支持科技企业上市", "证监会发布新规支持科技创新企业上市")
        assert bound + 1e-12 >= quick
