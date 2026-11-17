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


class TestEntityFirstGate:
    """实体重叠前置关卡：overlap == 0 的对不构造相似度（判定不变，只省代价）。

    合法性前提：**所有合并规则都要求 overlap ≥ 1**（①≥4 / ②≥1 / ③≥3 / ④≥1 / ⑤≥2），
    唯一不需要实体的是 ⑥ 子串包含（本类末条用例守它没被连带跳过）。
    """

    _DISJOINT = [
        {"title": "甲辰科技有限公司：半年度净利润同比增长 35%", "_source": "sina"},
        {"title": "乙酉新能源：获机构上调评级", "_source": "eastmoney"},
        {"title": "丙午半导体宣布回购计划", "_source": "cls"},
        {"title": "丁未医药：新产品线投产", "_source": "sina"},
    ]

    def test_zero_overlap_pairs_skip_similarity(self, monkeypatch):
        """实体互不重叠且无共享窗口的标题：连重叠计算都不发生，且全部保留。"""
        monkeypatch.setenv("INVEST_DEDUP_COLLECT_ANCHORS", "0")
        from src.python.providers import news_dedup as dedup_mod

        computed: list[tuple[str, str]] = []
        compared: list[tuple[str, str]] = []
        real_ratio = dedup_mod._ratio_of_norms_bounded
        real_overlap = dedup_mod._overlap_of_norms

        def _ratio_spy(a: str, b: str, threshold: float) -> float:
            computed.append((a, b))
            return real_ratio(a, b, threshold)

        def _overlap_spy(a: str, b: str) -> int:
            compared.append((a, b))
            return real_overlap(a, b)

        monkeypatch.setattr(dedup_mod, "_ratio_of_norms_bounded", _ratio_spy)
        monkeypatch.setattr(dedup_mod, "_overlap_of_norms", _overlap_spy)
        kept = _dedup_by_title(list(self._DISJOINT))

        assert len(kept) == len(self._DISJOINT)
        assert compared == []
        assert computed == []

    def test_merge_result_matches_baseline_when_pairs_overlap(self, monkeypatch):
        """共享实体的语料：跳过零重叠对不得改变保留集合（与本文件基线对照逐条比）。"""
        monkeypatch.setenv("INVEST_DEDUP_COLLECT_ANCHORS", "0")
        items = _corpus(80) + [
            {"title": "英伟达发布新一代 GPU 算力平台，机构上调目标价", "_source": "sina"},
            {"title": "英伟达发布新一代GPU算力平台 机构上调目标价", "_source": "eastmoney"},
        ]
        optimized = [it["title"] for it in _dedup_by_title(items)]
        legacy = [it["title"] for it in _legacy_dedup(items, monkeypatch)]
        assert optimized == legacy

    def test_substring_path_survives_zero_overlap(self, monkeypatch):
        """子串包含（⑥）不依赖实体重叠，前置关卡不得把它一并跳过。"""
        monkeypatch.setenv("INVEST_DEDUP_COLLECT_ANCHORS", "0")
        from src.python.providers import news_dedup as dedup_mod

        short = "净利润同比增长目标价"
        long_title = "净利润同比增长目标价上调至 480 元"
        assert rules._overlap_of_norms(short, long_title) == 0, "本用例前提：零实体重叠"
        computed: list[int] = []
        monkeypatch.setattr(
            dedup_mod, "_ratio_of_norms_bounded", lambda a, b, t: computed.append(1) or 0.0
        )

        kept = _dedup_by_title(
            [
                {"title": long_title, "_source": "sina"},
                {"title": short, "_source": "eastmoney"},
            ]
        )

        assert [it["title"] for it in kept] == [long_title]
        assert computed == []
