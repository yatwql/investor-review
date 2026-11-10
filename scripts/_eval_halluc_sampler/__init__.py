"""eval-llm-hallucination 实现包（入口脚本仅留 CLI 主流程）。

模块划分：
  - holdings.py    品种分类 / 组合核心数值 / 标准数据集加载
  - llm_call.py    HTTP 客户端工厂 / 模块映射 / prompt 构建（dry-run）与真实调用
  - fact_check.py  事实校验（独立检查器精准分类）
  - report.py      幻觉率评估报告生成
  - self_review.py 自检抽样（离线；产物双写模块名，人机共读）
  - from_report.py 既有报告重放（`--from-report`：零 LLM 的确定性核对 + 覆盖率）
"""

from __future__ import annotations

from _eval_halluc_sampler.fact_check import _run_fact_check  # noqa: F401
from _eval_halluc_sampler.from_report import (  # noqa: F401
    extract_holdings_details,
    extract_sections,
    run_from_report,
)
from _eval_halluc_sampler.holdings import (  # noqa: F401
    _compute_categories,
    _compute_portfolio_values,
    _load_datasets,
)
from _eval_halluc_sampler.llm_call import (  # noqa: F401
    _MODULE_FNS,
    _call_llm_module,
    _get_http_client,
)
from _eval_halluc_sampler.report import _generate_report  # noqa: F401
from _eval_halluc_sampler.self_review import (  # noqa: F401
    _build_self_review_dry_run_prompt,
    _generate_self_review_section,
    _run_self_review_sample,
)
