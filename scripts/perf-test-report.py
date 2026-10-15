#!/usr/bin/env python3
"""端到端性能基准测试 — 全量报告生成管线计时。

生成模拟持仓（规模见 ``_PHASE1_STOCK_COUNT`` / ``_PHASE3_STOCK_COUNT``，实际数量
以 ``len(holdings)`` 为准），运行 basic/both 报告生成管线，测量各阶段耗时，
输出性能报告 Markdown。

用法：
  python scripts/perf-test-report.py
  python scripts/perf-test-report.py --gate          # 门禁模式：未达标退出码 2（供 CI 拦截）

输出：
  docs/tmp/better-investment-performance-test-report.md

目标：
  - basic 模式总耗时 < 60s

定位说明：本脚本是**性能测试**（主动压测）——自造模拟持仓、mock 外部数据源，
同条件可比，故适合做 CI 门禁（退化即回归）。运行历史查看（被动统计既有记录、
样本不可控）由 `perf-view.py` 承担，**不用于门禁**。
"""

from __future__ import annotations

import logging
import argparse
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

# ── 项目路径 ─────────────────────────────────────

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

# ── 常量 ─────────────────────────────────────────

_TARGET_SECONDS = 60  # 性能基准目标
_PHASE1_STOCK_COUNT = 20  # Phase1/2 股票取样数（场外基金另见 SAMPLE_FUNDS）
_PHASE3_STOCK_COUNT = 50  # Phase3 压力股票取样数（须 ≤ len(SAMPLE_STOCKS)，否则被样本池截断）
_REPORT_OUTPUT_DIR = os.path.join(
    _PROJECT_ROOT,
    "docs",
    "tmp",
)
_PERF_REPORT_PATH = os.path.join(_REPORT_OUTPUT_DIR, "better-investment-performance-test-report.md")

# ── 行情/K线历史/交易日历离线桩 ───────────────────
#
# 门禁相关的三阶段必须与网络条件无关：真实行情抓取（Tencent/Sina K 线）走同源
# 重试退避，交易日历首拉 akshare（Sina 源）——CI 冷缓存或端点变慢时，门禁会测成
# 「网络状况」而非「代码性能」（实测：断网后 Phase1 从个位数秒级涨到四十余秒，
# 全耗在 K 线重试退避上；桩后断网 Phase1=2.3s / Phase3=2.1s）。桩钉在咽喉而非
# 各调用点：
#   ① fetch_market_data —— 行情链唯一入口。函数内 import 的调用方
#      （基金风格分类等）读 fetcher.price 模块属性，市值核算是模块级绑定，
#      故两处都钉；
#   ② trading_calendar._get_trading_calendar —— 日历模块唯一网络出口
#      （ak.tool_trade_date_hist_sina）。所有日历函数经它取集合，钉住即全链离线
#      （含各模块模块级绑定的 get_last_trading_day）；
#   ③ chain/chain_incremental 的 fetch_with_incremental_fallback —— K 线/历史链
#      唯一入口（流动性检查、风格因子、事件面板、市场情绪逐仓拉历史都经它）。
#      注：portfolio_history 是模块级绑定，但其仅在 fetch_history=True 路径生效，
#      本脚本 Phase 2 显式传 False，不入桩。
#
# 边界：Phase 2 的新闻/财报类抓取仍走真实网络（断网自动降级，实测 26s 内完成，
# 且其耗时不入门禁判定——门禁只看 basic 即 Phase 1），故不为它们编造返回契约。


def _last_workday_str() -> str:
    """最近一个工作日（YYYY-MM-DD，仅去周末，无节假日感知——基准用）。"""
    day = date.today()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


def _stub_trading_calendar() -> set[str]:
    """交易日历桩：近 400 天 + 未来 30 天的工作日集合（零网络）。"""
    dates: set[str] = set()
    day = date.today() - timedelta(days=400)
    end = date.today() + timedelta(days=30)
    while day <= end:
        if day.weekday() < 5:
            dates.add(day.isoformat())
        day += timedelta(days=1)
    return dates


def _mock_bars(chain_name: str, code: str, days: int = 30, **_kw: Any) -> list[dict[str, Any]]:
    """历史K线桩：约 `days` 自然日窗口内的工作日 OHLC 序列（确定性、升序、零网络）。

    至少返回 5 根（极短窗口/周末起步也要给出可计算样本）；收盘价带周期性波动，
    保证收益率/流动性类计算不会除零。
    """
    target = max(5, int(days) * 5 // 7)
    rows: list[dict[str, Any]] = []
    day = date.today()
    while len(rows) < target:
        if day.weekday() < 5:
            idx = len(rows)
            close = 10.0 + (idx % 7) * 0.1
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": round(close - 0.05, 2),
                    "high": round(close + 0.1, 2),
                    "low": round(close - 0.15, 2),
                    "close": close,
                    "volume": 1_000_000 + idx * 1000,
                    "code": code,
                }
            )
        day -= timedelta(days=1)
    rows.reverse()
    return rows


def _mock_quote(code: str, expected_name: str = "") -> dict[str, Any]:
    """行情桩：固定价格，让市值/盈亏/行情明细走真实计算路径（而非降级占位）。

    与 `fetch_market_data(code, expected_name)` 同签名；键集满足明细行消费
    （price/yesterday_close/price_date/source/source_api/name）。
    """
    return {
        "price": 10.0,
        "yesterday_close": 9.9,
        "price_date": _last_workday_str(),
        "source": "性能测试桩",
        "source_api": "tencent",
        "name": expected_name or "",
    }


# ── LLM 生成 mock ─────────────────────────────────
#
# patch 目标必须是**包属性**：调用点 `report/_llm_news._submit_llm_future` 在函数内
# `from src.python.llm import generate_all_llm`，每次调用都读 `src.python.llm` 包属性；
# patch `generators_orchestrator` 子模块属性不会覆盖该读取点（子模块与包是两个名字空间）。
_LLM_MOCK_TARGET = "src.python.llm.generate_all_llm"
#: 与 `generate_all_llm` 返回契约同构：4 个模块内容 + 4 个缓存标志（辩论信息缺省不带）
_LLM_MOCK_VALUE = (
    "<p>因性能测试跳过 LLM：全球政经局势占位</p>",
    "<p>因性能测试跳过 LLM：智囊团深度复盘占位</p>",
    "<p>因性能测试跳过 LLM：持仓体检占位</p>",
    "<p>因性能测试跳过 LLM：穿透深度分析占位</p>",
    False,
    False,
    False,
    False,
)

# ── 样本池 ───────────────────────────────────────

#: 股票样本池（账户口径「证券账户」；含港股非 6 位代码，分类一律按账户不按代码位数）
SAMPLE_STOCKS: list[tuple[str, str]] = [
    ("贵州茅台", "600519"),
    ("长江电力", "600900"),
    ("招商银行", "600036"),
    ("宁德时代", "300750"),
    ("中国平安", "601318"),
    ("五粮液", "000858"),
    ("腾讯控股", "00700"),
    ("美团-W", "03690"),
    ("药明康德", "603259"),
    ("迈瑞医疗", "300760"),
    ("恒瑞医药", "600276"),
    ("隆基绿能", "601012"),
    ("比亚迪", "002594"),
    ("伊利股份", "600887"),
    ("海康威视", "002415"),
    ("工商银行", "601398"),
    ("建设银行", "601939"),
    ("中国中免", "601888"),
    ("万华化学", "600309"),
    ("中兴通讯", "000063"),
    ("紫金矿业", "601899"),
    ("中国神华", "601088"),
    ("美的集团", "000333"),
    ("海尔智家", "600690"),
    ("中国石油", "601857"),
    ("中国石化", "600028"),
    ("京东方A", "000725"),
    ("万科A", "000002"),
    ("格力电器", "000651"),
    ("泸州老窖", "000568"),
    ("洋河股份", "002304"),
    ("山西汾酒", "600809"),
    ("中国人寿", "601628"),
    ("中国太保", "601601"),
    ("中国中铁", "601390"),
    ("中国铁建", "601186"),
    ("中国建筑", "601668"),
    ("工业富联", "601138"),
    ("韦尔股份", "603501"),
    ("汇川技术", "300124"),
    ("亿纬锂能", "300014"),
    ("阳光电源", "300274"),
    ("国电南瑞", "600406"),
    ("上海机场", "600009"),
    ("南方航空", "600029"),
    ("中国国航", "601111"),
    ("云南白药", "000538"),
    ("恒生电子", "600570"),
    ("三一重工", "600031"),
    ("潍柴动力", "000338"),
]

#: 场外基金样本池（账户口径「基金账户」），两个 Phase 均全量追加
SAMPLE_FUNDS: list[tuple[str, str]] = [
    ("易方达蓝筹精选", "005827"),
    ("招商中证白酒", "161725"),
    ("富国天惠成长", "161005"),
]


@dataclass(frozen=True)
class PerfSample:
    """单阶段样本规模（报告文案的真值来源：文案按实际数量出，不写死）。"""

    holdings: int
    stocks: int
    funds: int


# ── 持仓生成 ─────────────────────────────────────


def _generate_holdings(count: int = _PHASE1_STOCK_COUNT) -> list[Any]:
    """生成模拟持仓数据。

    股票按 ``count`` 从 :data:`SAMPLE_STOCKS` 取样（样本池不足时以池大小为上限，
    实际股票数 = ``min(count, len(SAMPLE_STOCKS))``），场外基金全量追加
    （:data:`SAMPLE_FUNDS`）——因此实际持仓总数 = 取样股票数 + 场外基金数，
    报告文案按 ``len(...)`` 派生，不按请求值写死。

    生成的品种涵盖股票、港股、场外基金等类型，确保管线全路径覆盖。
    """
    from src.python.core.models import Holding

    holdings: list[Any] = []
    import random

    random.seed(42)

    for name, code in SAMPLE_STOCKS[:count]:
        holdings.append(
            Holding(
                account="证券账户",
                name=name,
                code=code,
                shares=round(random.uniform(100, 5000), 2),
                cost_price=round(random.uniform(5, 500), 2),
            )
        )

    for name, code in SAMPLE_FUNDS:
        holdings.append(
            Holding(
                account="基金账户",
                name=name,
                code=code,
                shares=round(random.uniform(500, 20000), 2),
                cost_price=round(random.uniform(0.5, 5), 2),
            )
        )

    return holdings


def _sample_of(holdings: list[Any]) -> PerfSample:
    """按**账户口径**统计样本规模（证券账户=股票、基金账户=场外基金）。

    不按代码位数分类：港股代码非 6 位，按位数会把港股股票误计为场外基金。
    """
    stocks = sum(1 for h in holdings if h.account == "证券账户")
    return PerfSample(holdings=len(holdings), stocks=stocks, funds=len(holdings) - stocks)


# ── 模拟详情生成 ──────────────────────────────────


def _generate_details(holdings: list[Any]) -> list[Any]:
    """生成模拟 DetailRow 数据结构。"""
    import random

    from src.python.report.market_value import DetailRow

    random.seed(42)

    details: list[DetailRow] = []
    for h in holdings:
        cost = round(h.shares * h.cost_price, 2)
        price = round(h.cost_price * random.uniform(0.8, 2.5), 2)
        market_value = round(h.shares * price, 2)
        profit = round(market_value - cost, 2)
        profit_rate = round(profit / cost, 4) if cost else 0.0
        today_profit = round(profit * random.uniform(-0.02, 0.03), 2)

        details.append(
            DetailRow(
                account=h.account,
                name=h.name,
                code=h.code,
                price=price,
                market_value=market_value,
                cost=cost,
                profit=profit,
                profit_rate=profit_rate,
                today_profit=today_profit,
                shares=h.shares,
            )
        )
    return details


# ── 性能基准主要流程 ─────────────────────────────


def _isolate_state_writes() -> str:
    """状态隔离：把 perf 历史/数据源健康快照重定向到临时目录。

    基准运行不得把记录写进真实 `perf_history.jsonl` / `datasource_health.jsonl`——
    否则会污染运行历史视图的统计样本（perf-view 的分位/离群分析直接受此影响）。
    两者都是 perf.py 的模块级变量（该文件头注明「测试时可通过 setattr 重定向」），
    直接改写；本脚本是一次性 CLI，无需还原。

    Returns:
        隔离目录路径
    """
    from src.python.core import perf as _perf_state

    iso_dir = tempfile.mkdtemp(prefix="perf_bench_state_")
    _perf_state._PERF_HISTORY_FILE = os.path.join(iso_dir, "perf_history.jsonl")
    _perf_state._HEALTH_CHECK_FILE = os.path.join(iso_dir, "datasource_health.jsonl")
    return iso_dir


def run_perf_test() -> tuple[dict[str, float], PerfSample, PerfSample]:
    """执行性能基准测试，返回（各阶段耗时, Phase1/2 样本规模, Phase3 样本规模）。"""
    from unittest.mock import patch

    from src.python.report.excel_generator import generate_excel_report
    from src.python.report.progress import SilentProgressReporter

    _isolate_state_writes()

    timings: dict[str, float] = {}

    # 生成测试数据
    print("\n[..] 生成测试持仓数据...")
    t0 = time.perf_counter()
    holdings = _generate_holdings(_PHASE1_STOCK_COUNT)
    details = _generate_details(holdings)
    t1 = time.perf_counter()
    data_gen_time = round(t1 - t0, 4)
    timings["data_generation"] = data_gen_time
    phase1_sample = _sample_of(holdings)
    print(f"  [{data_gen_time:7.2f}s] 生成 {phase1_sample.holdings} 品种持仓数据")
    print(f"  {phase1_sample.holdings} 品种（含 {phase1_sample.stocks} 股票 + {phase1_sample.funds} 基金）")

    reporter = SilentProgressReporter()
    tmp_dir = tempfile.TemporaryDirectory()
    config = {
        "output_dir": tmp_dir.name,
    }

    # ── Phase 1: basic 报告生成（Excel only） ──
    print("\n[..] Phase 1: basic 模式报告生成 (Excel)...")
    with (
        patch("src.python.fetcher.index.fetch_indices", return_value={}),
        patch("src.python.fetcher.index.fetch_us_indices", return_value={}),
        patch("src.python.report.fund_performance.write_fund_performance_sheet"),
        patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={}),
        patch("src.python.fetcher.fund.fetch_fund_rankings", return_value=None),
        # 行情/K线历史/交易日历离线桩（咽喉点说明见 _mock_quote 处）
        patch("src.python.fetcher.price.fetch_market_data", new=_mock_quote),
        patch("src.python.report.market_value.fetch_market_data", new=_mock_quote),
        patch("src.python.core.trading_calendar._get_trading_calendar", new=_stub_trading_calendar),
        patch("src.python.fetcher.chain.fetch_with_incremental_fallback", new=_mock_bars),
        patch("src.python.fetcher.chain_incremental.fetch_with_incremental_fallback", new=_mock_bars),
    ):
        t_start = time.perf_counter()
        generate_excel_report(
            holdings,
            include_news=False,
            output_dir=tmp_dir.name,
            details=details,
            progress=reporter,
            a_indices={},
            us_indices={},
        )
        t_elapsed = time.perf_counter() - t_start

    timings["phase1_basic_excel"] = round(t_elapsed, 2)
    print(f"  [{t_elapsed:7.2f}s] basic Excel 报告完成")

    # ── Phase 2: both 模式（Excel + HTML，不含LLM） ──
    print("\n[..] Phase 2: both 模式报告生成 (Excel+HTML)...")
    with (
        patch("src.python.fetcher.index.fetch_indices", return_value={}),
        patch("src.python.fetcher.index.fetch_us_indices", return_value={}),
        patch("src.python.report.fund_performance.write_fund_performance_sheet"),
        patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={}),
        patch("src.python.fetcher.fund.fetch_fund_rankings", return_value=None),
        patch(_LLM_MOCK_TARGET, return_value=_LLM_MOCK_VALUE),
        # 行情/K线历史/交易日历离线桩（咽喉点说明见 _mock_quote 处）
        patch("src.python.fetcher.price.fetch_market_data", new=_mock_quote),
        patch("src.python.report.market_value.fetch_market_data", new=_mock_quote),
        patch("src.python.core.trading_calendar._get_trading_calendar", new=_stub_trading_calendar),
        patch("src.python.fetcher.chain.fetch_with_incremental_fallback", new=_mock_bars),
        patch("src.python.fetcher.chain_incremental.fetch_with_incremental_fallback", new=_mock_bars),
    ):
        # 公开 API（generate_report 报告类型分发），不依赖编排层内部私有函数
        from src.python.report.orchestrator import generate_report

        t_start = time.perf_counter()
        result = generate_report(
            holdings,
            config,
            reporter,
            report_type="both",
            fetch_history=False,
            output_dir=tmp_dir.name,
        )
        t_elapsed = time.perf_counter() - t_start

    timings["phase2_both_html_excel"] = round(t_elapsed, 2)
    print(f"  [{t_elapsed:7.2f}s] both Excel+HTML 报告完成")
    print(f"  Excel OK: {result.excel_ok}, HTML OK: {result.html_ok}")

    # ── Phase 3: 大持仓压力测试 ──
    large_holdings = _generate_holdings(_PHASE3_STOCK_COUNT)
    large_details = _generate_details(large_holdings)
    phase3_sample = _sample_of(large_holdings)
    print(f"\n[..] Phase 3: 大持仓压力测试 ({phase3_sample.holdings}品种, basic)...")
    print(f"  {phase3_sample.holdings} 品种（含 {phase3_sample.stocks} 股票 + {phase3_sample.funds} 基金）")

    with (
        patch("src.python.fetcher.index.fetch_indices", return_value={}),
        patch("src.python.fetcher.index.fetch_us_indices", return_value={}),
        patch("src.python.report.fund_performance.write_fund_performance_sheet"),
        patch("src.python.fetcher.industry.batch_fetch_industry_data", return_value={}),
        patch("src.python.fetcher.fund.fetch_fund_rankings", return_value=None),
        # 行情/K线历史/交易日历离线桩（咽喉点说明见 _mock_quote 处）
        patch("src.python.fetcher.price.fetch_market_data", new=_mock_quote),
        patch("src.python.report.market_value.fetch_market_data", new=_mock_quote),
        patch("src.python.core.trading_calendar._get_trading_calendar", new=_stub_trading_calendar),
        patch("src.python.fetcher.chain.fetch_with_incremental_fallback", new=_mock_bars),
        patch("src.python.fetcher.chain_incremental.fetch_with_incremental_fallback", new=_mock_bars),
    ):
        t_start = time.perf_counter()
        generate_excel_report(
            large_holdings,
            include_news=False,
            output_dir=tmp_dir.name,
            details=large_details,
            progress=reporter,
            a_indices={},
            us_indices={},
        )
        t_elapsed = time.perf_counter() - t_start

    timings["phase3_stress_large"] = round(t_elapsed, 2)
    print(f"  [{t_elapsed:7.2f}s] {phase3_sample.holdings}品种 basic Excel 报告完成")

    # ── 清理 ──
    tmp_dir.cleanup()

    return timings, phase1_sample, phase3_sample


# ── 报告生成 ─────────────────────────────────────


def _verdict(seconds: float, target: float = _TARGET_SECONDS) -> str:
    """达标判定文案（≤ 目标值即达标）。"""
    if seconds <= target:
        return f"✅ 达标（≤{target}s）"
    return f"❌ 超标（>{target}s）"


def _test_time_text(now: datetime | None = None) -> str:
    """报告「测试时间」行文本——按传入时刻或当前时刻动态生成。"""
    if now is None:
        now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def _size_text(sample: PerfSample) -> str:
    """样本规模文案（按实际数量派生）。"""
    return f"{sample.holdings} 品种（{sample.stocks} 股票 + {sample.funds} 场外基金）"


def write_perf_report(timings: dict[str, float], phase1: PerfSample, phase3: PerfSample) -> str:
    """生成性能测试报告 Markdown 文件。

    Args:
        timings: 各阶段耗时（``run_perf_test`` 产出）。
        phase1: Phase1/2 实际样本规模（文案真值来源）。
        phase3: Phase3 实际样本规模（文案真值来源）。
    """
    os.makedirs(os.path.dirname(_PERF_REPORT_PATH), exist_ok=True)

    basic_time = timings.get("phase1_basic_excel", 0)
    both_time = timings.get("phase2_both_html_excel", 0)
    stress_time = timings.get("phase3_stress_large", 0)
    data_gen = timings.get("data_generation", 0)
    total = round(basic_time + both_time + stress_time, 2)

    lines = [
        "# 端到端性能测试报告",
        "",
        "## 概述",
        "",
        f"- **测试时间**: {_test_time_text()}",
        f"- **持仓规模**: Phase1/2: {_size_text(phase1)}，Phase3: {_size_text(phase3)}",
        "- **测试模式**: basic（仅 Excel）/ both（Excel+HTML）",
        "- **性能目标**: basic 模式 ≤ 60s",
        "",
        "## 各阶段耗时",
        "",
        "| 阶段 | 耗时 | 判定 | 说明 |",
        "|:-----|-----:|:----|:-----|",
        f"| 数据准备（持仓+详情模拟） | {data_gen:.2f}s | — | 合成 {phase1.holdings} 品种持仓与详情数据 |",
        f"| Phase 1: basic Excel | {basic_time:.2f}s | {_verdict(basic_time)} | 仅 Excel 生成，不含数据获取/LLM |",
        f"| Phase 2: both HTML+Excel | {both_time:.2f}s | — | HTML + Excel 双输出，不含 LLM |",
        f"| Phase 3: {phase3.holdings}品种压力测试 | {stress_time:.2f}s | — | 大持仓场景下的 Excel 生成 |",
        f"| **合计** | **{total:.2f}s** | — | 三个阶段串联总耗时 |",
        "",
        "## 性能基准结论",
        "",
        "### basic 模式（Phase 1）",
        f"**{_verdict(basic_time)}**。",
        f"{_size_text(phase1)}basic 报告生成耗时 **{basic_time:.2f}s**，"
        f"{'达到' if basic_time <= _TARGET_SECONDS else '未达到'}性能目标 {_TARGET_SECONDS}s。",
        "",
        "### both 模式（Phase 2）",
        f"HTML + Excel 双输出耗时 **{both_time:.2f}s**。",
        "不含 LLM 分析生成。",
        "",
        "### 大持仓压力测试（Phase 3）",
        f"{_size_text(phase3)}basic Excel 生成耗时 **{stress_time:.2f}s**。",
        "",
        "## 环境",
        "",
        f"- **平台**: {sys.platform}",
        f"- **Python**: {sys.version.split()[0]}",
        "",
        "## 备注",
        "",
        "- 所有外部数据源（指数、基金排行、行业分类、概念数据）均已 mock，",
        "  测试结果仅反映本地计算管线性能",
        "- LLM 生成环节已 mock 跳过，实际 full 模式会额外增加 LLM 调用耗时",
        "- 实际耗时受硬件配置、磁盘速度、缓存状态等因素影响",
        "",
    ]

    report = "\n".join(lines) + "\n"
    with open(_PERF_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    return _PERF_REPORT_PATH


# ── 入口 ─────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="端到端性能基准测试")
    parser.add_argument(
        "--gate",
        action="store_true",
        help="门禁模式：未达标时退出码 2（与检查脚本契约一致，供 CI 拦截性能回归）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  端到端性能基准测试")
    print("=" * 60)

    timings, phase1_sample, phase3_sample = run_perf_test()

    print("\n" + "=" * 60)
    print("  生成性能报告...")
    report_path = write_perf_report(timings, phase1_sample, phase3_sample)
    print(f"  [OK] 报告已写入: {report_path}")

    basic_time = timings.get("phase1_basic_excel", 0)
    passed = basic_time <= _TARGET_SECONDS
    if passed:
        print(f"\n[OK] basic 模式达标: {basic_time:.2f}s ≤ {_TARGET_SECONDS}s")
    else:
        print(f"\n[ERR] basic 模式未达标: {basic_time:.2f}s > {_TARGET_SECONDS}s")

    print("=" * 60)
    if args.gate:
        # 门禁模式：退出码 2 = 发现 finding（与检查脚本契约一致）
        return 0 if passed else 2
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
