"""LLM 事实锚定校验器 — 非收益率语境守卫（与 test_fact_checker_context 的语境归属簇分文件）。

覆盖：
  - 目标位 / 合计=分项之和 / 主体不可解析 三类守卫（占比与目标权重不被改写成收益率）
  - 括号内并列品种按最近代码归因、同句同值多义整值放弃
  - 权重表面：占 X% 与表格并列裸百分比单元格
  - 市场/板块口径（指数中文名与基金名重叠）按距离让位
  - 「已修正明细」只列实际生效的改写
  - LLM 缓存键版本盐的暴露与首尾日志

运行：
    pytest src/test/unit/llm/test_fact_checker_nonrate_guards.py -v
"""

from __future__ import annotations

import pytest

from src.python.llm.fact_checker import (
    check_numerical_consistency,
    run_fact_check,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.llm,
]


class TestNonRateValueGuards:
    """非收益率数值的三类守卫：目标位 / 合计=分项之和 / 主体未解析。

    实盘事故（一次真实报告的 4 处「修正」里 3 处是误伤）：校验器把
    **仓位占比与目标权重**按最近邻改写成某品种收益率，又因口语简称
    「建信装备」解析不到 011506，把该品种**正确**的 +21.91% 换成同句 016055
    的 18.7%。修正直接进用户可见正文，下游 `self_review` 再把改错后的矛盾
    当模型错误报出——把正确文本改错比漏改代价大得多。
    """

    pytestmark = [
        pytest.mark.unit,
        pytest.mark.unit_llm,
        pytest.mark.llm,
    ]

    @pytest.fixture
    def holdings(self) -> list[dict]:
        """事故句涉及的四个品种（profit_rate 取真实口径百分值）。"""
        return [
            {
                "name": "兴全恒慧30天持有超短债C",
                "code": "012325",
                "market_value": 34203.0,
                "cost": 32700.0,
                "profit_rate": 4.6,
            },
            {
                "name": "华宝增强收益债券A",
                "code": "240012",
                "market_value": 15950.0,
                "cost": 17337.0,
                "profit_rate": -8.0,
            },
            {
                "name": "建信高端装备股票A",
                "code": "011506",
                "market_value": 30000.0,
                "cost": 24607.0,
                "profit_rate": 21.91,
            },
            {
                "name": "博时纳斯达克100联接A",
                "code": "016055",
                "market_value": 21100.0,
                "cost": 17779.0,
                "profit_rate": 18.66,
            },
        ]

    def test_target_weight_and_breakdown_not_corrected(self, holdings):
        """事故原句：占比 18.3% = 括号内 12.5%+5.8%，25% 是目标权重 → 都不改写。"""
        text = "方向：把低风险资产从当前的 18.3%（012325 12.5% + 240012 5.8%）提到 25% 附近，代价是牺牲部分上行。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"占比/目标权重不应被改写成收益率: {corrections}"

    def test_breakdown_sum_guard_alone(self, holdings):
        """仅「合计 = 分项之和」结构（无「附近」目标位）也不改写。"""
        text = "固收部分合计 18.3%（012325 12.5% + 240012 5.8%）是压舱石。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"合计=分项之和不应被改写: {corrections}"

    def test_unresolved_short_name_not_rewritten(self, holdings):
        """口语简称解析不到持仓时，不得改用同句其他品种的收益率。"""
        text = "各品种持仓收益率分层合理：纳指联接 016055 +18.66%、建信装备 +21.91% 属中等偏上。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"主体未解析的数值不可改写成同句他品种收益率: {corrections}"

    def test_resolvable_subject_still_corrected_in_same_sentence(self, holdings):
        """守卫不过度：同句里主体可解析的错误数值仍须纠正。"""
        text = "各品种持仓收益率分层合理：纳指联接 016055 +99.9%、建信装备 +21.91% 属中等偏上。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert len(corrections) == 1, f"应只纠正 99.9 一处: {corrections}"
        assert corrections[0][0] == "99.9" and corrections[0][1] == "18.7"

    def test_resolved_full_name_still_corrected(self, holdings):
        """全名主体（省略类型尾缀「股票A」）解析得到 → 错值仍须纠正。"""
        text = "建信高端装备持仓收益率 +25.0% 领先。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert len(corrections) == 1 and corrections[0][1] == "21.9", f"全名主体错值应被纠正: {corrections}"

    def test_time_filler_does_not_shield_real_rate(self, holdings):
        """时间填充词（本季度）不遮蔽主体：主体在更左侧仍能解析并纠正。"""
        text = "兴全恒慧30天持有超短债C（012325）本季度收益率为 11.0%，表现稳健。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert len(corrections) == 1 and corrections[0][1] == "4.6", f"主体可解析时应纠正: {corrections}"


class TestBracketScopeNearestCode:
    """括号内并列多只品种时，数值归**最近**代码而非括号内首个代码。

    实盘事故：「（240012 -8.03%、561910 -36.20%）」——`_locate_subject_code` 的
    括号作用域取括号内首个代码 240012，把 561910 **正确**的 -36.20% 改写成 240012
    的 -8.0%；叠加回写与按数值去重，逐轮把同一事实的其他句子逐个改错，最终同一份
    报告里并存 -8.0% 与 -36.20%，缓存里也是自相矛盾的。
    """

    pytestmark = [
        pytest.mark.unit,
        pytest.mark.unit_llm,
        pytest.mark.llm,
    ]

    @pytest.fixture
    def holdings(self) -> list[dict]:
        return [
            {
                "name": "华宝增强收益债券A",
                "code": "240012",
                "market_value": 15950.0,
                "cost": 17343.0,
                "profit_rate": -8.03,
            },
            {
                "name": "招商中证电池主题ETF",
                "code": "561910",
                "market_value": 20680.0,
                "cost": 32414.0,
                "profit_rate": -36.20,
            },
        ]

    def test_second_code_in_bracket_keeps_its_own_rate(self, holdings):
        """事故原句：561910 的 -36.20% 不再被改写成 240012 的 -8.0%。"""
        text = "12 只中 10 只盈利、2 只亏损（240012 -8.03%、561910 -36.20%），浮盈浮亏结构健康。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"括号内第二个品种的正确数值被改写: {corrections}"

    def test_bracket_value_without_code_keeps_nearest_subject(self, holdings):
        """代码在括号外紧邻时仍按最近主体归因（如「561910（-36.20%，7.3%）」）。"""
        text = "561910（-36.20%，7.3%）仍是唯一深度亏损品种。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"紧邻代码的主体不应被改写: {corrections}"

    def test_wrong_rate_of_bracketed_second_code_still_corrected(self, holdings):
        """守卫不过度：括号内第二个品种的**错误**数值仍按其自身收益率纠正。"""
        text = "2 只亏损（240012 -8.03%、561910 -99.9%），结构与预期不符。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert len(corrections) == 1, f"应纠正 561910 的错值: {corrections}"
        assert corrections[0][0] == "99.9" and corrections[0][1] == "-36.2", corrections[0]


class TestWeightSurfacesNotRates:
    """权重类表述（「占 X%」与表格并列裸百分比单元格）不得按收益率改写。

    实盘事故：智囊团模块单轮产生 9 处「修正」，全部是把权重改写成收益率——
    「它现在仍占 7.3%」若按收益率处理即变成 561910 的 -36.2%；「| 建设银行 |
    601939 | 8.8% | 6.5% |」的两个权重列同理会被按 241.5% 改写。中文投资写作里「占 X%」是最常见的权重
    表达，而 `_NON_RATE_PRE_WORDS` 只收了「占比」，「占」单独出现时未识别；
    表格行的权重列/目标列是裸百分比、单元格内无任何语境词，只能靠「同行多列并列
    裸百分比即数值列」判据整体跳过。
    """

    pytestmark = [
        pytest.mark.unit,
        pytest.mark.unit_llm,
        pytest.mark.llm,
    ]

    @pytest.fixture
    def holdings(self) -> list[dict]:
        return [
            {"name": "建设银行", "code": "601939", "market_value": 19800.0, "cost": 5800.0, "profit_rate": 241.5},
            {
                "name": "华宝增强收益债券A",
                "code": "240012",
                "market_value": 15950.0,
                "cost": 17343.0,
                "profit_rate": -8.03,
            },
            {
                "name": "招商中证电池主题ETF",
                "code": "561910",
                "market_value": 20680.0,
                "cost": 32414.0,
                "profit_rate": -36.2,
            },
        ]

    def test_zhan_weight_not_corrected(self, holdings):
        """「仍占 7.3%」是权重，不改写成品种收益率。"""
        text = "它现在仍占 7.3%，是组合第 9 大持仓，而它是唯一一个 -36.20% 的品种。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"权重表述被改写成收益率: {corrections}"

    def test_zhan_weight_bracket_list_not_corrected(self, holdings):
        """「（012325 占 12.5%、011506 占 11.1%）」并列权重全部跳过。"""
        text = "前三持仓（601939 占 8.8%、240012 占 5.9%）合计约三成，集中度不极端。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"并列权重被改写: {corrections}"

    def test_table_parallel_percent_cells_not_corrected(self, holdings):
        """表格行并列裸百分比（权重列 + 目标列）整体跳过，不按就近代码改写。"""
        text = "| 建设银行 | 601939 | 8.8% | 6.5% | 减仓 | 持仓收益率 -8.03% |"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        rewritten = {c[0] for c in corrections}
        assert "8.8" not in rewritten and "6.5" not in rewritten, f"表格权重列被改写: {corrections}"

    def test_single_percent_table_cell_still_checked(self, holdings):
        """守卫不过度：行内只有一个百分比单元格（带收益率标签）时仍按主体纠正错值。"""
        text = "| 建设银行 | 601939 | 持仓收益率 123.4% |"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert len(corrections) == 1 and corrections[0][1] == "241.5", f"单列百分比仍应纠正: {corrections}"


class TestAppliedCorrectionReporting:
    """「已修正明细」只列真正生效的改写。

    检查阶段判定与改写阶段落笔是两件事：归属不可知的数值（同值异义/同句多义/表格
    并列裸百分比）在改写阶段被跳过，若摘要仍按判定列表生成，报告会宣称「已修正 9
    处」而实际一处未动，读者无法判断正文是否被改过。
    """

    pytestmark = [
        pytest.mark.unit,
        pytest.mark.unit_llm,
        pytest.mark.llm,
    ]

    def test_skipped_value_not_claimed_as_corrected(self):
        """同句同值多义 → 改写阶段跳过：摘要不得宣称已修正该值。"""
        holdings = [
            {"name": "工商银行", "code": "601398", "market_value": 15000.0, "cost": 8814.0, "profit_rate": 70.18},
        ]
        html = "<p>止盈约30%持仓，收益率30%。</p>"
        corrected, summary = run_fact_check(html, holdings, module_label="智囊团深度复盘")
        assert corrected == html, "同值异义不得改写"
        assert "已修正明细" not in summary, f"未改写却在摘要里宣称已修正: {summary}"

    def test_unapplied_value_not_listed_as_warning(self):
        """归属不可知而未改写的数值也不列为告警（检查器未判定其为错值）。"""
        holdings = [
            {"name": "工商银行", "code": "601398", "market_value": 15000.0, "cost": 8814.0, "profit_rate": 70.18},
        ]
        html = "<p>止盈约30%持仓，收益率30%。</p>"
        _corrected, summary = run_fact_check(html, holdings, module_label="智囊团深度复盘")
        assert "30" not in summary or "修正" not in summary, f"跳过项不应出现在摘要告警里: {summary}"


class TestMarketScopeNoSubject:
    """市场/板块口径且分句内无持仓主体 → 不改写。

    实盘事故：「银行板块净流出15.06亿、跌0.35%，白酒净流出16.86亿、跌2.35%」——
    板块单日涨跌被全局最近邻兜底改写成某品种收益率（先是 102.0%、后是 4.6%，随
    最近邻漂移）。更贵的是它**回写缓存**：下一轮自检的输入段随之变化，每轮多付一次
    11~17s 的自检调用（长驻进程连跑三份报告时稳定复现）。
    """

    pytestmark = [
        pytest.mark.unit,
        pytest.mark.unit_llm,
        pytest.mark.llm,
    ]

    @pytest.fixture
    def holdings(self) -> list[dict]:
        return [
            {
                "name": "兴全恒慧30天持有超短债C",
                "code": "012325",
                "market_value": 34203.0,
                "cost": 32700.0,
                "profit_rate": 4.6,
            },
            {"name": "建设银行", "code": "601939", "market_value": 19800.0, "cost": 5800.0, "profit_rate": 241.5},
        ]

    def test_sector_daily_move_not_corrected(self, holdings):
        """板块净流出与涨跌幅（无持仓主体）不改写为品种收益率。"""
        text = "而银行板块净流出15.06亿、跌0.35%，白酒净流出16.86亿、跌2.35%。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"板块涨跌被改写: {corrections}"

    def test_index_moves_not_corrected(self, holdings):
        """指数/大盘涨跌（无持仓主体）不改写。"""
        text = "沪深300涨1.2%，创业板跌0.8%，两市成交额萎缩。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"指数涨跌被改写: {corrections}"

    def test_holding_rate_in_market_sentence_still_corrected(self, holdings):
        """守卫不过度：含持仓主体的分句仍按其自身收益率纠正。"""
        text = "建设银行 持仓收益率 123.4%，领先同板块同业。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert len(corrections) == 1 and corrections[0][1] == "241.5", f"持仓错值应纠正: {corrections}"

    def test_index_name_overlapping_holding_name_not_corrected(self):
        """指数中文名与基金名重叠时按距离让位给指数口径（实盘 1.18%→18.7% 根因）。

        「纳斯达克100涨1.18%」里「纳斯达克100」同时是持仓 016055（博时纳斯达克100联接A）
        名称的一部分，只看「分句内有无持仓主体」会把它当收益率改写成 016055 的 18.7%；
        而指数名词离数值更近 → 判为市场口径，不改写。
        """
        from src.python.llm.fact_checker import check_numerical_consistency

        holdings = [
            {
                "name": "博时纳斯达克100联接A",
                "code": "016055",
                "market_value": 21100.0,
                "cost": 17779.0,
                "profit_rate": 18.7,
            },
        ]
        text = "美国方面，纳斯达克100涨1.18%、标普500涨0.60%，科技成长延续强势。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert corrections == [], f"指数涨跌被改写成基金收益率: {corrections}"

    def test_holding_name_closer_than_index_still_corrected(self):
        """守卫不过度：同句里持仓主体比指数名词更近时，错值仍按持仓收益率纠正。"""
        from src.python.llm.fact_checker import check_numerical_consistency

        holdings = [
            {
                "name": "博时纳斯达克100联接A",
                "code": "016055",
                "market_value": 21100.0,
                "cost": 17779.0,
                "profit_rate": 18.7,
            },
        ]
        text = "博时纳斯达克100联接A 持仓收益率 9.9%，跟踪纳斯达克100。"
        _issues, _checked, _passed, corrections = check_numerical_consistency(text, holdings)
        assert len(corrections) == 1 and corrections[0][1] == "18.7", f"持仓错值应纠正: {corrections}"


class TestCacheKeySaltLogging:
    """缓存键版本盐首尾各打一行（模块整批重算时不必翻代码比对指纹）。"""

    pytestmark = [
        pytest.mark.unit,
        pytest.mark.unit_llm,
        pytest.mark.llm,
    ]

    def test_salts_expose_both_versions(self):
        from src.python.llm.fact_checker._constants import FACT_CHECK_RULES_VERSION
        from src.python.llm.fingerprint import cache_key_salts
        from src.python.llm.rate_caliber import PROMPT_SCHEMA_VERSION

        salts = cache_key_salts()
        assert salts["prompt_schema"] == PROMPT_SCHEMA_VERSION
        assert salts["fact_rules"] == FACT_CHECK_RULES_VERSION

    def test_log_cache_key_salts_emits_one_info(self, caplog):
        import logging

        from src.python.llm.fingerprint import log_cache_key_salts

        with caplog.at_level(logging.INFO, logger="invest"):
            log_cache_key_salts("本轮开始")
        rows = [r for r in caplog.records if "缓存键版本盐" in r.getMessage()]
        assert len(rows) == 1 and rows[0].levelno == logging.INFO
        assert "本轮开始" in rows[0].getMessage()

    def test_cache_summary_line_carries_salts(self, caplog):
        """收尾 `[cache]` 汇总行带版本盐尾注（命中率高却整批重算时可一眼分辨原因）。"""
        import logging

        from src.python.cache._stats import _record_cache_hit, log_cache_summary, reset_cache_stats

        reset_cache_stats()
        _record_cache_hit()
        with caplog.at_level(logging.INFO, logger="invest"):
            log_cache_summary(salts_note="缓存键版本盐：提示词=p 校验规则=fact-rules-9")
        rows = [r for r in caplog.records if r.getMessage().startswith("[cache] 本次命中")]
        assert len(rows) == 1 and "校验规则=fact-rules-9" in rows[0].getMessage()
        reset_cache_stats()
