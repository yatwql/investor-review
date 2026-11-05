"""LLM 模块失败原因常量（语义名 failure_reasons）— 门面 prompts_core / prompts 共享再导出。"""

from __future__ import annotations

# ── 模块级失败原因记录（供 write_llm_sheets 读取以输出具体提示） ──

FAIL_REASON_NOT_CONFIGURED = "not_configured"
FAIL_REASON_API_ERROR = "api_error"
FAIL_REASON_NETWORK_ERROR = "network_error"
FAIL_REASON_TIMEOUT = "timeout"
FAIL_REASON_CIRCUIT_OPEN = "circuit_open"
# 端点配额/风控类拒绝（如订阅制端点的 5 小时窗口、并发上限）——重试无益且会加剧风控画像
FAIL_REASON_QUOTA_EXCEEDED = "quota_exceeded"
FAIL_REASON_DISABLED = "disabled"

LLM_MODULE_FAILURE: dict[str, str | dict] = {}
"""{module_key: reason|dict} 各 LLM 模块最近一次生成的失败原因。"""

FAIL_REASON_LABELS: dict[str, str] = {
    FAIL_REASON_NOT_CONFIGURED: "LLM 未配置",
    FAIL_REASON_API_ERROR: "LLM API 调用失败",
    FAIL_REASON_NETWORK_ERROR: "LLM API 网络连接失败",
    FAIL_REASON_TIMEOUT: "LLM API 请求超时",
    FAIL_REASON_CIRCUIT_OPEN: "LLM API 暂时不可用（熔断冷却中）",
    FAIL_REASON_QUOTA_EXCEEDED: "LLM 端点配额/风控限制已触发（稍后重试或改用按量付费端点）",
}
"""失败原因 → 上屏文案（报告模块状态与日志共用此单一事实来源）。"""


def describe_failure_reason(reason: str | None) -> str:
    """失败原因码 → 可读文案（未知码原样返回，None → 空串）。"""
    if not reason:
        return ""
    return FAIL_REASON_LABELS.get(reason, str(reason))
