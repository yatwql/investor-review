"""test_fact_checker 兄弟分片（ranking）：排名正确性与整体运行。"""

from __future__ import annotations
import pytest
from src.python.llm.fact_checker import (
    check_ranking_correctness,
    run_fact_check,
)

# 夹具按名注入（由测试签名消费），代码里无引用

# ruff: noqa: F811 — 参数与模块级夹具同名（pytest 按名注入），非重定义
from src.test.unit.llm.test_fact_checker import (
    sample_holdings,  # noqa: F401
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.llm,
]


class TestCheckRankingCorrectness:
    """排名正确性校验测试。"""

    def test_empty_text(self):
        """空文本 → 无检查项。"""
        issues, checked, passed = check_ranking_correctness("", None)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_no_ranking_claims(self, sample_holdings):
        """无排名声称 → 无检查项。"""
        text = "本季度组合各品种均有较好表现。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_largest_holding_correct(self, sample_holdings):
        """声称最大持仓 = 实际最大（600519）→ 通过。"""
        text = "贵州茅台（600519）是本季度组合最大持仓，市值占比过半。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 1
        assert issues == []

    def test_largest_holding_wrong(self, sample_holdings):
        """声称的"最大持仓"不是实际最大 → 告警。"""
        text = "招商银行（600036）是组合最大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "600036" in issues[0]
        assert "最大持仓" in issues[0]
        assert "600519" in issues[0]  # 提示实际最大是 600519

    def test_first_major_holding_wrong(self, sample_holdings):
        """声称"第一重仓"不是实际第一 → 告警。"""
        text = "宁德时代（300750）是第一重仓股。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "300750" in issues[0]
        assert "600519" in issues[0]

    def test_code_not_in_rank_map(self, sample_holdings):
        """排名语句中的代码不在持仓排名中 → 告警。"""
        text = "中国平安（601318）是组合最大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "601318" in issues[0]
        assert "无法在持仓市值排名中找到" in issues[0]

    def test_no_code_in_ranking_sentence(self, sample_holdings):
        """排名句子中无代码 → 跳过。"""
        text = "组合最大持仓品种本季度表现优异。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_mixed_ranking_claims(self, sample_holdings):
        """混合正确和错误的排名声称。"""
        text = "贵州茅台（600519）是组合最大持仓。宁德时代（300750）是第一重仓股。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 2
        assert passed == 1
        assert len(issues) == 1  # 只有宁德时代的有问题

    def test_holdings_none(self):
        """holdings_details 为 None → 直接返回。"""
        issues, checked, passed = check_ranking_correctness("600519 是最大持仓。", None)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_holdings_empty_list(self):
        """holdings_details 为空列表 → 直接返回。"""
        issues, checked, passed = check_ranking_correctness("600519 是最大持仓。", [])
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_no_market_value_data(self):
        """持仓市值全部缺失 → 无检查项。"""
        holdings = [
            {"name": "测试A", "code": "000001"},
            {"name": "测试B", "code": "000002"},
        ]
        text = "测试A（000001）是最大持仓。"
        issues, checked, passed = check_ranking_correctness(text, holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_rank_tie(self, sample_holdings):
        """第一和第二并列 — 仅检查严重偏离的情况。"""
        # 添加一个市值与最大接近的品种
        holdings = sample_holdings + [
            {"name": "竞争品种", "code": "000888", "market_value": 1990000.0, "cost": 1800000.0},
        ]
        text = "竞争品种（000888）是组合最大持仓。"
        issues, checked, passed = check_ranking_correctness(text, holdings)
        # 000888 排第2（市值 199万 vs 600519 市值 200万）
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1

    # ── 第N大 / 前N大 / 主要持仓 声称 ──────────────

    def test_second_largest_correct_pass(self, sample_holdings):
        """声称"第二大持仓"且名次正确（600036 实际第2）→ 通过。"""
        text = "招商银行（600036）是组合第二大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 1
        assert issues == []

    def test_second_largest_wrong_flagged(self, sample_holdings):
        """声称"第二大持仓"但名次错误（300750 实际第3）→ 告警且指名实际第2。"""
        text = "宁德时代（300750）是组合第二大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "300750" in issues[0]
        assert "第2大持仓" in issues[0]
        assert "600036" in issues[0]  # 实际第二大是招商银行

    def test_third_largest_correct_pass(self, sample_holdings):
        """声称"第三大持仓"且名次正确（300750 实际第3）→ 通过。"""
        text = "宁德时代（300750）是组合第三大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 1
        assert issues == []

    def test_third_largest_wrong_flagged(self, sample_holdings):
        """声称"第三大持仓"但名次错误（600900 实际第4）→ 告警且指名实际第3。"""
        text = "长江电力（600900）是组合第三大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "600900" in issues[0]
        assert "第3大持仓" in issues[0]
        assert "300750" in issues[0]  # 实际第三大是宁德时代

    def test_top3_non_first_rank_pass(self, sample_holdings):
        """声称"前三大持仓"且品种在 top3 内但非第一（600036 实际第2）→ 通过。"""
        text = "招商银行（600036）属于组合前三大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 1
        assert issues == []

    def test_top3_outside_rank_flagged(self, sample_holdings):
        """声称"前三大持仓"但品种不在 top3（510300 实际第5）→ 告警。"""
        text = "沪深300ETF（510300）属于组合前三大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "510300" in issues[0]
        assert "前3大持仓" in issues[0]

    def test_major_holding_vague_claim_skipped(self, sample_holdings):
        """ "主要持仓"是模糊声称（不断言精确名次）→ 不校验不告警。"""
        text = "招商银行（600036）是组合主要持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert issues == []
        assert checked == 0

    def test_ordinal_beyond_holdings_count(self, sample_holdings):
        """声称"第十大持仓"但持仓不足 10 只 → 告警说明品种不足。"""
        text = "长江电力（600900）是组合第十大持仓。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 0
        assert len(issues) == 1
        assert "持仓品种不足" in issues[0]

    # ── 表格句就近归因 ────────────────

    @pytest.fixture
    def table_holdings(self) -> list[dict]:
        """模拟真实组合：华安纳斯达克100 为第一、电池ETF 为第三。"""
        return [
            {"name": "华安纳斯达克100ETF联接A", "code": "040046", "market_value": 100000.0, "cost": 80000.0},
            {"name": "建信高端装备股票A", "code": "011506", "market_value": 50000.0, "cost": 45000.0},
            {"name": "招商中证电池主题ETF", "code": "561910", "market_value": 30000.0, "cost": 30010.0},
            {"name": "长江电力", "code": "600900", "market_value": 20000.0, "cost": 19000.0},
        ]

    def test_table_sentence_nearest_code_attribution(self, table_holdings):
        """表格句中的合法排名声称按所在行就近归因，不误报。

        LLM 以表格输出调仓方案，句中含多个代码：
        - "561910 ... 已是组合第三大持仓"（561910 实际第3，正确）
        - "040046 ... 组合第一大重仓"（040046 实际第1，正确）
        两处声称分别指向各自所在行内的品种，均通过校验。
        """
        text = (
            "操作建议|优先级|品种|建议操作|理由|| 🔴 高 | 561910 招商中证电池主题ETF | 减仓 | "
            "市场占比10.6%，已是组合第三大持仓却贡献负收益 || 🟢 低 | 040046 华安纳斯达克100ETF联接基金A | "
            "持有 | 收益率+1.16%，组合第一大重仓，继续持有"
        )
        issues, checked, passed = check_ranking_correctness(text, table_holdings)
        assert checked == 2  # 两处排名声称均被校验
        assert passed == 2
        assert issues == [], f"合法排名声称不应告警: {issues}"

    def test_table_sentence_wrong_claim_still_detected(self, table_holdings):
        """表格句中的错误排名声称 → 仍能检测（不因就近归因而漏检）。"""
        text = (
            "操作建议|优先级|品种|建议操作|理由|| 🔴 高 | 600900 长江电力 | 减仓 | "
            "已是组合第三大持仓却贡献负收益 || 🟢 低 | 561910 招商中证电池主题ETF | 持有 | "
            "收益率+1.16%，组合第一大重仓，继续持有"
        )
        issues, checked, passed = check_ranking_correctness(text, table_holdings)
        assert checked == 2
        assert passed == 0
        assert len(issues) == 2
        # 600900 实际第4，被声称"第三大持仓" → 告警
        assert any("600900" in i and "第3大持仓" in i for i in issues)
        # 561910 实际第3，被声称"第一大重仓" → 告警
        assert any("561910" in i and "最大持仓" in i for i in issues)

    # ── 非持仓排名语境不误判 ──────────────────────────────

    def test_max_single_loss_item_not_flagged(self, sample_holdings):
        """ "最大单项亏损品种" 是非持仓排名语境 → 不误判为排名声称。"""
        text = "561910 是组合最大单项亏损品种，需关注回撤风险。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_contributed_main_profit_not_flagged(self, sample_holdings):
        """ "贡献了主要利润" 是非持仓排名语境 → 不误判为排名声称。"""
        text = "601939 本季度贡献了主要利润，表现突出。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_max_loss_source_not_flagged(self, sample_holdings):
        """ "最大亏损来源" 是非持仓排名语境 → 不误判为排名声称。"""
        text = "600900 是组合最大亏损来源，拖累整体表现。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_max_feature_not_flagged(self, sample_holdings):
        """排名词 + 非持仓名词（特点/风险）→ 不误判为排名声称。"""
        text = "600900 最大特点是高股息，适合防守配置。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert issues == []
        assert checked == 0
        assert passed == 0

    def test_top3_holding_claim_still_detected(self, sample_holdings):
        """前三大持仓（合法排名声称）→ 仍被检测且正确通过（不破坏既有功能）。"""
        text = "组合前三大持仓依次为 600519、600036、300750。"
        issues, checked, passed = check_ranking_correctness(text, sample_holdings)
        assert checked == 1
        assert passed == 1  # 600519 是实际第一
        assert issues == []


class TestRunFactCheck:
    """统一入口 — run_fact_check 测试。"""

    def test_empty_content(self, sample_holdings):
        """空 HTML 内容 → 返回(原内容, 空字符串)。"""
        corr, summ = run_fact_check("", sample_holdings, "测试模块")
        assert corr == ""
        assert summ == ""

    def test_none_content(self, sample_holdings):
        """None 内容 → 原样返回 None，摘要为空（早退分支不触碰内容）。"""
        corr, summ = run_fact_check(None, sample_holdings, "测试模块")
        assert corr is None
        assert summ == ""

    def test_all_checks_pass(self, sample_holdings):
        """所有检查通过 → 绿色摘要。"""
        html = """<p>贵州茅台（600519）是组合最大持仓。</p>
<p>组合累计收益率为 30.3%。</p>"""
        corr, summ = run_fact_check(html, sample_holdings, "智囊团深度复盘")
        assert summ != ""
        assert "事实校验通过" in summ
        assert "color:#4a4" in summ  # 绿色
        assert "智囊团深度复盘" in summ

    def test_with_issues(self, sample_holdings):
        """存在不一致 → 黄色告警摘要 + 自动修正。"""
        html = """<p>招商银行（600036）是组合最大持仓。</p>
<p>组合累计收益率为 5.0%。</p>"""
        corr, summ = run_fact_check(html, sample_holdings, "持仓体检报告")
        assert summ != ""
        assert "事实校验" in summ
        assert "项通过" in summ
        assert "color:#a40" in summ  # 黄色
        assert "持仓体检报告" in summ
        assert "600036" in summ
        # 自动修正：5.0% → 30.3%
        assert "30.3%" in corr
        assert "5.0%" not in corr

    def test_no_module_label(self, sample_holdings):
        """无 module_label 时摘要不包含标签前缀。"""
        html = "<p>贵州茅台（600519）是组合最大持仓。</p>"
        corr, summ = run_fact_check(html, sample_holdings)
        assert summ != ""
        assert "[贵州茅台" not in summ  # 模块标签标记不出现
        assert "事实校验通过" in summ

    def test_holdings_none(self):
        """holdings_details 为 None → 跳过品种和排名检查，只检数值。"""
        # 纯文本不含百分比 → 0 checks
        html = "<p>贵州茅台是组合最大持仓。</p>"
        corr, summ = run_fact_check(html, None, "测试")
        assert corr == html  # 内容不变
        assert summ == ""  # 没有代码可检（纯中文）也没百分比

    def test_integration_full_html(self, sample_holdings):
        """模拟真实 LLM HTML 内容做完整端到端校验。"""
        html = """<h2>组合回顾</h2>
<p>本季度贵州茅台（600519）作为组合最大持仓继续领跑，白酒板块整体向好。</p>
<p>招商银行（600036）表现稳健，宁德时代（300750）受新能源政策提振。</p>
<p>组合累计收益率为 30.3%，跑赢沪深300指数（000300）。</p>"""
        corr, summ = run_fact_check(html, sample_holdings, "智囊团深度复盘")
        assert summ != ""
        # 代码检查：600519✓, 600036✓, 300750✓, 000300(指数跳过) — 全部通过
        # 排名检查：600519 是最大持仓 ✓
        # 数值检查：30.3% ≈ 30.28% ✓
        assert "事实校验通过" in summ

    def test_empty_holdings_edge(self):
        """空持仓列表 — 品种和排名检查跳过，数值检查至少不崩溃。"""
        html = "<p>组合累计收益率为 5.0%。</p>"
        corr, summ = run_fact_check(html, [], "测试")
        # 空持仓时 profit_rate=0，"5.0%" 不匹配但上下文不含收益关键词，跳过
        # 无论是否通过，不应崩溃
        assert isinstance(corr, str)
        assert isinstance(summ, str)

    # ── 缓存命中跳过排名校验 ──────────────────────────────

    def test_skip_ranking_check_skips_stale_rank_claim(self, sample_holdings):
        """缓存命中内容含过期排名声称：skip_ranking_check=True → 不报排名误报。

        600036 是实际第 2 大持仓，声称其为最大持仓在默认校验下会告警；
        但缓存内容基于生成时价格快照，当前排名可能已翻转 → 缓存命中场景应跳过排名校验。
        数值/品种校验仍执行。
        """
        html = "<p>招商银行（600036）是组合最大持仓。</p>"
        corr, summ = run_fact_check(
            html,
            sample_holdings,
            "智囊团深度复盘",
            skip_ranking_check=True,
        )
        # 排名校验被跳过 → 无"声称最大持仓"误报
        assert "最大持仓" not in summ
        # 600036 为真实持仓 → 品种存在性通过，无其他告警 → 全部通过
        assert "事实校验通过" in summ

    def test_skip_ranking_check_still_corrects_numbers(self, sample_holdings):
        """缓存命中跳过排名校验但数值自动修正仍生效（保留数值修正）。"""
        html = """<p>招商银行（600036）是组合最大持仓。</p>
<p>组合累计收益率为 5.0%。</p>"""
        corr, summ = run_fact_check(
            html,
            sample_holdings,
            "持仓体检报告",
            skip_ranking_check=True,
        )
        # 排名误报不出现
        assert "最大持仓" not in summ
        # 数值修正仍生效：5.0% → 30.3%
        assert "30.3%" in corr
        assert "5.0%" not in corr
        assert "自动修正 1 处数值" in summ

    def test_ranking_check_active_by_default(self, sample_holdings):
        """默认（skip_ranking_check=False）：过期排名声称仍被检出（不破坏既有功能）。"""
        html = "<p>招商银行（600036）是组合最大持仓。</p>"
        corr, summ = run_fact_check(html, sample_holdings, "智囊团深度复盘")
        assert "600036" in summ
        assert "最大持仓" in summ

    def test_corrections_detail_in_summary(self, sample_holdings):
        """自动修正后摘要列出修正明细（wrong%→correct% + 语义 reason），供用户直接查看。"""
        html = """<p>招商银行（600036）是组合最大持仓。</p>
<p>组合累计收益率为 5.0%。</p>"""
        corr, summ = run_fact_check(html, sample_holdings, "智囊团深度复盘")
        # 内容中 5.0% 已被替换为 30.3%
        assert "30.3%" in corr
        assert "5.0%" not in corr
        # 摘要追加灰色「已修正明细」行，含 wrong→correct 与语义 reason
        # （语义 reason 替代原截断句段，说明修正的是哪个数字的含义）
        assert "已修正明细" in summ
        assert "5.0%→30.3%" in summ
        assert "组合实际收益率30.3%" in summ

    def test_run_fact_check_change_rate_not_corrected(self, sample_holdings):
        """run_fact_check 整链路：环比变化率不被自动修正。

        持仓体检"环比对比中总市值变化-96.02%"是相对上期的变化率，与收益率
        维度不同，直接比较会误修正。环比变化率跳过数值校验，内容不被篡改，
        摘要无修正明细。
        """
        html = (
            "<p>组合整体稳健。与上月环比对比，组合总市值大幅下跌96.02%，"
            "总盈亏变化+3,263，主要受到重仓个股回调影响。</p>"
        )
        corr, summ = run_fact_check(html, sample_holdings, "持仓体检报告")
        assert corr == html  # 内容不被篡改（96.02% 保留）
        assert "96.02%" in corr
        assert "已修正明细" not in summ  # 无修正明细
        assert "事实校验通过" in summ

    def test_corrections_logged(self, sample_holdings, caplog):
        """自动修正明细写入日志（含模块标签 + wrong→correct 明细）。"""
        import logging

        html = """<p>招商银行（600036）是组合最大持仓。</p>
<p>组合累计收益率为 5.0%。</p>"""
        with caplog.at_level(logging.INFO, logger="invest"):
            run_fact_check(html, sample_holdings, "智囊团深度复盘")
        joined = caplog.text
        assert "智囊团深度复盘" in joined
        assert "自动修正 1 处数值" in joined
        assert "5.0%→30.3%" in joined
