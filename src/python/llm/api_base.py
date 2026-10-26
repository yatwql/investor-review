"""LLM API 基础模块 — 共享的常量、检测函数、失败追踪与重试骨架。

基础设施层（被 api.py / skeleton.py / generators 系列共用）。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import httpx

from src.python.core.http_client import post_with_deadline
from src.python.core.retry import STRATEGY_TABLE, RetryPolicy, retry_transient
from src.python.core.text_safety import sanitize_llm_payload

from src.python.llm.circuit_breaker import (
    _cb_endpoint,
    _cb_is_open,
    _cb_record_failure,
    _cb_record_success,
)
from src.python.llm.pacing import _concurrency_hint
from src.python.llm.prompts import (
    FAIL_REASON_API_ERROR,
    FAIL_REASON_CIRCUIT_OPEN,
    FAIL_REASON_NETWORK_ERROR,
    FAIL_REASON_QUOTA_EXCEEDED,
    FAIL_REASON_TIMEOUT,
)
from src.python.llm.session import record_per_module

from ._api_responses import (
    TRUNCATION_MARKER,
    _check_claude_truncation,
    _check_gemini_truncation,
    _check_openai_truncation,
    _extract_content,
    _extract_content_from_gemini,
    _log_token_usage,
    _process_success_response,
    _server_error_local,
    _set_last_server_error,
    _thinking_exhausted_local,
    _truncation_warning,
)

from src.python.config import get_llm_setting_default

logger = logging.getLogger("invest")

__all__ = [
    "_last_llm_failure_reason",
    "clear_last_llm_failure",
    "_get_last_llm_failure",
    "_get_last_thinking_exhausted",
    "clear_last_thinking_exhausted",
    "_get_last_server_error",
    "clear_last_server_error",
    "LLM_TIMEOUT",
    "_RETRY_DELAYS",
    "TRUNCATION_MARKER",
    "AUTO_INCREASE_FACTOR",
    "CACHE_LINE_HTML",
    "_cache_line_model_tpl",
    "_MODEL_LINE_RE",
    "_THINKING_SUPPORTED_PREFIXES",
    "_THINKING_EFFORT_MODEL_PREFIXES",
    "_THINKING_DEFAULT_ON_PREFIXES",
    "_supports_extended_thinking",
    "_is_effort_model",
    "_is_default_thinking_on",
    "_truncation_warning",
    "_check_claude_truncation",
    "_check_openai_truncation",
    "_check_gemini_truncation",
    "_extract_content",
    "_extract_content_from_gemini",
    "_extract_model_from_cached",
    "_log_token_usage",
    "_get_retry_max",
    "_sanitize_endpoint",
    "_check_circuit_breaker",
    "_process_success_response",
    "_attempt_api_call",
    "_retry_policy",
    "_retry_detail",
    "call_llm_with_retry",
]

# ── 上次失败的详细原因（供调用方区分失败类型，不改变函数签名） ──


_RATE_LIMIT_RECOVERY = 600  # 429 首试熔断的端点冷却（秒）：限速属配额/风控终态，
# 常规 60s 冷却会在下一批调用时再次撞限速并重复整段重试，长冷却消除无效先试

_last_llm_failure_reason: str | None = None
"""最近一次 LLM API 调用失败的详细原因（FAIL_REASON_* 常量），成功调用后为 None。"""

# 思考耗尽标志使用线程局部存储：LLM 生成在 ThreadPoolExecutor(llm_max_concurrency=3)
# 下并发执行（generators_orchestrator），若用模块级全局会被其他线程 _extract_content 的
# 无条件复位踩踏，导致 call_claude"关闭 thinking 重试"安全网静默失效。
"""线程局部的思考耗尽标志。

仅由 _extract_content 设置：`stop_reason == "max_tokens"` 且无任何 text block 时为 True，
其余路径复位为 False。供 call_claude 判断是否可用"关闭 thinking 重试"安全网兜底。
"""


# 提取上下文（config_field / max_tokens）同走线程局部：诊断日志在 _extract_content 内
# 发出，而配置值只在调用链上层可见——由 _process_success_response 置入后，
# 「思考耗尽」提示能回显当前配置值，读者不必翻 llm_settings.json 就知道要从多少调到多少。


def clear_last_llm_failure() -> None:
    """清除上次失败原因记录。"""
    global _last_llm_failure_reason
    _last_llm_failure_reason = None


def _get_last_thinking_exhausted() -> bool:
    """返回当前线程最近一次响应提取是否因思考耗尽而空内容。"""
    return getattr(_thinking_exhausted_local, "last", False)


def clear_last_thinking_exhausted() -> None:
    """清除当前线程的思考耗尽标志（重试前复位）。"""
    try:
        del _thinking_exhausted_local.last
    except AttributeError:
        pass


# ── 服务端错误信封标志（线程局部） ──
# 200 响应体携带 error 字段（如 DeepSeek 兼容端点「无法在服务端超时上限内开始处理」）
# 在提取层与「200 但 content 为空」不可区分（都表现为 _extract_content 返回 None），
# 只有 _extract_content 看得到真实 JSON。此标志供上层安全网区分服务侧故障与
# 真·空响应：对已故障的端点关 thinking 重试只会重复失败，最坏再挂一个超时周期。


def _get_last_server_error() -> bool:
    """返回当前线程最近一次响应提取是否因响应体携带 error 信封而失败。"""
    return bool(getattr(_server_error_local, "last", False))


def clear_last_server_error() -> None:
    """清除当前线程的服务端错误信封标志（测试隔离复位用）。"""
    _set_last_server_error(False)


def _get_last_llm_failure() -> str | None:
    """返回最近一次 LLM API 调用的失败原因，无失败时返回 None。"""
    return _last_llm_failure_reason


# ── 默认超时 ─────────────────────────────────────────────────

LLM_TIMEOUT = 120.0

# ── 重试配置 ─────────────────────────────────────────────────

_RETRY_DELAYS = [1.0, 3.0, 5.0, 10.0, 15.0]  # 递增退避表：第 1~5 次依次等待（手工调优，非等比）
_RETRY_POLICY = RetryPolicy(strategy=STRATEGY_TABLE, delays=tuple(_RETRY_DELAYS))
"""LLM 重试策略模板：显式退避序列（超出末位锁定末位）；尝试次数由配置补齐。"""


def _retry_policy(max_retries: int) -> RetryPolicy:
    """按 ``max_retries`` 生成重试策略（总尝试次数 = max_retries + 1，下限 1）。"""
    return replace(_RETRY_POLICY, attempts=max(1, max_retries + 1))


def _retry_detail(info: Any) -> str:
    """把「可重试」结果的状态码/描述转成日志可读文本。"""
    if info is None:
        return "超时"
    if isinstance(info, int):
        return f"{info}"
    return f"网络错误 ({info})"


# ── 输出截断自适应重试 ────────────────────────────────

"""截断警告中的唯一标记，用于检测输出是否被 max_tokens 截断。"""

AUTO_INCREASE_FACTOR = 1.5
"""截断时自动增大的倍数。"""

# _CONTENT_FILTER_RECOVERY（留在 api.py，仅 _call_llm 使用 — 见复盘修正记录）


# ── 缓存行定义 ────────────────────────────────────

CACHE_LINE_HTML = '<p style="color:#888;font-size:12px">本次使用LLM缓存，未直接使用LLM服务能力</p>'
"""缓存命中的 HTML 提示行。"""


def _cache_line_model_tpl(model: str) -> str:
    """生成缓存命中提示行（含模型名）。"""
    return f'<p style="color:#888;font-size:12px">本次使用LLM缓存（原始模型：{model}）</p>'


def _build_cache_hint_and_record(
    cached: str,
    module_key: str,
    llm_config: dict,
    thinking_enabled: bool,
    endpoint: str = "",
    model_hint: str | None = None,
) -> str:
    """构建缓存 HTML 提示行并记录模块用量。

    统一 _handle_cache_hit 与 _precheck_one_cache 中的重复逻辑。

    Args:
        cached: 缓存的原始 HTML 内容
        module_key: 模块键名
        llm_config: LLM 配置
        thinking_enabled: 是否启用 Extended Thinking
        endpoint: API 端点（可为空字符串）
        model_hint: 模型名称提示（用于当缓存中无法提取模型名时回退）

    Returns:
        附加了缓存提示的 HTML 内容
    """
    orig_model = _extract_model_from_cached(cached)
    hint = _cache_line_model_tpl(orig_model) if orig_model else CACHE_LINE_HTML
    if thinking_enabled:
        hint = hint.rstrip().replace("</p>", " | Extended Thinking</p>", 1)
    if module_key:
        chain_model, chain_endpoint = _chain_route_hint(llm_config)
        model_for_record = orig_model or model_hint or chain_model or "缓存命中"
        endpoint_for_record = endpoint or chain_endpoint or ""
        record_per_module(
            module_key, model_for_record, cached=True, thinking=thinking_enabled, endpoint=endpoint_for_record
        )
    return cached + hint


# 含原始模型名称的缓存提示行模板。

_MODEL_LINE_RE = re.compile(r"模型[：:]\s*([^|<\s][^|]*)")
"""从 token 行中提取模型名称的正则。"""


# ── Extended Thinking 模型兼容性名单 ──

_THINKING_SUPPORTED_PREFIXES = (
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-fable-5",
    "deepseek-flash",
    "deepseek-v4-",
    "gemini-3.5-",
    "gemini-2.5-",
    "kimi-",
    # Kimi Code 订阅端点的旗舰模型以 `k3` 命名（不属 `kimi-` 前缀）：漏登记会让
    # 「未开启 thinking 时显式禁用」的安全网失效，请求落入默认思考模式。
    "k3",
)

# 使用 output_config.effort（而非 thinking.budget_tokens）控制思考深度的模型。
# deepseek-flash 是 DeepSeek 新一代 Flash 的正式模型名，与它接管的 deepseek-v4-flash
# 同属强制推理族——漏登记会让「未开启 thinking 时显式禁用」的安全网失效，请求落入
# 默认思考模式占满 max_tokens 而无正文。
_THINKING_EFFORT_MODEL_PREFIXES = ("deepseek-flash", "deepseek-v4-")

# 默认开启思考模式的模型（不传任何思考参数即自动思考）。
# 这是独立于「控制方式」（budget_tokens / effort）的第二个维度：未显式开启 thinking
# 时必须显式发送 thinking.disabled，否则思考 token 会占满 max_tokens 导致无正文。
# DeepSeek 推理族（effort 控制）与 Kimi（budget_tokens 控制）均为默认开思考；
# Anthropic 原生模型默认不思考，不在此列。
# Kimi Anthropic 兼容端点行为：默认返回 thinking 块；thinking.enabled+budget_tokens
# 与 thinking.disabled 均接受。
_THINKING_DEFAULT_ON_PREFIXES = ("deepseek-flash", "deepseek-v4-", "kimi-", "k3")


def _supports_extended_thinking(model: str) -> bool:
    """检查模型是否支持 Extended Thinking。"""
    return any(model.lower().startswith(p) for p in _THINKING_SUPPORTED_PREFIXES)


def _is_effort_model(model: str) -> bool:
    """检查模型是否使用 effort（而非 budget_tokens）控制思考深度。"""
    return any(model.lower().startswith(p) for p in _THINKING_EFFORT_MODEL_PREFIXES)


def _is_default_thinking_on(model: str) -> bool:
    """检查模型是否默认开启思考（未显式禁用时思考 token 会占用 max_tokens）。"""
    return any(model.lower().startswith(p) for p in _THINKING_DEFAULT_ON_PREFIXES)


def _chain_route_hint(llm_config: dict | None) -> tuple[str, str]:
    """缓存命中路径的模型/端点提示：取 provider 链首条目的解析结果。

    缓存命中不经过 provider 解析，记录里的模型名仍要能指向真实线路
    （否则「模块用量」只能显示「缓存命中」，无法对账）。
    """
    chain = (llm_config or {}).get("_provider_list") or []
    creds = (llm_config or {}).get("_llm_credentials") or {}
    for entry in chain:
        if not isinstance(entry, dict):
            continue
        block = creds.get(entry.get("credentials_ref"), {}) if entry.get("credentials_ref") else {}
        model = entry.get("model") or (block or {}).get("model") or ""
        endpoint = entry.get("endpoint") or (block or {}).get("endpoint") or ""
        if model or endpoint:
            return str(model or ""), str(endpoint or "")
    return "", ""


def _extract_model_from_cached(html: str) -> str:
    """从缓存的 HTML 中提取原始模型名称。"""
    m = _MODEL_LINE_RE.search(html)
    return m.group(1).strip() if m else ""


def _get_retry_max(llm_config: dict) -> int:
    """从 llm_config 中读取最大重试次数，兜底返回 2。"""
    try:
        val = int(llm_config.get("max_retries", get_llm_setting_default("max_retries")))
        return max(0, val)
    except (TypeError, ValueError):
        return 2


def _sanitize_endpoint(endpoint: str) -> str:
    """从 endpoint URL 中提取纯域名，避免路径/参数泄露到日志。"""
    try:
        return endpoint.split("/")[2] if endpoint else "unknown"
    except (IndexError, TypeError, AttributeError):
        return "unknown"


def _check_circuit_breaker(url: str, label: str) -> bool:
    """检查熔断器状态，若已熔断则记录日志并返回 True。"""
    if _cb_is_open(url):
        logger.warning("%s API 熔断中 (%s)，跳过本次请求", label, _cb_endpoint(url))
        return True
    return False


def _attempt_api_call(
    client: httpx.Client,
    url: str,
    headers: dict,
    payload: dict,
    timeout: float,
    endpoint_key: str = "",
) -> tuple[str, Any]:
    """执行一次 LLM API 调用，返回 (kind, info)。

    Args:
        endpoint_key: provider 条目名，仅用于 429 时回显该端点的并发配置（见
            :func:`pacing._concurrency_hint`）；不影响调用行为。

    Returns:
        ("success", data) — 调用成功，data 为解析后的 JSON
        ("retryable", detail) — 可重试（503 / 传输失败；detail 为 int 状态码或 str 描述）
        ("quota", detail) — 配额/限速/风控拒绝（403/429，不重试）
        ("fatal", error_msg) — 不可恢复（响应解析失败）
    """
    try:
        resp = post_with_deadline(client, url, headers, payload, timeout)
        if resp.status_code in (429, 503):
            if resp.status_code == 429:
                logger.warning(
                    "%s API 返回 429 Too Many Requests（API 限速），%s",
                    _sanitize_endpoint(url),
                    _concurrency_hint(endpoint_key),
                )
                # 限速属配额/风控终态：首试即终止（不进退避重试——重试都是
                # 无效请求与日志噪音），交由下游长冷却熔断
                return ("quota", resp.status_code)
            return ("retryable", resp.status_code)
        if resp.status_code == 403:
            # 端点配额/风控拒绝（订阅制端点的 5 小时窗口、并发上限、月度额度等）：
            # 重试无益（窗口按时间滚动，非瞬时故障），且高频重试会加剧风控画像，
            # 故标记为不可重试，交由上层链降级到下一 provider。
            logger.warning(
                "%s API 返回 403（端点配额/风控拒绝，重试无益）：%s",
                _sanitize_endpoint(url),
                (resp.text or "")[:160],
            )
            return ("quota", resp.status_code)
        resp.raise_for_status()
        return ("success", resp.json())
    except httpx.TimeoutException:
        logger.debug("[llm/api] 请求超时: %s", _sanitize_endpoint(url))
        return ("retryable", None)
    except httpx.HTTPError:
        host = _sanitize_endpoint(url)
        logger.debug("[llm/api] HTTP 异常: %s", host)
        return ("retryable", host)
    except (ValueError, KeyError) as e:
        logger.warning("[llm/api] 响应解析失败: %s", e)
        return ("fatal", str(e))


def call_llm_with_retry(
    label: str,
    client: httpx.Client,
    url: str,
    headers: dict,
    payload: dict,
    timeout: float,
    max_retries: int,
    max_tokens: int,
    config_field: str,
    extract_fn: Callable[[dict], str | None],
    check_truncation_fn: Callable[[dict, int], bool],
    provider: str,
    model_name: str = "",
    endpoint_key: str = "",
) -> tuple[str | None, dict | None]:
    """LLM API 调用通用重试骨架。

    重试/退避/超时/错误处理**全部委托** :mod:`core.retry`（策略：显式退避序列，
    见 :data:`_RETRY_POLICY`），本函数只负责 LLM 特有的部分：每次尝试前的端点
    节流门、失败分类的终态处理（断路器/失败原因码/响应提取）。

    Args:
        label: 显示名称（"Claude" / "OpenAI"），用于日志
        client: httpx 客户端实例
        url: API 端点 URL
        headers: HTTP 请求头
        payload: JSON 请求体
        timeout: 请求超时秒数
        max_retries: 最大重试次数
        max_tokens: 最大输出 token 数（用于截断日志）
        config_field: llm_settings.json 中的配置字段名（截断时提示用户）
        extract_fn: 从响应 dict 中提取文本内容的回调
        check_truncation_fn: 检查是否被截断的回调
        provider: 日志中的 provider 标识（"claude" / "openai"）
        model_name: 模型名称（用于费用估算，可空）
        endpoint_key: 端点策略键（provider 条目名）；非空且该端点声明了 ``pacing``
            时，每次请求前经 :class:`llm.pacing.PacingGate` 施加间隔与在途并发约束。
            空串 = 无约束（与未引入端点节流时逐字节一致）。

    Returns:
        (content, usage) — content 为文本，usage 为 API 用量字典，失败时均为 None
    """
    global _last_llm_failure_reason
    # 请求体净化：用户输入（stdin surrogateescape）与外部文本可能带无法编码的孤立
    # 代理项，httpx 序列化时会抛 UnicodeEncodeError 并被误判为响应解析失败。
    payload = sanitize_llm_payload(payload)
    if _check_circuit_breaker(url, label):
        _last_llm_failure_reason = FAIL_REASON_CIRCUIT_OPEN
        return (None, None)

    from src.python.llm.pacing import PacingGate

    policy = _retry_policy(max_retries)
    last: dict[str, tuple[str, Any]] = {}

    def _attempt() -> tuple[str, Any]:
        # 端点级节流：仅在配置声明了 pacing 时生效（无声明 → 零开销直通）
        with PacingGate(endpoint_key):
            result = _attempt_api_call(client, url, headers, payload, timeout, endpoint_key)
        last["result"] = result
        return result

    def _on_retry(failed_attempt: int, delay: float, _exc: BaseException | None) -> None:
        from src.python.llm.observation import current_llm_observation

        _sink = current_llm_observation()
        if _sink is not None:
            _sink.note_retry(delay)
        logger.warning(
            "%s API %s (尝试 %d/%d)，%.1fs 后重试...",
            label,
            _retry_detail(last["result"][1]),
            failed_attempt,
            policy.attempts,
            delay,
        )

    kind, info = retry_transient(
        _attempt,
        policy=policy,
        retry_on=lambda _exc: False,  # 异常已由 _attempt_api_call 归一为结果，不重复按异常重试
        retry_if_result=lambda result: result[0] == "retryable",
        on_retry=_on_retry,
    )

    if kind == "success":
        clear_last_llm_failure()
        _cb_record_success(url)
        return _process_success_response(
            info,
            extract_fn,
            check_truncation_fn,
            max_tokens,
            config_field,
            provider,
            model_name,
            label,
            url,
        )

    if kind == "quota":
        # 配额/限速/风控拒绝：均不重试（窗口按时间滚动，重试无益），降级到下一 provider
        if info == 429:
            # 限速终态：首试即 force 长冷却熔断，后续调用在冷却期内零请求秒切下家
            logger.warning("%s API 429 限速终态：首试即熔断 %ss，跳过退避重试", label, _RATE_LIMIT_RECOVERY)
            _cb_record_failure(url, cooldown=_RATE_LIMIT_RECOVERY, force=True)
        else:
            _cb_record_failure(url)
        _last_llm_failure_reason = FAIL_REASON_QUOTA_EXCEEDED
        return (None, None)

    if kind == "retryable":
        logger.warning("%s API %s（已重试 %d 次）", label, _retry_detail(info), max_retries)
        _cb_record_failure(url)
        _last_llm_failure_reason = FAIL_REASON_TIMEOUT if info is None else FAIL_REASON_NETWORK_ERROR
        return (None, None)

    # kind == "fatal"
    logger.warning("%s API 响应解析失败: %s", label, info)
    _cb_record_failure(url)
    _last_llm_failure_reason = FAIL_REASON_API_ERROR
    return (None, None)
