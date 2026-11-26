"""LLM API 调用模块 — Provider 路由、Extended Thinking、调用实现。

仅包含 Provider 路由 + Thinking 注入 + 5 个核心调用函数。
基础设施（常量/重试/截断/内容提取/失败追踪）位于 api_base.py。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

from src.python.llm.api_base import (
    _get_last_llm_failure,
    _get_retry_max,
    _is_default_thinking_on,  # noqa: F401 —— 再导出面：provider 子模块与测试按原名从门面取用
    _is_effort_model,  # noqa: F401 —— 再导出面：provider 子模块与测试按原名从门面取用
    _supports_extended_thinking,  # noqa: F401 —— 再导出面：provider 子模块与测试按原名从门面取用
    _DEFAULT_CLAUDE_MODEL,  # noqa: F401 —— 再导出面：provider 子模块与测试按原名从门面取用
    _DEFAULT_OPENAI_MODEL,  # noqa: F401 —— 再导出面：provider 子模块与测试按原名从门面取用
    _DEFAULT_GEMINI_MODEL,  # noqa: F401 —— 再导出面：provider 子模块与测试按原名从门面取用
    _resolve_thinking_budget,  # noqa: F401 —— 再导出面：provider 子模块与测试按原名从门面取用
    configure_extended_thinking,
)
from src.python.llm.compliance import apply_compliance_guardrails
from src.python.llm.prompts import (
    FAIL_REASON_API_ERROR,
    FAIL_REASON_CIRCUIT_OPEN,
    FAIL_REASON_NETWORK_ERROR,
    FAIL_REASON_TIMEOUT,
    LLM_MODULE_FAILURE,
)
from src.python.llm.strategy import resolve_provider_chain

logger = logging.getLogger("invest")

# ── 默认模型名（Provider 未指定时使用） ─────────────────

# ── 内容过滤安抚重试 ────────────────────────────────

_CONTENT_FILTER_RECOVERY = (
    "\n\n注意：请确保你的回答包含实质性的分析内容。"
    "如果前一版本未输出任何内容，请提供完整的分析结果。"
    "所有数据均基于公开市场信息，请客观分析即可。"
)
"""当 API 返回空内容（可能被内容过滤机制拦截）时，
追加到 system prompt 尾部重新请求。"""


def _calm_retry(
    system_prompt: str,
    user_prompt: str,
    name: str,
    do_retry: Callable[[str, str], tuple[str | None, dict | None]],
) -> tuple[str | None, dict | None]:
    """追加安抚指令后重试一次（空白内容兜底）。

    Args:
        system_prompt: 原始 system prompt
        user_prompt: 原始 user prompt
        name: provider 名称（日志用）
        do_retry: 重试可调用，签名 (sys, usr) -> (result, usage)

    Returns:
        (result, usage)，失败返回 (None, None)
    """
    logger.warning("%s API 返回空内容，追加安抚指令重试一次", name)
    calmed = system_prompt + _CONTENT_FILTER_RECOVERY
    result2, usage2 = do_retry(calmed, user_prompt)
    if result2 and result2.strip():
        logger.info("%s 安抚重试成功", name)
        return result2, usage2
    logger.warning("%s 安抚重试后仍返回空内容", name)
    return None, None


def _resolve_entry_credentials(
    entry: dict,
    llm_config: dict | None,
) -> tuple[str, str, str]:
    """从 provider entry 解析 api_key / model / endpoint。

    解析顺序：credentials_ref → llm_key.json 多键凭据；entry 级字段叠加覆盖。

    凭据来源边界（凭据分离，见 config/_llm_providers.py）：
        - `entry["api_key"]` 分支只服务**运行期内存条目**（调用方直接构造）。
          经 `_parse_providers_list()` 从 llm_providers.json 解析出的条目**永不带
          此键**——内联 api_key 在校验阶段即被拒（该条目会被整条跳过）。
        - llm_key.json 的凭据**不**流经本函数的 entry 分支：由 `credentials_ref`
          查 `_llm_credentials`（扁平密钥文档在读取阶段即规范为命名凭据块）。
        - `model` / `endpoint` 是非敏感路由字段，entry 级值优先于凭据块同名值。
    Returns:
        (api_key, model, endpoint)
    """
    api_key = entry.get("api_key", "")
    model = entry.get("model", "")
    endpoint = entry.get("endpoint") or ""

    creds_ref = entry.get("credentials_ref")
    if creds_ref and llm_config:
        all_creds = llm_config.get("_llm_credentials", {})
        ref_creds = all_creds.get(creds_ref, {})
        if isinstance(ref_creds, dict):
            if not api_key:
                api_key = ref_creds.get("api_key", "")
            if not model:
                model = ref_creds.get("model", "")
            if not endpoint:
                endpoint = ref_creds.get("endpoint", "") or ""

    return (api_key, model, endpoint)


def resolve_provider_endpoint(entry: dict, llm_config: dict | None = None) -> str:
    """解析 provider entry 的最终 endpoint（entry 级优先，否则取 credentials_ref 凭据块）。

    本函数是「链条目 → endpoint」解析的唯一公开入口，供报告层等外部模块复用，
    避免各处自行重写 credentials_ref → endpoint 的遍历规则而漂移。
    """
    return _resolve_entry_credentials(entry, llm_config)[2]


def _resolve_first_provider_model_endpoint(
    llm_config: dict | None,
    module_key: str,
) -> tuple[str | None, str]:
    """从多链配置的首个 chain entry 解析 model 和 endpoint。

    仅当存在 _provider_list 且 module_key 非空时生效。
    非多链模式（含 llm_config 缺失）返回 (None, "")。

    Returns:
        (model_name, endpoint) — model 为解析后的模型名（含 credentials_ref），
        endpoint 为解析后的 API 地址
    """
    llm_config = llm_config or {}
    provider_list = llm_config.get("_provider_list")
    if not provider_list or not module_key:
        return (None, "")
    strategy = llm_config.get("_strategy", "priority")
    preferred = llm_config.get("_preferred_providers", {})
    try:
        from src.python.llm.strategy import resolve_provider_chain

        chain = resolve_provider_chain(provider_list, strategy, module_key, preferred)
        entry = chain[0] if chain else None
        if entry:
            _, model, endpoint = _resolve_entry_credentials(entry, llm_config)
            return (model, endpoint or "")
    except Exception:  # noqa: BLE001 — [llm] _resolve_first_provider_model_endpoint 异常
        logger.debug("[llm] _resolve_first_provider_model_endpoint 异常", exc_info=True)
    return (None, "")


def _infer_module_key(config_field: str) -> str:
    """从 config_field 推导 module_key。

    "max_tokens_global_macro" → "global_macro"
    "max_tokens" → ""（用不到 inference 的模块）
    "max_tokens_expert_review" → "expert_review"
    """
    if not config_field or not config_field.startswith("max_tokens_"):
        return ""
    return config_field[len("max_tokens_") :]


def _call_provider_entry(
    entry: dict,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    timeout: float,
    max_retries: int,
    http_client: httpx.Client | None,
    config_field: str,
    temperature: float | None,
    llm_config: dict | None,
) -> tuple[str | None, dict | None]:
    """从 provider entry dict 提取参数，委托给 call_single_provider。

    内部处理空内容安抚重试（限制在当前 provider 内，不触发 chain 切换）。

    凭据解析优先级：
      credentials_ref → llm_key.json 中同名键 → entry 内联字段覆盖。
    """
    name = entry.get("name", "unknown")
    resolved_api_key, resolved_model, resolved_endpoint = _resolve_entry_credentials(entry, llm_config)
    provider_type = entry["provider"]
    entry_timeout = entry.get("timeout", timeout)

    def _do_call(sys: str, usr: str) -> tuple[str | None, dict | None]:
        return call_single_provider(
            provider=provider_type,
            system_prompt=sys,
            user_prompt=usr,
            api_key=resolved_api_key,
            resolved_model=resolved_model,
            endpoint=resolved_endpoint,
            max_tokens=max_tokens,
            timeout=entry_timeout,
            max_retries=max_retries,
            http_client=http_client,
            config_field=config_field,
            temperature=temperature,
            llm_config=llm_config,
            # 条目名 = 端点节流策略键（pacing）与 429 并发回显的唯一钥匙：
            # 不传则下游 PacingGate("") 空转，llm_providers.json 的 pacing 声明全部失效
            endpoint_key=name,
        )

    result, usage = _do_call(system_prompt, user_prompt)
    # 空内容 → 安抚重试（仅一次）
    if result is not None and result == "":
        result2, usage2 = _calm_retry(system_prompt, user_prompt, name, _do_call)
        if result2 is not None:
            return result2, usage2
        logger.warning("%s 安抚重试后仍返回空内容，切换下一 provider", name)
        return (None, None)
    return result, usage


def call_single_provider(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    resolved_model: str,
    endpoint: str,
    max_tokens: int,
    timeout: float,
    max_retries: int,
    http_client: httpx.Client | None,
    config_field: str,
    temperature: float | None,
    llm_config: dict | None,
    endpoint_key: str = "",
) -> tuple[str | None, dict | None]:
    """调用单个 LLM provider。

    ``http_client`` 缺省（None）时自建一次性兜底客户端，调用结束后关闭。
    分发层（``_llm_dispatch._execute``）为并行 worker 装配共享客户端，但
    **串行后置模块**（生成后自检、持仓变动复盘归因）不经该装配、以 None
    进入——若 None 直达 provider 层 ``assert client is not None``，
    AssertionError 会被 ``call_llm`` 的 per-provider ``except Exception``
    吞掉，表现为「provider 异常，切换下一 provider」整链秒败、模块内容
    静默丢失（本函数是多链与 legacy 两路的唯一汇聚点，兜底收口于此）。
    """
    if http_client is None and provider in ("claude", "openai", "gemini"):
        from src.python.core.http_client import make_http_client

        logger.debug("call_single_provider 未收到 http_client，自建一次性客户端（provider=%s）", provider)
        with make_http_client(timeout=timeout) as _client:
            return call_single_provider(
                provider,
                system_prompt,
                user_prompt,
                api_key,
                resolved_model,
                endpoint,
                max_tokens,
                timeout,
                max_retries,
                _client,
                config_field,
                temperature,
                llm_config,
                endpoint_key=endpoint_key,
            )

    if provider == "claude":
        return call_claude(
            system_prompt,
            user_prompt,
            api_key,
            resolved_model,
            endpoint,
            max_tokens,
            timeout,
            max_retries=max_retries,
            http_client=http_client,
            config_field=config_field,
            temperature=temperature,
            llm_config=llm_config,
            endpoint_key=endpoint_key,
        )
    elif provider == "openai":
        return call_openai(
            system_prompt,
            user_prompt,
            api_key,
            resolved_model,
            endpoint,
            max_tokens,
            timeout,
            max_retries=max_retries,
            http_client=http_client,
            config_field=config_field,
            temperature=temperature,
            endpoint_key=endpoint_key,
        )
    elif provider == "gemini":
        return call_gemini(
            system_prompt,
            user_prompt,
            api_key,
            resolved_model,
            endpoint,
            max_tokens,
            timeout,
            max_retries=max_retries,
            http_client=http_client,
            config_field=config_field,
            temperature=temperature,
            llm_config=llm_config,
            endpoint_key=endpoint_key,
        )
    else:
        logger.warning("不支持的 LLM provider: %s", provider)
        return (None, None)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    llm_config: dict,
    timeout: float = 60.0,
    http_client: httpx.Client | None = None,
    max_tokens: int | None = None,
    config_field: str = "max_tokens",
    temperature: float | None = None,
    model: str | None = None,  # noqa: ARG001 — call_llm 公开签名（provider 链按关键字传 provider 模型）
) -> tuple[str | None, dict | None, dict | None]:
    """调用 LLM API 生成文本（多 Provider 链式）。

    按 provider 链依次尝试，第一个成功即返回。
    全部失败返回 (None, None, None)。

    Args:
        同前，新增返回值第三元组 provider_info。

    Returns:
        (content, usage, provider_info)
        — provider_info dict: {"name": entry名, "model": 解析后的模型名, "endpoint": 解析后的 endpoint}
          全部失败时为 None
    """
    provider_list = llm_config.get("_provider_list")
    # 合规声明集中注入：单一漏斗覆盖全部 LLM 模块（幂等，见 llm.compliance）
    system_prompt = apply_compliance_guardrails(system_prompt, role=_infer_module_key(config_field))
    if not provider_list:
        # 无 provider 链即配置不可用：显式失败（不设单 Provider 直连回退——绕过链路由
        # 会绕开策略/熔断/端点节流，违背 Provider Chain 必经约束）
        logger.error("LLM 配置缺少 provider 链（llm_providers.json 未配置或读取失败）——本次调用不可用")
        return (None, None, None)

    # 多链模式
    strategy = llm_config.get("_strategy", "priority")
    preferred = llm_config.get("_preferred_providers", {})
    module_key = _infer_module_key(config_field)

    chain = resolve_provider_chain(provider_list, strategy, module_key, preferred)
    if not chain:
        logger.warning("resolve_provider_chain 返回空列表")
        return (None, None, None)

    max_retries = _get_retry_max(llm_config)
    resolved_max_tokens = max_tokens or 2500

    attempted: list[str] = []

    for entry in chain:
        name = entry.get("name", "unknown")
        entry_api_key, entry_model, entry_endpoint = _resolve_entry_credentials(entry, llm_config)
        provider_type = entry["provider"]
        _entry_desc = f"{name}({provider_type}/{entry_model})"
        if entry_endpoint:
            _entry_desc += f" [{entry_endpoint}]"
        logger.info("尝试 provider: %s", _entry_desc)
        try:
            result, usage = _call_provider_entry(
                entry,
                system_prompt,
                user_prompt,
                resolved_max_tokens,
                timeout,
                max_retries,
                http_client,
                config_field,
                temperature,
                llm_config,
            )
            if result is not None:
                logger.info("provider 成功: %s", _entry_desc)
                attempted.append(f"{name}: SUCCESS")
                from src.python.llm.observation import current_llm_observation

                _sink = current_llm_observation()
                if _sink is not None:
                    _sink.note_call(provider=name, model=entry_model or "")
                if module_key:
                    LLM_MODULE_FAILURE[module_key] = {
                        "attempted": attempted,
                        "final_status": "success",
                    }
                return (result, usage, {"name": name, "model": entry_model, "endpoint": entry_endpoint or ""})
            else:
                reason = _get_last_llm_failure() or FAIL_REASON_API_ERROR
                logger.warning("provider %s 失败（%s），切换下一 provider", _entry_desc, reason)
                attempted.append(f"{name}: {reason}")
                from src.python.llm.observation import current_llm_observation

                _sink = current_llm_observation()
                if _sink is not None:
                    _sink.note_fallback()
        except Exception:  # noqa: BLE001 — provider %s 异常，切换下一 provider
            logger.warning("provider %s 异常，切换下一 provider", _entry_desc, exc_info=True)
            attempted.append(f"{name}: EXCEPTION")

    # 全链不可用是错误级事件（不是可容忍的降级）：升 ERROR 以便与「数值缺失」类
    # WARNING 区分开——这类事件若只发 WARNING，事后只能翻日志才能发现整段内容缺失。
    logger.error(
        "全部 provider 尝试失败（已尝试：%s）——本轮 LLM 内容不可用，报告将降级/占位",
        "、".join(attempted) or "无可用 provider",
    )
    if module_key:
        # 从最后一次失败推论 final_status
        final_status = FAIL_REASON_API_ERROR
        if attempted:
            last_reason = attempted[-1].split(": ", 1)[-1]
            _known_reasons = {
                FAIL_REASON_TIMEOUT,
                FAIL_REASON_NETWORK_ERROR,
                FAIL_REASON_API_ERROR,
                FAIL_REASON_CIRCUIT_OPEN,
            }
            if last_reason in _known_reasons:
                final_status = last_reason
        LLM_MODULE_FAILURE[module_key] = {
            "attempted": attempted,
            "final_status": final_status,
        }
    return (None, None, None)


# ── Provider 调用实现（从子模块导入） ─────────────────
from src.python.llm._api_claude import call_claude  # noqa: E402 — Provider 实现须排在分派定义之后
from src.python.llm._api_openai import call_openai  # noqa: E402 — Provider 实现须排在分派定义之后
from src.python.llm._api_gemini import call_gemini  # noqa: E402 — Provider 实现须排在分派定义之后

__all__ = [
    "call_llm",
    "call_single_provider",
    "call_claude",
    "call_openai",
    "call_gemini",
    "configure_extended_thinking",
    "resolve_provider_endpoint",
]
