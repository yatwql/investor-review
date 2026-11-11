"""both 路径：HTML+Excel（不含 LLM 章节）生成编排。"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING


if TYPE_CHECKING:  # ReportResult 定义在编排门面，运行期从生成入口传入（避免循环导入）
    from src.python.report.orchestrator import ReportResult
from src.python.report.progress import ProgressReporter
from src.python.report._report_output import (  # noqa: F401  # 产物落盘子模块（消费方在本门面，patch 点不变）
    _generate_full_excel_report,
    _generate_full_html_report,
)

# ── 子模块 re-export ────────────────────────────────────
# 健康检查与运行边界仍是本路径的编排水位（patch 点在此）：消费方就是下面的壳。
from src.python.report._report_health import _collect_health_checks, _spawn_health_checks  # noqa: F401
from src.python.report.run_integrity import bind_health, bind_perf
from src.python.report._report_helpers import (  # noqa: F401
    _validate_pipeline_snapshot,
    _validate_prep_completeness,
)

logger = logging.getLogger("invest")


def _generate_report_both(
    holdings: list,
    config: dict,
    reporter: ProgressReporter,
    fetch_history: bool = False,
    output_dir: str | None = None,
    transactions: list | None = None,
    dividends: list | None = None,
    *,
    snapshot_namespace: str | None = None,
) -> "ReportResult":
    """both 报告路径：生成 HTML + Excel，不含 LLM 分析章节。

    流程：_compute_details() → capture_snapshot() → fetch_history_data()
          → write_html_report() → generate_excel_report()

    Args:
        snapshot_namespace: 快照隔离域（None=共享主目录；如 "web"=web 试算域）。
            快照对比/组合演进/快照差异均在本域内闭环，不污染共享时间线。
    """
    from src.python.core.cancel import token_of
    from src.python.core.perf import PerfCollector
    from src.python.report._both_stages import BothRun, resolve_both_options, stage_runner
    from src.python.report.orchestrator import ReportResult

    from src.python.report._run_scope import finish_report_run, start_report_run

    perf = PerfCollector(
        report_type="both",
        holdings=holdings,
        stage_announcer=reporter.stage_progress,
        cancel_token=token_of(reporter),
    )
    bind_perf(perf)
    # 报告运行边界：清本轮降级事件与自检载体（both 路径不调 LLM，无需用量基线）
    start_report_run()
    result = ReportResult()
    result.holdings_ok = True

    # 后台启动健康检查（与数据获取并行，收尾统一收集）
    _health_fut = _spawn_health_checks()
    bind_health(_health_fut, "both", holdings)

    # 五阶段按 `BOTH_STAGES` 表执行（阶段名即 perf 口径，start/stop 由 stage_runner 配对）
    stage_runner(
        BothRun(
            holdings=holdings,
            config=config,
            reporter=reporter,
            fetch_history=fetch_history,
            transactions=transactions,
            dividends=dividends,
            snapshot_namespace=snapshot_namespace,
            options=resolve_both_options(config, output_dir),
            perf=perf,
            result=result,
        )
    )

    result.report_generated = result.html_ok or result.excel_ok
    finish_report_run(perf)
    _collect_health_checks(_health_fut, "both", holdings)
    return result
