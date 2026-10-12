"""报告对话式追问错误码——单一来源（会话/上下文层产出，Web/TUI 同源引用）。

错误码是跨层契约：``qa/context.py`` 与 ``qa/session.py`` 产出、
``web/handlers.py`` 映射 HTTP 状态码、``tui/handlers_qa.py`` 决定退出
追问循环；三处消费方一律 import 本模块常量，不写字面量副本，
避免新增/改名错误码时下游映射静默失配。
"""

from __future__ import annotations

# ── 输入校验（HTTP 400 / TUI 交互提示）──
QA_BAD_QUESTION = "QA_BAD_QUESTION"
QA_QUESTION_TOO_LONG = "QA_QUESTION_TOO_LONG"
QA_BAD_REPORT = "QA_BAD_REPORT"

# ── 报告/上下文不可用（HTTP 404）──
QA_REPORT_NOT_FOUND = "QA_REPORT_NOT_FOUND"
QA_CONTEXT_INVALID = "QA_CONTEXT_INVALID"

# ── 会话生命周期（TUI 交互提示）──
QA_SESSION_LIMIT = "QA_SESSION_LIMIT"
QA_INPUT_CAP_EXCEEDED = "QA_INPUT_CAP_EXCEEDED"

# ── LLM 依赖不可用（HTTP 503）──
QA_LLM_UNAVAILABLE = "QA_LLM_UNAVAILABLE"
QA_LLM_FAILED = "QA_LLM_FAILED"

# ── 门控未启用（HTTP 503，Web/TUI 各自处理入口可见性）──
QA_DISABLED = "QA_DISABLED"
