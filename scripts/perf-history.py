#!/usr/bin/env python3
"""性能历史趋势查看工具 — Layer 3：跨版本耗时趋势可视化。

读取 data/state/perf_history.jsonl，按版本和报告类型分组统计，
输出版本间性能趋势对比 Markdown 表格；另输出跨版本「总体分位概览」，
给出 P95 / P99 报告生成耗时（最近秩分位：95% 的报告在该耗时内完成，99% 的报告在该耗时内完成）。

用法：
  python scripts/perf-history.py                          # 输出到 stdout
  python scripts/perf-history.py --save                   # 同时写入 docs/tmp/perf_trend.md
  python scripts/perf-history.py --report-type full       # 仅查看 full 类型
  python scripts/perf-history.py --last 30                # 仅查看最近 30 条记录
  python scripts/perf-history.py --exclude-outlier        # 剔除离群运行（稳健口径）
  python scripts/perf-history.py --by day                 # 按时段聚合（day/week/hour）
  python scripts/perf-history.py --compare 0.13.3 0.13.4  # 版本间阶段级对比
  python scripts/perf-history.py --json                   # 机读输出（JSON）
  python scripts/perf-history.py --csv                    # 机读输出（CSV）
  python scripts/perf-history.py --summary                # 仅输出概览段（略去逐版本分组）
  python scripts/perf-history.py --outlier-k 4.0          # 自定义离群判定系数（默认 3.5）

归因能力：版本演进总表、离群点标注（中位 ± MAD）、稳健均值、阶段级分位、尾部归因
（最慢运行逐阶段 z 分数）、异常运行专区（中断/失败）、同版本漂移检测（渐进劣化）、
秒/品种归一化、小样本分位提示、时段聚合、版本间对比、机读输出（记录 + 汇总信封）。

定位说明：本脚本是**运行历史查看**（被动统计既有记录），不是性能测试——
样本取决于最近跑过什么，不可复现，故**不用于 CI 门禁**；性能门禁由主动压测的
`test-perf-report.py` 承担（同条件可比，退化即回归）。
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# 实现按职责拆在 scripts/_perf_history/：data（派生）/ report（渲染）/ cli（入口）；
# 此处 re-export 既有符号，保持 load_script 的测试直调面不变。
from _perf_history.cli import main  # noqa: E402
from _perf_history.data import (  # noqa: E402, F401
    _bucket_key,
    _compare_versions,
    _cost_period_data,
    _drift_data,
    _is_abnormal_record,
    _llm_cost_data,
    _machine_readable,
    _machine_summary,
    _slowest_phase,
    _version_evolution_data,
    _version_records,
)
from _perf_history.report import (  # noqa: E402, F401
    _TREND_REPORT_PATH,
    _TMP_DIR,
    _abnormal_lines,
    _bucket_lines,
    _compare_lines,
    _drift_lines,
    _freshness_line,
    _llm_context_lines,
    _outlier_lines,
    _overview_lines,
    _tail_attribution_lines,
    _version_evolution_lines,
    build_trend_report,
)
from _perf_history.stats import (  # noqa: E402, F401
    _DRIFT_MIN_SAMPLES,
    _OUTLIER_K,
    _cv,
    _filter_records,
    _group_by_version_type,
    _group_filtered,
    _group_records,
    _is_outlier,
    _mad,
    _mean,
    _median,
    _merge_breakdown_stats,
    _merge_phase_stats,
    _min_max,
    _outlier_records,
    _outlier_threshold,
    _per_holding_median,
    _percentile,
    _robust_mean,
    _stdev,
    _total_summary,
    _z_scores,
)
from src.python.core.perf import load_history  # noqa: E402, F401


if __name__ == "__main__":
    sys.exit(main())
