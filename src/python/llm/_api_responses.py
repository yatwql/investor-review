"""LLM 响应解析：截断检测、内容提取、token 用量记录与成功响应装配。

从 :mod:`llm.api_base` 拆出——请求发送与重试编排留在原模块（单向依赖：
请求 → 解析），门面 re-export 保持既有导入面。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable


from src.python.core.text_safety import sanitize_lone_surrogates
from src.python.llm.circuit_breaker import (
    _cb_record_failure,
)
from src.python.llm.pricing import estimate_cost
from src.python.llm.session import _normalize_usage_tokens, track_session_usage

logger = logging.getLogger("invest")


_thinking_exhausted_local = threading.local()


def _set_last_thinking_exhausted(value: bool) -> None:
    """设置当前线程的思考耗尽标志。"""
    _thinking_exhausted_local.last = value


_extract_ctx_local = threading.local()


def _set_extract_ctx(config_field: str, max_tokens: int) -> None:
    """记录当前线程本次调用的配置字段与上限（仅供诊断日志回显）。"""
    _extract_ctx_local.config_field = config_field or ""
    _extract_ctx_local.max_tokens = max_tokens or 0


def _get_extract_ctx() -> tuple[str, int]:
    """返回 (config_field, max_tokens)；未记录时为 ("", 0)。"""
    return (
        str(getattr(_extract_ctx_local, "config_field", "")),
        int(getattr(_extract_ctx_local, "max_tokens", 0) or 0),
    )


_server_error_local = threading.local()


def _set_last_server_error(value: bool) -> None:
    """设置当前线程的服务端错误信封标志。"""
    _server_error_local.last = value


TRUNCATION_MARKER = "【⚠ 输出已被截断"


def _truncation_warning(config_field: str) -> str:
    """生成截断警告，指明 llm_settings.json 中需要增大的具体配置项。"""
    return (
        f"\n\n{TRUNCATION_MARKER}！{config_field} 上限不足，内容不完整。"
        f"请在 data/config/llm_settings.json 中增大 {config_field} 后重新生成。】"
    )


def _check_claude_truncation(data: dict, max_tokens: int, label: str, config_field: str = "max_tokens") -> bool:
    """检查 Claude Messages API 响应是否被 max_tokens 截断。

    若 stop_reason 为 "max_tokens"，说明输出达到 token 上限被截断，
    记录 ERROR 日志。由调用方决定是否在内容后附加警告。
    """
    stop_reason = data.get("stop_reason")
    if stop_reason == "max_tokens":
        out_tokens = (data.get("usage") or {}).get("output_tokens", 0)
        logger.error(
            "LLM 输出被截断 [%s]: %s=%d, 实际输出=%d tokens。内容不完整，请在 llm_settings.json 中增大 %s",
            label,
            config_field,
            max_tokens,
            out_tokens,
            config_field,
        )
        return True
    return False


def _check_openai_truncation(data: dict, max_tokens: int, label: str, config_field: str = "max_tokens") -> bool:
    """检查 OpenAI Chat Completions 响应是否被 max_tokens 截断。

    finish_reason 为 "length" 表示达到 token 上限被截断。
    """
    try:
        finish_reason = data["choices"][0].get("finish_reason")
    except (KeyError, IndexError, TypeError):
        return False
    if finish_reason == "length":
        out_tokens = (data.get("usage") or {}).get("completion_tokens", 0)
        logger.error(
            "LLM 输出被截断 [%s]: %s=%d, 实际输出=%d tokens。内容不完整，请在 llm_settings.json 中增大 %s",
            label,
            config_field,
            max_tokens,
            out_tokens,
            config_field,
        )
        return True
    return False


def _check_gemini_truncation(data: dict, max_tokens: int, label: str, config_field: str = "max_tokens") -> bool:
    """检查 Gemini 响应是否被 max_tokens 截断。

    finishReason 为 "MAX_TOKENS" 表示达到 token 上限被截断。
    """
    try:
        candidates = data.get("candidates", [])
        if not candidates:
            return False
        finish_reason = candidates[0].get("finishReason", "")
        if finish_reason == "MAX_TOKENS":
            usage_meta = data.get("usageMetadata", {})
            out_tokens = usage_meta.get("candidatesTokenCount", 0)
            logger.error(
                "LLM 输出被截断 [%s]: %s=%d, 实际输出=%d tokens。内容不完整，请在 llm_settings.json 中增大 %s",
                label,
                config_field,
                max_tokens,
                out_tokens,
                config_field,
            )
            return True
    except (KeyError, IndexError, TypeError, AttributeError):
        return False
    return False


def _extract_content(data: dict) -> str | None:
    """从 Anthropic Messages API 兼容响应中提取文本内容。

    兼容标准 Claude 格式及 DeepSeek Anthropic 兼容端点等多种格式变体。
    会遍历 content 列表中所有 text block 并拼接返回。

    Returns:
        str: 提取的文本内容
        None: 响应格式异常或内容被过滤
    """
    _set_last_thinking_exhausted(False)  # 每次提取前复位（当前线程），仅 max_tokens 无正文分支置 True
    _set_last_server_error(False)
    # API 返回了错误信息
    if data and "error" in data:
        _set_last_server_error(True)
        logger.warning("LLM API 返回错误: %s", data["error"])
        return None

    try:
        content_field = data.get("content")
    except (AttributeError, TypeError):
        return None

    # content 为字符串（部分兼容实现）
    if isinstance(content_field, str):
        return content_field

    # content 为列表：提取所有 text block 并拼接
    if isinstance(content_field, list):
        texts = []
        for block in content_field:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
                elif block.get("type") == "text" and block.get("text"):
                    texts.append(str(block["text"]))
        if texts:
            return "\n".join(texts)
        # content 无任何 text block（如只有 thinking / redacted_thinking，或空列表）。
        # 区分根因，避免误报"内容被过滤"：
        #   1) stop_reason=max_tokens → 思考部分耗尽 max_tokens 预算（DeepSeek V4 等强制
        #      推理模型常见），未产出最终文本。安抚重试（改 system prompt）对该场景无效，
        #      返回 None 触发 provider 切换而非无效重试。
        #   2) 其他 → 内容可能被过滤拦截，同样视为无可用文本，返回 None。
        if data.get("stop_reason") == "max_tokens":
            _set_last_thinking_exhausted(True)
            _field, _budget = _get_extract_ctx()
            if _field and _budget:
                logger.warning(
                    "LLM 输出思考部分耗尽 max_tokens 预算，未生成最终文本"
                    "（当前 %s=%d；建议增大 llm_settings.json 中的 %s，或降低 reasoning_effort/thinking_budget）",
                    _field,
                    _budget,
                    _field,
                )
            else:
                logger.warning(
                    "LLM 输出思考部分耗尽 max_tokens 预算，未生成最终文本"
                    "（建议增大 llm_settings.json 中对应 max_tokens 配置，或降低 reasoning_effort/thinking_budget）"
                )
        else:
            # 记录响应结构供诊断：空 content 不必然等于"内容被过滤"——DeepSeek 强制推理
            # 模型在并发/异常下可能返回 HTTP 200 但 content 为空（区别于思考耗尽的
            # stop_reason=max_tokens）。带 stop_reason / block 类型 / usage 打日志，
            # 下次可直接定位根因，不再武断归因。
            _block_types = [b.get("type") for b in content_field if isinstance(b, dict)]
            logger.warning(
                "LLM API 返回空 content（stop_reason=%r，block types=%s，usage=%r）",
                data.get("stop_reason"),
                _block_types,
                data.get("usage"),
            )
        return None

    return None


def _extract_content_from_gemini(data: dict) -> str | None:
    """从 Gemini generateContent 响应中提取文本内容。

    Gemini 响应格式：
    {
      "candidates": [{
        "content": {"parts": [{"text": "..."}], "role": "model"},
        "finishReason": "STOP"
      }],
      "usageMetadata": {...}
    }

    Returns:
        str: 提取的文本内容
        None: 响应格式异常
    """
    if data and "error" in data:
        logger.warning("Gemini API 返回错误: %s", data["error"])
        return None

    try:
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
        if texts:
            return "\n".join(texts)
        return "" if candidates else None
    except (KeyError, IndexError, TypeError, AttributeError) as e:
        logger.warning("Gemini API 响应格式异常: %s", e)
        return None


def _log_token_usage(provider: str, usage: dict | None, label: str, model_name: str = "") -> None:
    """记录 LLM API 调用的 token 使用量，可选估算费用。

    Args:
        provider: "claude" 或 "openai"
        usage: API 响应中的 usage 字典
        label: 调用标签（如 "全球政经局势"）
        model_name: 模型名称（用于费用估算，可空）
    """
    if not usage:
        return
    inp, out, cache_hit = _normalize_usage_tokens(provider, usage)
    total = inp + out
    msg = f"  [LLM] {label}: 输入 {inp:,} + 输出 {out:,} = {total:,} tokens"
    if model_name:
        msg += f" | 模型: {model_name}"
    if cache_hit:
        msg += f" (缓存命中 {cache_hit:,})"
    if model_name:
        _cost = estimate_cost(model_name, inp, out, cache_hit_input_tokens=cache_hit)
        if _cost != "-":
            msg += f" | 估算费用: {_cost}"
    logger.info("%s", msg)


def _process_success_response(
    data: dict,
    extract_fn: Callable[[dict], str | None],
    check_truncation_fn: Callable[[dict, int], bool],
    max_tokens: int,
    config_field: str,
    provider: str,
    model_name: str,
    label: str,
    url: str,
) -> tuple[str | None, dict | None]:
    """处理成功响应：内容提取、截断检测、Token 日志。"""
    _set_extract_ctx(config_field, max_tokens)  # 供 _extract_content 诊断日志回显当前配置值
    content = extract_fn(data)
    if content is None:
        logger.warning("%s API 响应格式异常", label)
        _cb_record_failure(url)
        return (None, None)
    content = sanitize_lone_surrogates(content)  # 响应中的 \udXXX 孤立代理项不可编码
    if not content.strip():
        logger.warning("%s API 返回空内容（可能被内容过滤机制拦截）", label)
        return ("", data.get("usage"))

    truncated = check_truncation_fn(data, max_tokens)
    # 兼容 Gemini usageMetadata：若 usage 字段不存在但 usageMetadata 存在则转换
    usage = data.get("usage")
    if usage is None:
        usage_meta = data.get("usageMetadata")
        if usage_meta:
            usage = {
                "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
            }
    _log_token_usage(provider, usage, label, model_name=model_name)
    track_session_usage(provider, usage, model_name=model_name)

    content = content.strip()
    if truncated:
        content += _truncation_warning(config_field)

    return (content, usage)
