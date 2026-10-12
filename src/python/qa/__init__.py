"""报告对话式追问（report_qa）— 面向本期报告的会话式答疑子包。

设计定稿：``docs/plan/report-followup-qa-design.md``（立项评估交付的报告页对话式追问设计）。

架构边界（依赖方向单向，llm 不感知 qa）：

  - ``qa → llm``：LLM 调用仅经 ``llm/api.call_llm``（Provider Chain 路由 +
    合规声明漏斗自动生效），回答渲染经 ``llm/markdown.markdown_to_html``，
    质量核对经 ``llm/fact_checker.run_fact_check``；
  - **不进** LLM 模块注册（无模块级缓存、无指纹、不入 ``_MODULE_FNS``）——
    追问是「面向报告的服务」而非「LLM 报告模块」；
  - 零新增取数：上下文只读 output_dir 下的报告 HTML，不触数据源链路；
  - 用量独立记账于会话对象，不写报告周期的 LLM 用量统计。

出口：``ask_report_qa``（会话服务编排入口，Web 路由与 TUI 共用同一实现）。
"""

from src.python.qa.context import ReportQaContext, ReportQaContextError, extract_report_qa_context
from src.python.qa.session import (
    QaSession,
    ask_report_qa,
    create_report_qa_session,
    report_qa_session_count,
    reset_report_qa_sessions,
)

__all__ = [
    "QaSession",
    "ReportQaContext",
    "ReportQaContextError",
    "ask_report_qa",
    "create_report_qa_session",
    "extract_report_qa_context",
    "report_qa_session_count",
    "reset_report_qa_sessions",
]
