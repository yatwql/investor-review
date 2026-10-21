"""报告生成实现 — both/full 两种路径的 HTML+Excel 生成逻辑（聚合门面）。

包含报告生成管线各工序实现。本文件为聚合门面：
  - 后台健康检查          → `_report_health.py`
  - 轻量行情/数据注入/校验 → `_report_helpers.py`
  - 全量量化指标装配       → `_full_risk_metrics.py`
  - Chart.js 数据集构建    → `_chart_dataset_factory.py`
门面保留 both/full 双路径生成编排（`_generate_report_*`）并 re-export 子模块符号。
"""

from __future__ import annotations


from src.python.report._report_output import (  # noqa: F401  # 产物落盘子模块（消费方在本门面，patch 点不变）
    _generate_full_excel_report,
    _generate_full_html_report,
)

# ── 子模块 re-export ────────────────────────────────────
from src.python.report._chart_dataset_factory import _build_chart_datasets_for_report  # noqa: F401
from src.python.report._full_risk_metrics import _prepare_full_risk_metrics  # noqa: F401
from src.python.report._report_health import _collect_health_checks, _spawn_health_checks  # noqa: F401
from src.python.report._report_helpers import (  # noqa: F401
    _action_holdings_details,
    _compute_details,
    _inject_evolution_data,
    _inject_snapshot_diff_data,
    _validate_pipeline_snapshot,
    _validate_prep_completeness,
)

from ._generation_shared import (  # noqa: F401
    _record_llm_context,
)

from ._generation_both import (  # noqa: F401
    _generate_report_both,
)

from ._generation_full import (  # noqa: F401
    _generate_report_full,
)

logger = __import__("logging").getLogger("invest")
