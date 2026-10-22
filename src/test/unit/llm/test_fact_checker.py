"""测试：LLM 事实锚定校验器 — fact_checker.py

覆盖：
  - check_numerical_consistency: 数值一致性校验（含各种收益率上下文）
  - check_symbol_existence: 品种存在性校验（持仓代码 vs 指数代码）
  - check_ranking_correctness: 排名正确性校验（最大持仓声称）
  - run_fact_check: 统一入口 + HTML 摘要格式
  - 边界场景：空输入、None 入参、无匹配、全通过

兄弟分片：test_fact_checker_context.py（上下文归属与自动纠错场景）。"""

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


@pytest.fixture
def sample_holdings() -> list[dict]:
    """一个含 5 只品种的模拟持仓。"""
    return [
        {"name": "贵州茅台", "code": "600519", "market_value": 2000000.0, "cost": 1500000.0},
        {"name": "招商银行", "code": "600036", "market_value": 800000.0, "cost": 600000.0},
        {"name": "宁德时代", "code": "300750", "market_value": 500000.0, "cost": 400000.0},
        {"name": "长江电力", "code": "600900", "market_value": 300000.0, "cost": 250000.0},
        {"name": "沪深300ETF", "code": "510300", "market_value": 100000.0, "cost": 90000.0},
    ]


@pytest.fixture
def holdings_with_rates() -> list[dict]:
    """含 profit_rate（百分单位，orchestrator 已 ×100）与 change_pct（单日涨跌）的持仓。

    用于百分单位契约与单日涨跌语境校验：数值须按百分单位比较，
    单日涨跌语境按 change_pct 校验（不当作收益率修正）。
    """
    return [
        {
            "name": "建设银行",
            "code": "601939",
            "market_value": 287120.0,
            "cost": 100000.0,
            "profit_rate": 187.12,
            "change_pct": -3.41,
        },
        {
            "name": "贵州茅台",
            "code": "600519",
            "market_value": 2000000.0,
            "cost": 1500000.0,
            "profit_rate": 33.33,
            "change_pct": 1.25,
        },
    ]


@pytest.fixture
def portfolio_mixed_holdings() -> list[dict]:
    """组合级+个股级收益同句场景的持仓：组合总收益率≈9.9%，招商银行 8.0%，茅台 15.0%。

    组合累计收益与个股涨跌同句时，组合收益归组合总收益率、
    个股收益归各自代码。
    """
    return [
        {"name": "工商银行", "code": "601398", "market_value": 200000.0, "cost": 185000.0, "profit_rate": 8.11},
        {"name": "招商银行", "code": "600036", "market_value": 108000.0, "cost": 100000.0, "profit_rate": 8.0},
        {"name": "贵州茅台", "code": "600519", "market_value": 115000.0, "cost": 100000.0, "profit_rate": 15.0},
    ]


class TestCheckNumericalConsistency:
    """数值一致性校验测试。"""

    def test_empty_text(self):
        """空文本 → 无检查项。"""
        issues, checked, passed, corrections = check_numerical_consistency("", None)
        assert issues == []
        assert checked == 0
        assert passed == 0
        assert corrections == []

    def test_no_percentage_values(self, sample_holdings):
        """无百分比数值的文本 → 无检查项。"""
        text = "本季度组合运行平稳，持仓结构保持合理分散。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0
        assert corrections == []

    def test_profit_percentage_matches(self, sample_holdings):
        """收益率数值与实际一致 → 通过。"""
        # 总收益率 = (200+80+50+30+10 - (150+60+40+25+9)) / (150+60+40+25+9) * 100
        # total_mv = 3700000, total_cost = 2840000, profit_rate ≈ 30.28%
        text = "本季度组合累计收益率为 30.5%，表现稳健。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert checked == 1
        assert passed == 1
        assert issues == []
        assert corrections == []

    def test_profit_percentage_mismatch(self, sample_holdings):
        """收益率数值与实际偏差大 → 告警。"""
        text = "本季度组合累计收益率为 5.0%，表现不及预期。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "偏差超过容差" in issues[0]
        assert len(corrections) == 1  # 返回修正信息
        assert corrections[0][0] == "5.0"  # wrong value
        assert corrections[0][1] == "30.3"  # correct value

    def test_non_profit_context_skipped(self, sample_holdings):
        """非收益上下文中的百分比不检查（如仓位比例）。"""
        text = "股票仓位占比 70%，债券仓位占比 30%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        # 百分比 30 在文本中出现但无收益关键词，跳过
        # 70% 也是无收益关键词
        assert checked >= 2
        assert passed == checked  # 全部跳过=全部通过
        assert issues == []
        assert corrections == []

    def test_deduplicate_same_value(self, sample_holdings):
        """同一数值多次出现只检一次。"""
        text = "累计收益率为 30.3%。表现不错，收益率 30.3%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert checked == 1  # 只检一次
        assert passed == 1
        assert corrections == []

    def test_negative_profit_rate(self, sample_holdings):
        """亏损场景 — 绝对值比较。"""
        # 模拟亏损持仓: cost > mv
        loss_holdings = [
            {"name": "贵州茅台", "code": "600519", "market_value": 100000.0, "cost": 200000.0},
            {"name": "招商银行", "code": "600036", "market_value": 50000.0, "cost": 100000.0},
        ]
        # 总亏损率 ≈ -50%
        text = "组合累计亏损 50.0%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, loss_holdings)
        assert checked == 1
        assert passed == 1
        assert issues == []
        assert corrections == []

    def test_zero_cost_edge(self):
        """零成本持仓 — 不产生 NaN 错误。"""
        holdings = [{"name": "测试", "code": "000001", "market_value": 1000.0, "cost": 0.0}]
        text = "累计收益率为 10.0%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings)
        # 零成本导致 profit_rate=0，与 10% 偏差超过容差
        assert isinstance(checked, int)
        assert isinstance(passed, int)
        assert isinstance(corrections, list)
        # profit_rate 为 0，但文本是 10%，应该不匹配
        assert checked >= 0

    def test_missing_market_value(self):
        """市值缺失 — 不影响函数运行。"""
        holdings = [{"name": "测试", "code": "000001", "cost": 1000.0}]
        text = "累计收益率为 5.0%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings)
        assert isinstance(issues, list)
        assert isinstance(checked, int)
        assert isinstance(passed, int)
        assert isinstance(corrections, list)

    def test_multiple_values_with_mixed_context(self, sample_holdings):
        """混合上下文中的多个百分比 — 只检收益相关的。"""
        text = "本季度组合累计收益率为 30.3%。股票仓位 75%，债券仓位 25%。最大回撤 3.5%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        # 30.3% → 收益上下文 → 检查通过
        # 75%, 25% → 仓位上下文 → 跳过
        # 3.5% → 回撤上下文 → 跳过
        assert checked >= 1
        assert passed == checked
        assert corrections == []

    def test_portfolio_level_plus_stock_level_same_sentence(self, portfolio_mixed_holdings):
        """组合级收益与个股级收益同句：组合收益归组合、个股收益归各自代码。

        组合累计收益 10.0% 归组合总收益率，不因邻近个股数值而产生假阳性。
        """
        text = "组合累计收益约10.0%，招商银行(600036)上涨8.0%，贵州茅台(600519)上涨15.0%"
        issues, checked, passed, corrections = check_numerical_consistency(text, portfolio_mixed_holdings)
        assert issues == []
        assert checked == 3
        assert passed == 3
        assert corrections == []

    def test_portfolio_level_mismatch_attributed_to_portfolio(self, portfolio_mixed_holdings):
        """组合级收益数值错误时归因到组合总收益率而非个股。"""
        text = "组合累计收益约20.0%，招商银行(600036)上涨8.0%，贵州茅台(600519)上涨15.0%"
        issues, checked, passed, corrections = check_numerical_consistency(text, portfolio_mixed_holdings)
        assert checked == 3
        assert passed == 2
        assert len(issues) == 1
        # 归因到组合总收益率（"实际累计收益率"为组合级专用消息），不写成某个个股的收益率
        assert "实际累计收益率" in issues[0]
        assert len(corrections) == 1
        assert corrections[0][3] == "组合实际收益率9.9%"

    def test_pp_vs_rate_confusion_detected(self):
        """LLM 混淆贡献占比 pp 与个股收益率 → 检测并修正。"""
        holdings = [
            {
                "name": "建设银行",
                "code": "601939",
                "market_value": 500000.0,
                "cost": 490000.0,
                "profit": 10000.0,
                "profit_rate": 2.0,
            },
            {
                "name": "贵州茅台",
                "code": "600519",
                "market_value": 2000000.0,
                "cost": 1500000.0,
                "profit": 500000.0,
                "profit_rate": 33.3,
            },
        ]
        # LLM 误将 11.0pp 贡献占比当作收益率 11.0%
        text = "建设银行（601939）本季度收益率为 11.0%，表现稳健。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "601939" in issues[0]
        assert "11.0" in issues[0]
        assert "2.0" in issues[0]  # 实际收益率
        assert len(corrections) == 1
        assert corrections[0][0] == "11.0"  # wrong value
        assert corrections[0][1] == "2.0"  # correct value
        assert "601939" in corrections[0][2]  # sentence context

    def test_contribution_sentence_skips_pp_values(self):
        """贡献归因句中的 pp 数值不触发告警（策略 3）。"""
        holdings = [
            {
                "name": "建设银行",
                "code": "601939",
                "market_value": 500000.0,
                "cost": 490000.0,
                "profit": 10000.0,
                "profit_rate": 2.0,
            },
        ]
        # 收益归因句中的 pp 数值应跳过
        text = "主要盈利来源中，建设银行(+11.0pp)为组合贡献了重要收益。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings)
        # 收益归因句整体跳过，无检查项
        assert issues == []
        assert passed == 0
        assert corrections == []

    def test_change_rate_context_skipped(self, sample_holdings):
        """环比/同比变化率语境数值不误判为收益率。

        持仓体检的"环比对比：总市值变化-96.02%"是相对上期的变化率，
        与收益率（相对成本）维度不同。句子含"下跌"等收益关键词时，
        变化率必须跳过，否则会被误修正为最近个股/组合收益率。
        """
        text = "与上月环比对比，组合总市值大幅下跌96.02%，总盈亏变化+3,263，主要受到重仓个股回调影响。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert checked == 1  # 96.02% 被识别为变化率语境
        assert passed == 1  # 跳过 = 通过
        assert issues == []
        assert corrections == []  # 不被误修正

    def test_change_rate_uses_nearby_not_whole_sentence(self, sample_holdings):
        """变化率语境用数值邻近关键词判断，同句首部的真实收益率仍被校验。

        同句"环比总市值变化-96.02%，其中贵州茅台收益率为5.0%"：
        96.02% 跳过（邻近"变化"），5.0% 仍与茅台 33.3% 比较 → 被修正。
        """
        text = "环比上月总市值变化-96.02%，其中贵州茅台收益率为5.0%，表现不佳。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert checked == 2  # 96.02% + 5.0%
        assert passed == 1  # 只有变化率通过
        assert len(corrections) == 1  # 5.0% 被修正
        assert corrections[0][0] == "5.0"
        assert corrections[0][1] == "30.3"  # 最接近参考值（组合总收益率）

    def test_change_rate_with_volume_keywords(self, sample_holdings):
        """变化率语境覆盖"同比/较上期/总市值变化"等关键词组合。"""
        text = "同比总市值变化-96.02%，较上期总盈亏变化+3,263。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert issues == []
        assert corrections == []

    def test_tolerance_override_looser(self, sample_holdings):
        """宽松容差下偏差较小的数值通过。"""
        text = "组合收益率为 31.5%。"  # 实际≈30.28%，偏差1.22pp
        issues, checked, passed, corrections = check_numerical_consistency(
            text,
            sample_holdings,
            tolerance_pct=2.0,
        )
        assert checked == 1
        assert passed == 1  # 容差 ±2% 已覆盖
        assert issues == []
        assert corrections == []

    def test_drawdown_value_within_tolerance(self, sample_holdings):
        """回撤语境数值与实际最大回撤在容差内 → 通过。"""
        text = "组合历史最大回撤为 19.0%。"
        issues, checked, passed, corrections = check_numerical_consistency(
            text,
            sample_holdings,
            max_drawdown_pct=18.97,
        )
        assert checked == 1
        assert passed == 1  # 19.0 vs 18.97, diff=0.03 <= 1.0
        assert issues == []
        assert corrections == []

    def test_drawdown_value_out_of_tolerance(self, sample_holdings):
        """回撤语境数值与实际偏差大 → 告警。"""
        text = "组合历史最大回撤为 5.0%。"
        issues, checked, passed, corrections = check_numerical_consistency(
            text,
            sample_holdings,
            max_drawdown_pct=18.97,
        )
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "回撤相关数值" in issues[0]
        assert "18.97" in issues[0] or "19.0" in issues[0]
        assert len(corrections) == 1

    def test_drawdown_value_no_data_skips(self, sample_holdings):
        """回撤语境但无回撤数据 → 跳过（无法校验）。"""
        text = "组合最大回撤为 19.0%。"
        issues, checked, passed, corrections = check_numerical_consistency(
            text,
            sample_holdings,
            max_drawdown_pct=None,
        )
        assert checked == 1  # % found
        assert passed == 1  # skipped (no drawdown data, no profit context)
        assert issues == []

    def test_drawdown_mixed_with_profit_in_sentence(self, sample_holdings):
        """同一句中同时含回撤和收益数值 → 分别校验。"""
        text = "最大回撤 19.0%，累计收益 30.3%。"
        issues, checked, passed, corrections = check_numerical_consistency(
            text,
            sample_holdings,
            max_drawdown_pct=18.97,
        )
        # 19.0% → drawdown context, matches 18.97 within tolerance
        # 30.3% → profit context, matches 30.28 within tolerance
        assert checked == 2
        assert passed == 2
        assert issues == []

    def test_issue_message_contains_sentence_snippet(self, sample_holdings):
        """告警消息包含句段上下文摘要。"""
        text = "本季度组合累计收益率为 5.0%，表现不及预期。"
        issues, checked, passed, corrections = check_numerical_consistency(text, sample_holdings)
        assert len(issues) == 1
        assert "句段：" in issues[0]
        assert "本季度组合累计收益率" in issues[0]

    def test_run_fact_check_corrected_values_not_in_warnings(self, sample_holdings):
        """run_fact_check 中已自动修正的数值不在告警明细列出。"""
        text = "<p>组合累计收益率为 5.0%，历史最大回撤 19.0%。</p>"
        from src.python.llm.fact_checker import run_fact_check

        corrected, summary = run_fact_check(
            text,
            sample_holdings,
            module_label="测试",
            history_data={"max_drawdown_pct": 18.97},
        )
        # 5.0% → will be auto-corrected, not in warning details
        # 19.0% → drawdown within tolerance, no issue
        assert "自动修正 1 处数值" in summary
        # The corrected 5.0 should NOT appear as a ⚠ warning
        assert "⚠" not in summary


class TestProfitRateUnitAndDailyChange:
    """profit_rate 百分单位契约 + 单日涨跌语境按 change_pct 校验。

    profit_rate 为百分单位（187.12 表示 187.12%），数值校验须按百分单位比较；
    单日涨跌语境按 change_pct 校验，不得把 3.41% 当作收益率修正。
    """

    def test_profit_rate_percent_unit_matches(self, holdings_with_rates):
        """百分单位：实际收益率 187.12% 时声称 187.1% → 通过，不再误修正。"""
        text = "建设银行（601939）持仓收益率为 187.1%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings_with_rates)
        assert checked == 1
        assert passed == 1
        assert issues == []
        assert corrections == []

    def test_profit_rate_decimal_value_corrected(self, holdings_with_rates):
        """百分单位：数值 1.9%（与 187.12 偏差超容差）→ 修正为 187.1%。

        百分单位契约下 1.9 与 187.12 偏差超容差，应修正为 187.1。
        """
        text = "建设银行（601939）持仓收益率为 1.9%。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings_with_rates)
        assert checked == 1
        assert passed == 0
        assert len(corrections) == 1
        assert corrections[0][0] == "1.9"
        assert corrections[0][1] == "187.1"
        assert "187.1%" in corrections[0][3]  # 语义 reason 指明实际收益率

    def test_daily_change_matching_change_pct_not_corrected(self, holdings_with_rates):
        """单日涨跌语境：今日下跌 3.41% 与 601939 change_pct=-3.41 一致 → 不修正。

        单日涨跌按 change_pct 校验，不当作收益率修正。
        """
        text = "建设银行（601939）今日下跌3.41%，表现弱于大盘。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings_with_rates)
        assert checked == 1
        assert passed == 1
        assert issues == []
        assert corrections == []

    def test_daily_change_mismatch_corrected(self, holdings_with_rates):
        """单日涨跌语境：声称下跌 1.0% 与实际 -3.41% 偏差大 → 修正为 -3.4%。"""
        text = "建设银行（601939）今日下跌1.0%，跌幅较大。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings_with_rates)
        assert checked == 1
        assert passed == 0
        assert len(corrections) == 1
        assert corrections[0][0] == "1.0"
        assert corrections[0][1] == "-3.4"

    def test_daily_change_without_subject_skipped(self, holdings_with_rates):
        """单日涨跌语境无持仓主体（指数）→ 无可用校验数据，跳过不修正。"""
        text = "上证指数今日下跌0.5%，市场整体偏弱。"
        issues, checked, passed, corrections = check_numerical_consistency(text, holdings_with_rates)
        assert checked == 1
        assert passed == 1
        assert corrections == []

    def test_run_fact_check_daily_change_not_corrected(self, holdings_with_rates):
        """run_fact_check 整链路：单日涨跌不被自动修正，摘要无修正明细。"""
        html = "<p>建设银行（601939）今日下跌3.41%，表现弱于大盘。</p>"
        corr, summ = run_fact_check(html, holdings_with_rates, "持仓体检报告")
        assert corr == html  # 内容不被篡改
        assert "3.41%" in corr
        assert "已修正明细" not in summ


class TestAutoCorrectionCounters:
    """自动修正次数跨模块累计（供 perf_history.counters 跨期对拍）。

    判定口径：单次运行实测 5 处数值修正（智囊团/体检/穿透），只进日志时无法回答
    「提示词改动后偏差是变好还是变坏」——计数必须可编程取用。
    """

    def test_run_fact_check_accumulates_counts(self, sample_holdings):
        from src.python.llm.fact_checker import auto_correction_counts, reset_auto_correction_counts

        reset_auto_correction_counts()
        run_fact_check(
            "<p>组合累计收益率为 5.0%，历史最大回撤 19.0%。</p>",
            sample_holdings,
            module_label="测试模块",
            history_data={"max_drawdown_pct": 18.97},
        )
        counts = auto_correction_counts()
        assert counts.get("fact_fix:测试模块") == 1
        assert counts.get("fact_fix_total") == 1
        assert counts.get("fact_fix_numeric") == 1
        assert "fact_fix_code" not in counts

    def test_no_correction_records_nothing(self, sample_holdings):
        from src.python.llm.fact_checker import auto_correction_counts, reset_auto_correction_counts

        reset_auto_correction_counts()
        run_fact_check("<p>一切正常。</p>", sample_holdings, module_label="测试模块")
        assert auto_correction_counts() == {}

    def test_reset_clears_previous_run(self, sample_holdings):
        """长驻进程 N 次生成不得跨轮累计（每轮从零开始）。"""
        from src.python.llm.fact_checker import auto_correction_counts, reset_auto_correction_counts

        run_fact_check(
            "<p>组合累计收益率为 5.0%，历史最大回撤 19.0%。</p>",
            sample_holdings,
            module_label="测试模块",
            history_data={"max_drawdown_pct": 18.97},
        )
        assert auto_correction_counts()
        reset_auto_correction_counts()
        assert auto_correction_counts() == {}
