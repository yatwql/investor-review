"""新闻去重实现分片：标题判定算法、锚点追加写、维护压缩。

判定口径：
- 写侧只追加（不读旧文件）；同批内按 (source,title) 去重，跨轮重复由校准工具按键去重；
- 维护压缩按「每 key 最新 + 保留期」双条件裁剪（评估默认执行，报告路径不压缩）。
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime
from unittest.mock import patch

import pytest

from src.python.providers.news_dedup import _record_anchor

pytestmark = [pytest.mark.unit, pytest.mark.unit_news]


@pytest.fixture(autouse=True)
def _enable_anchor_collection(monkeypatch):
    """锚点采集默认开启；本文件显式固定为开启，避免外部环境变量影响断言。"""
    monkeypatch.setenv("INVEST_DEDUP_COLLECT_ANCHORS", "1")


def test_anchor_collection_defaults_on(monkeypatch):
    """采集默认开启（诊断数据持续积累）；仅显式设 0 才关闭。"""
    from src.python.providers.news_dedup import _anchor_collection_enabled

    monkeypatch.delenv("INVEST_DEDUP_COLLECT_ANCHORS", raising=False)
    assert _anchor_collection_enabled() is True


class TestFlushAnchorsDedup(unittest.TestCase):
    """_flush_anchors 追加写语义：批内去重、跨轮追加由校准工具按键去重。

    设计取舍：写侧只追加、不读旧文件（避免每轮解析 39MB）；同一标题对跨轮
    重复由 ``eval-dedup-threshold.py::load_anchors`` 按键去重（保留最早一条），
    因此诊断结论不受重复行影响。
    """

    pytestmark = [
        pytest.mark.unit,
        pytest.mark.unit_news,
    ]

    def setUp(self) -> None:
        """隔离锚点路径并清空内存记录，避免污染真实 calibration 文件。"""
        import tempfile
        from unittest.mock import patch

        self._tmpdir = tempfile.mkdtemp()
        self._anchor_path = os.path.join(self._tmpdir, "anchors.jsonl")
        from src.python.providers import news_dedup

        # 隔离写入路径：patch 模块常量，确保测试不触碰真实 data/calibration/
        self._path_patch = patch("src.python.providers.news_dedup._ANCHOR_PATH", self._anchor_path)
        self._path_patch.start()
        self._collect_patch = patch.dict(os.environ, {"INVEST_DEDUP_COLLECT_ANCHORS": "1"})
        self._collect_patch.start()
        news_dedup._ANCHOR_RECORDS = []

    def tearDown(self) -> None:
        """恢复 patch。"""
        self._collect_patch.stop()
        self._path_patch.stop()

    def _record_cross_skip(self, title_a: str, title_b: str) -> None:
        """记录一条 cross_skip 锚点（进入候选区但未合并的典型记录）。"""

        _record_anchor(
            {
                "source_a": "东方财富",
                "source_b": "新浪财经",
                "title_a": title_a,
                "title_b": title_b,
                "ratio": 0.312,
                "bigram_overlap": 2,
                "decision": False,
                "rule": "cross_skip",
                "ts": "",
            }
        )

    def test_collection_disabled_skips_record_and_flush(self) -> None:
        """显式关闭采集：_record_anchor 不积累、_flush_anchors 不创建文件。"""
        from src.python.providers import news_dedup

        with patch.dict(os.environ, {"INVEST_DEDUP_COLLECT_ANCHORS": "0"}):
            self._record_cross_skip("新闻A", "新闻B")
            self.assertEqual(news_dedup._ANCHOR_RECORDS, [])
            news_dedup._flush_anchors()
        self.assertFalse(os.path.exists(self._anchor_path))

    def test_same_pair_within_batch_flushed_once(self) -> None:
        """同一批内同一对新闻只写一次（批内去重）。"""
        from src.python.providers.news_dedup import _flush_anchors

        self._record_cross_skip("新闻A", "新闻B")
        self._record_cross_skip("新闻A", "新闻B")
        _flush_anchors()
        with open(self._anchor_path, encoding="utf-8") as f:
            self.assertEqual(len(f.readlines()), 1)

    def test_cross_run_duplicates_are_deduped_by_calibration(self) -> None:
        """跨轮重复会追加（写侧不读旧文件），但校准工具按键去重为一对。"""
        from src.python.providers.news_dedup import _flush_anchors
        from src.test._script_loader import load_script

        self._record_cross_skip("新闻A", "新闻B")
        _flush_anchors()
        self._record_cross_skip("新闻A", "新闻B")
        _flush_anchors()
        with open(self._anchor_path, encoding="utf-8") as f:
            self.assertEqual(len(f.readlines()), 2, "写侧只追加，跨轮重复保留在文件里")

        tool = load_script("eval-dedup-threshold.py", module_name="_eval_dedup_threshold_under_test")
        assert len(tool.load_anchors(self._anchor_path)) == 1, "校准工具应按键去重"

    def test_different_pairs_still_appended(self) -> None:
        """不同 (source,title) 对正常追加，不被误去重。"""
        from src.python.providers.news_dedup import _flush_anchors

        self._record_cross_skip("新闻A", "新闻B")
        _flush_anchors()
        self._record_cross_skip("新闻C", "新闻D")
        _flush_anchors()
        with open(self._anchor_path, encoding="utf-8") as f:
            self.assertEqual(len(f.readlines()), 2)


class TestDedupGenericTokenVeto(unittest.TestCase):
    """bg=2 梯度泛词否决表（ai/etf/cm/gb/ce/pcb/gdp 不作专名证据）。

    语料依据：锚点 7.8 万对实测——靠这些词过闸的 bg=2 合并绝大多数为跨主体
    误合并（不同基金各自行情/不同指数/“20cm”俚语/CE 认证/跨经济体 GDP 数据）；
    CPI/PPI/IPO/AMD 类真发布会与公司缩写不在表内、照常作专名证据。
    """

    def _make_item(self, title: str, source: str = "东方财富") -> dict:
        return {"title": title, "_source": source, "url": "http://x.com/" + title[:10]}

    def test_generic_tokens_vetoed_but_indicator_acronyms_allowed(self) -> None:
        """否决词全部无效；非否决短缩写（cpi 等）与混合集保留。"""
        from src.python.providers.news_dedup_rules import has_proper_noun_token, proper_noun_tokens

        for word in ("ai", "etf", "cm", "gb", "ce", "pcb", "gdp"):
            self.assertEqual(proper_noun_tokens({word, "芯片"}), [], f"泛词应被否决: {word}")
        self.assertFalse(has_proper_noun_token({"ai", "芯片"}))
        self.assertTrue(has_proper_noun_token({"cpi", "芯片"}))
        self.assertEqual(proper_noun_tokens({"etf", "cpi"}), ["cpi"])

    def test_bg2_merge_blocked_by_generic_veto(self) -> None:
        """真实锚点样本：黄金 ETF 两报——否决表置空即合并，现行否决表则保留两条。"""
        from src.python.providers import news_dedup_rules
        from src.python.providers.news_aggregator import _dedup_by_title
        from src.python.providers.news_dedup_rules import (
            _CROSS_BG2_RATIO,
            _extract_entity_bigrams,
            _normalize_title,
            _pair_similarity,
        )

        items = [
            self._make_item("全球黄金ETF资金净流入创纪录 黄金短期交易逻辑出现变化", "第一财经"),
            self._make_item("8月全球黄金ETF，净流入创新高！后市如何配置？机构研判", "同花顺"),
        ]
        # 自证这对标题确实走 bg=2 证据面：ratio 达梯度门槛、overlap=2、共享集含否决词
        ratio, overlap = _pair_similarity(items[0]["title"], items[1]["title"])
        self.assertGreaterEqual(ratio, _CROSS_BG2_RATIO)
        self.assertGreaterEqual(overlap, 2)
        shared = _extract_entity_bigrams(_normalize_title(items[0]["title"])) & _extract_entity_bigrams(
            _normalize_title(items[1]["title"])
        )
        self.assertLessEqual({"etf"}, shared)
        with patch.object(news_dedup_rules, "_GENERIC_TOKENS", frozenset()):
            self.assertEqual(len(_dedup_by_title([dict(i) for i in items])), 1)  # 否决表空 → 原证据合并
        self.assertEqual(len(_dedup_by_title([dict(i) for i in items])), 2)  # 现行否决 → 保留两条

    def test_gdp_generic_veto_blocks_cross_economy_pair(self) -> None:
        """校准实证样本：沙特与欧元区 GDP 数据发布——共享 gdp 不作专名证据，不合并。"""
        from src.python.providers import news_dedup_rules
        from src.python.providers.news_aggregator import _dedup_by_title
        from src.python.providers.news_dedup_rules import (
            _CROSS_BG2_RATIO,
            _extract_entity_bigrams,
            _normalize_title,
            _pair_similarity,
        )

        items = [
            self._make_item("沙特阿拉伯第二季度GDP初值同比下降4.8%", "东方财富"),
            self._make_item("欧元区二季度GDP季环比初值 0.4%，预期 0.2%，前值 -0.2%。", "华尔街见闻"),
        ]
        ratio, overlap = _pair_similarity(items[0]["title"], items[1]["title"])
        self.assertGreaterEqual(ratio, _CROSS_BG2_RATIO)
        self.assertGreaterEqual(overlap, 2)
        shared = _extract_entity_bigrams(_normalize_title(items[0]["title"])) & _extract_entity_bigrams(
            _normalize_title(items[1]["title"])
        )
        self.assertIn("gdp", shared)
        with patch.object(news_dedup_rules, "_GENERIC_TOKENS", frozenset({"ai", "etf", "cm", "gb", "ce", "pcb"})):
            self.assertEqual(len(_dedup_by_title([dict(i) for i in items])), 1)  # 旧表（无 gdp）→ 误合并
        self.assertEqual(len(_dedup_by_title([dict(i) for i in items])), 2)  # 现行表 → 保留两条

    def test_rules_fingerprint_covers_generic_token_table(self) -> None:
        """泛词表入规则指纹：词表变动必须换锚点时代（分代依据不遗漏）。"""
        from src.python.providers import news_dedup_rules
        from src.python.providers.news_dedup_rules import _rules_fingerprint

        base = _rules_fingerprint()
        with patch.object(
            news_dedup_rules, "_GENERIC_TOKENS", frozenset({"ai", "etf", "cm", "gb", "ce", "pcb", "xyz"})
        ):
            self.assertNotEqual(_rules_fingerprint(), base)


class TestDedupEventGroupGate(unittest.TestCase):
    """bg=3 下限档事件一致性判据（同主体不同事件对不合并）。

    语料依据：2026-10-20 锚点回放——中际旭创「暗盘跌 vs 资金抢筹 vs 成交额」
    两两互并、SK海力士「盘前跌 vs 上调目标价」均为同主体不同事件的误合并；
    同组词（立案/调查/留置/被查）互认保住真重复；职务/身份词（董事长/总经理）
    不入词表（跨事件普遍命中，会把中投副总任命与卫通副总离任误连）。
    """

    def _make_item(self, title: str, source: str = "东方财富") -> dict:
        return {"title": title, "_source": source, "url": "http://x.com/" + title[:10]}

    def test_same_subject_different_event_not_merged(self) -> None:
        """校准实证：中际旭创暗盘跌 vs 资金抢筹——共享 3 bigram 但事件不一致，不合并。"""
        from src.python.providers.news_aggregator import _dedup_by_title
        from src.python.providers.news_dedup_rules import (
            _CROSS_BIGRAM_MIN,
            _CROSS_CANDIDATE_RATIO,
            _extract_entity_bigrams,
            _normalize_title,
            _pair_similarity,
        )

        items = [
            self._make_item("中际旭创港股暗盘跌1.84%", "财联社"),
            self._make_item("中际旭创，18.89亿元资金抢筹，A股第一名", "东方财富"),
        ]
        ratio, overlap = _pair_similarity(items[0]["title"], items[1]["title"])
        self.assertGreaterEqual(ratio, _CROSS_CANDIDATE_RATIO)
        self.assertEqual(overlap, _CROSS_BIGRAM_MIN)  # 自证恰为 bg=3 下限档（判据适用面）
        shared = _extract_entity_bigrams(_normalize_title(items[0]["title"])) & _extract_entity_bigrams(
            _normalize_title(items[1]["title"])
        )
        self.assertGreaterEqual(len(shared), _CROSS_BIGRAM_MIN)
        self.assertEqual(len(_dedup_by_title([dict(i) for i in items])), 2)  # 事件不一致 → 保留两条

    def test_same_event_group_interchange_keeps_merge(self) -> None:
        """同组词互认：立案调查留置 vs 被查——同事件类型，仍合并（不误杀）。"""
        from src.python.providers.news_aggregator import _dedup_by_title
        from src.python.providers.news_dedup_rules import _CROSS_BIGRAM_MIN, _CROSS_CANDIDATE_RATIO, _pair_similarity

        items = [
            self._make_item("华锦股份通报副总经理闫增辉被立案调查并留置", "证券时报"),
            self._make_item("000059副总经理被查", "财联社"),
        ]
        ratio, overlap = _pair_similarity(items[0]["title"], items[1]["title"])
        self.assertGreaterEqual(ratio, _CROSS_CANDIDATE_RATIO)
        self.assertEqual(overlap, _CROSS_BIGRAM_MIN)
        self.assertEqual(len(_dedup_by_title([dict(i) for i in items])), 1)  # 同事件 → 合并

    def test_same_event_still_merged(self) -> None:
        """共享回购事件词：兆易创新提议回购 vs 集体公告——真重复仍合并。"""
        from src.python.providers.news_aggregator import _dedup_by_title

        items = [
            self._make_item("兆易创新：董事长朱一明提议回购10亿-20亿元A股股份用于注销", "证券时报"),
            self._make_item("603986，董事长提议不超20亿元回购、注销！又一批A股公司，集体公告", "同花顺"),
        ]
        self.assertEqual(len(_dedup_by_title([dict(i) for i in items])), 1)

    def test_event_group_membership(self) -> None:
        """组内互认（立案/被查）；跨组不互认（袭击 vs 回购）；职务词不触发。"""
        from src.python.providers.news_dedup_rules import share_event_group

        self.assertTrue(share_event_group("华锦副总被立案调查", "某公司副总被查"))
        self.assertTrue(share_event_group("兆易创新提议回购", "又一批公司集体回购公告"))
        self.assertFalse(share_event_group("以色列袭击加沙清真寺", "某公司拟回购股份"))
        self.assertFalse(share_event_group("陈忠任中投公司副总经理", "中国卫通副总经理退休离任"))
        self.assertFalse(share_event_group("苹果股价创历史新高", "可口可乐创历史新高"))  # 泛状态词不入表


class TestDedupNumericTokenNotProperNoun(unittest.TestCase):
    """纯数字共享不算专名证据（bg=2 梯度不再为数字误合并）。

    背景：旧判定 ``^[a-z0-9]+$`` 把纯数字 token 也算专名证据，于是只共享数字的
    无关标题（如战机型号数字、榜单序号各自对应的两条不同新闻）会靠 bg=2 梯度
    合并。锚点校准实测：收紧前 cross_merge_bg2 里 24 对仅靠数字证据成立。
    """

    def _make_item(self, title: str, source: str = "东方财富") -> dict:
        return {"title": title, "_source": source, "url": "http://x.com/" + title[:10]}

    def test_token_predicate_requires_letter(self) -> None:
        """专名证据判定：纯数字不算，含字母/虚拟专名才算。"""
        from src.python.providers.news_dedup_rules import _TOKEN_LIKE

        for digits in ("100", "4400", "35", "20"):
            self.assertIsNone(_TOKEN_LIKE.match(digits), f"纯数字不应算专名证据: {digits}")
        for proper in ("cpi", "5g", "kse100", "_tk:mlcc"):
            self.assertIsNotNone(_TOKEN_LIKE.match(proper), f"应算专名证据: {proper}")

    def test_shared_digits_only_not_merged(self) -> None:
        """共享数字 35（战机型号）+ 模板 bigram 的不同事件不合并。"""
        from src.python.providers.news_aggregator import _dedup_by_title

        items = [
            self._make_item("美国F-35战机在加州海军陆战队航空站附近坠毁", "新浪财经"),
            self._make_item("伊称摧毁3架美军F35战机", "华尔街见闻"),
        ]
        self.assertEqual(len(_dedup_by_title(items)), 2)

    def test_shared_digits_in_list_marker_not_merged(self) -> None:
        """共享数字 20（榜单序号/版本号）的不同事件不合并。"""
        from src.python.providers.news_aggregator import _dedup_by_title

        items = [
            self._make_item("博时ETF王者挑战赛丨第三周周榜TOP20正式公布", "新浪财经"),
            self._make_item("OpenClaw 2.0正式发布", "东方财富"),
        ]
        self.assertEqual(len(_dedup_by_title(items)), 2)


class TestDedupOppositeDirectionExtended(unittest.TestCase):
    """方向对立词对扩充（站稳/跌破、走高/走低、上探/下探、回升/回落、走软/走强）。

    跨源候选区内，共享实体 + 方向相反分属两标题 → 不合并（否则"金价站稳4000"
    与"黄金跌破4000"会被当作同一条改写重复）。该防护只在候选区（ratio < 0.50）
    生效：ratio ≥ 0.50 的高相似对常在同标题内同时提到两个方向词（如"49股涨停
    2股跌停"），把防护扩到安全区会误拦真重复（实测 6 对里 4 对属真重复）。
    """

    def _make_item(self, title: str, source: str = "东方财富") -> dict:
        return {"title": title, "_source": source, "url": "http://x.com/" + title[:10]}

    def test_extended_pairs_detected(self) -> None:
        """新方向对能被检出（一正一反分属两标题）。"""
        from src.python.providers.news_dedup_rules import _has_opposite_direction

        cases = [
            ("金价站稳4000美元上方", "现货黄金跌破4000美元关口"),
            ("算力硬件板块持续走高", "国际油价持续走低"),
            ("金价上探4400美元", "黄金下探4200美元"),
            ("存储芯片概念回升", "数字媒体板块回落"),
            ("原油价格走软", "美元指数走强"),
        ]
        for a, b in cases:
            self.assertTrue(_has_opposite_direction(a, b), f"应检出方向对立: {a} vs {b}")

    def test_direction_opposite_entity_overlap_not_merged(self) -> None:
        """共享 3 个实体 bigram 但方向相反（减持 vs 增持）→ 不合并。

        此例防护起决定作用：共享实体重叠=3 已够主规则合并，靠方向对立拦下。
        """
        from src.python.providers.news_aggregator import _dedup_by_title

        items = [
            self._make_item("兆易创新：5月6日至6月12日朱一明合计减持约44亿元公司股份", "东方财富"),
            self._make_item("兆易创新拟回购最高20亿元股份，董事长朱一明拟增持不低于10亿元", "新浪财经"),
        ]
        self.assertEqual(len(_dedup_by_title(items)), 2)


class TestAnchorRulesVersion(unittest.TestCase):
    """锚点规则指纹：让校准工具能区分规则时代，不靠人工维护版本号。

    锚点文件 append-only，规则调整后旧样本与新样本混在一起会使校准报告失真
    （实测 cross_skip 中 46% 的 ratio 低于当前候选区入口）。
    """

    def test_anchor_record_carries_rules_version(self) -> None:
        """每条锚点带当前规则指纹。"""
        from src.python.providers.news_dedup import _make_anchor
        from src.python.providers.news_dedup_rules import ANCHOR_RULES_FIELD, _ANCHOR_RULES_VERSION

        anchor = _make_anchor(
            {"title": "A", "_source": "x", "ctime": ""},
            {"title": "B", "_source": "y", "ctime": ""},
            0.4,
            2,
            True,
            "cross_merge",
        )
        self.assertEqual(anchor[ANCHOR_RULES_FIELD], _ANCHOR_RULES_VERSION)
        self.assertTrue(_ANCHOR_RULES_VERSION)

    def test_fingerprint_follows_threshold_change(self) -> None:
        """阈值一变，指纹随之变化（无需人工改版本号）。"""
        from src.python.providers import news_dedup_rules

        baseline = news_dedup_rules._ANCHOR_RULES_VERSION
        with patch.object(news_dedup_rules, "_CROSS_BG2_RATIO", 0.45):
            self.assertNotEqual(news_dedup_rules._rules_fingerprint(), baseline)

    def test_fingerprint_follows_opposite_pair_change(self) -> None:
        """方向词对一变，指纹随之变化（覆盖非数值规则数据）。"""
        from src.python.providers import news_dedup_rules

        baseline = news_dedup_rules._ANCHOR_RULES_VERSION
        with patch.object(news_dedup_rules, "_OPPOSITE_PAIRS", (("上涨", "下跌"),)):
            self.assertNotEqual(news_dedup_rules._rules_fingerprint(), baseline)


class TestPairSimilarityMatchesLinkDecision(unittest.TestCase):
    """``_pair_similarity`` 与链路内判定同口径（校准工具不得自带一套算法）。

    校准工具拿锚点里的原始标题调 ``_pair_similarity`` 重算；若它与
    ``_dedup_by_title`` 实际使用的口径不一致，校准结论就会系统性偏离线上行为。
    """

    def setUp(self) -> None:
        import tempfile

        from src.python.providers import news_dedup

        self._tmpdir = tempfile.mkdtemp()
        self._path_patch = patch(
            "src.python.providers.news_dedup._ANCHOR_PATH", os.path.join(self._tmpdir, "anchors.jsonl")
        )
        self._path_patch.start()
        news_dedup._ANCHOR_RECORDS = []

    def tearDown(self) -> None:
        self._path_patch.stop()

    def test_recorded_ratio_and_overlap_match_pure_recompute(self) -> None:
        """锚点记录里的 ratio/bigram_overlap 与纯重算结果一致（候选区样本）。"""
        from src.python.providers import news_dedup
        from src.python.providers.news_aggregator import _dedup_by_title

        title_a = "美国F-35战机在加州海军陆战队航空站附近坠毁"
        title_b = "伊称摧毁3架美军F35战机"
        _dedup_by_title(
            [
                {"title": title_a, "_source": "东方财富", "url": "a"},
                {"title": title_b, "_source": "新浪财经", "url": "b"},
            ]
        )
        records = [r for r in news_dedup._ANCHOR_RECORDS if r.get("rule") in ("cross_skip", "cross_merge")]
        self.assertTrue(records, "候选区样本应记录锚点")
        from src.python.providers.news_dedup_rules import _pair_similarity

        ratio, overlap = _pair_similarity(title_a, title_b)
        self.assertEqual(records[0]["ratio"], round(ratio, 3))
        self.assertEqual(records[0]["bigram_overlap"], overlap)


if __name__ == "__main__":
    unittest.main()


class TestAnchorAppendAndRetention(unittest.TestCase):
    """锚点文件：追加写不重写全文 + 压缩按保留期裁剪（体积有确定上限）。

    背景：37.9 MB 的锚点文件在每次 flush 都被「读全文 → 整文件替换」，而单轮只
    新增数十条；仅按 key 去重压不小（标题对高度唯一，实测压后仍 37.9 MB）。
    """

    pytestmark = [pytest.mark.unit, pytest.mark.unit_news]

    def setUp(self) -> None:
        import tempfile
        from unittest.mock import patch

        self._tmpdir = tempfile.mkdtemp()
        self._anchor_path = os.path.join(self._tmpdir, "anchors.jsonl")
        self._path_patch = patch("src.python.providers.news_dedup._ANCHOR_PATH", self._anchor_path)
        self._path_patch.start()
        from src.python.providers import news_dedup

        news_dedup._ANCHOR_RECORDS = []

    def tearDown(self) -> None:
        self._path_patch.stop()

    def _record(self, title_a: str, title_b: str, ts: str = "") -> None:

        _record_anchor(
            {
                "source_a": "东方财富",
                "source_b": "新浪财经",
                "title_a": title_a,
                "title_b": title_b,
                "ratio": 0.312,
                "bigram_overlap": 2,
                "merged": False,
                "rule": "cross_skip",
                "ts": ts,
            }
        )

    def test_flush_appends_without_replacing_file(self) -> None:
        """追加写：文件 inode 不变、既有内容逐字节保留（不再整文件替换）。"""
        from src.python.providers.news_dedup import _flush_anchors

        self._record("新闻A", "新闻B")
        _flush_anchors()
        before_stat = os.stat(self._anchor_path)
        before_bytes = open(self._anchor_path, "rb").read()

        self._record("新闻C", "新闻D")
        _flush_anchors()
        after_stat = os.stat(self._anchor_path)

        self.assertEqual(before_stat.st_ino, after_stat.st_ino, "追加写不应替换文件（inode 变化=整体重写）")
        with open(self._anchor_path, "rb") as f:
            after_bytes = f.read()
        self.assertTrue(after_bytes.startswith(before_bytes), "既有内容必须原样保留在前")
        self.assertGreater(len(after_bytes), len(before_bytes))

    def test_compaction_drops_records_beyond_retention(self) -> None:
        """压缩：超出保留期的记录被裁掉，保留期内的保留（体积才有上限）。"""
        from unittest.mock import patch

        from src.python.providers import news_dedup

        old_ts = "2020-01-02 10:00"
        recent_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        rows = [
            news_dedup._make_anchor(
                {"ctime": old_ts, "title": "旧新闻一", "_source": "A"},
                {"ctime": old_ts, "title": "旧新闻二", "_source": "B"},
                0.3,
                2,
                False,
                "cross_skip",
            ),
            news_dedup._make_anchor(
                {"ctime": recent_ts, "title": "新新闻一", "_source": "A"},
                {"ctime": recent_ts, "title": "新新闻二", "_source": "B"},
                0.3,
                2,
                False,
                "cross_skip",
            ),
        ]
        with open(self._anchor_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        with patch.object(news_dedup, "_ANCHOR_SIZE_WARN_BYTES", 1):
            news_dedup._compact_anchor_file(os.path.getsize(self._anchor_path))

        remaining = open(self._anchor_path, encoding="utf-8").read()
        self.assertIn("新新闻一", remaining)
        self.assertNotIn("旧新闻一", remaining, "超保留期记录应被裁掉")

    def test_retention_zero_keeps_all(self) -> None:
        """保留期设为 0 → 退回纯去重（不按时间裁剪），由运维显式选择。"""
        from unittest.mock import patch

        from src.python.providers import news_dedup

        old_ts = "2020-01-02 10:00"
        row = news_dedup._make_anchor(
            {"ctime": old_ts, "title": "很老的新闻甲", "_source": "A"},
            {"ctime": old_ts, "title": "很老的新闻乙", "_source": "B"},
            0.3,
            2,
            False,
            "cross_skip",
        )
        with open(self._anchor_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        with (
            patch.object(news_dedup, "_ANCHOR_SIZE_WARN_BYTES", 1),
            patch.dict(os.environ, {news_dedup._ANCHOR_RETENTION_ENV: "0"}),
        ):
            news_dedup._compact_anchor_file(os.path.getsize(self._anchor_path))

        self.assertIn("很老的新闻甲", open(self._anchor_path, encoding="utf-8").read())
