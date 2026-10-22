"""性能基准报告渲染（Markdown 组装 + 达标判定），纯函数、零 I/O 之外仅落盘一次。"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime

#: 性能基准目标秒数（报告达标判定与 --gate 退出码共用口径）
_TARGET_SECONDS = 60

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPORT_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "docs", "tmp")
_PERF_REPORT_PATH = os.path.join(_REPORT_OUTPUT_DIR, "better-investment-performance-test-report.md")


@dataclass(frozen=True)
class PerfSample:
    """单阶段样本规模（报告文案的真值来源：文案按实际数量出，不写死）。"""

    holdings: int
    stocks: int
    funds: int


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
