"""LLM 失败自动降级模板 — 全失败时提供占位文本。

当所有 LLM 模块均生成失败时，full 报告路径自动降级为使用占位文本，
避免报告页签完全空白。

设计原则：
  - 降级是静默的：用户看到的是"数据暂不可用"而非错误堆栈
  - 降级是完整的：所有 LLM 页签都获得同质的占位内容
  - 降级是可配置的：通过 features.llm_* 开关可独立关闭各模块
  - 降级是诚实的：禁用（enabled_llm = false）≠ 生成失败——禁用槽位保持
    None 由章级可见性整章隐藏，占位文本只注入「启用但真实失败」的模块
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.python.llm.failure_reasons import FAIL_REASON_DISABLED, LLM_MODULE_FAILURE

logger = logging.getLogger("invest")

# ── 占位文本模板 ───────────────────────────────────────────

_PLACEHOLDER_TEXT: dict[str, str] = {
    "global_macro": (
        "<h3>🌍 全球政经局势</h3>"
        "<p>⚠️ 当前无法获取全球政经局势分析。</p>"
        "<p>可能原因：LLM API 服务暂时不可用、网络连接异常或 API Key 配置错误。</p>"
        "<p>建议稍后重试，或检查 <code>data/config/llm_settings.json</code> 中 API 配置是否正确。</p>"
        "<hr/><p><em>数据获取时间：{timestamp}</em></p>"
    ),
    "expert_review": (
        "<h3>🧠 智囊团深度复盘</h3>"
        "<p>⚠️ 当前无法生成智囊团深度复盘内容。</p>"
        "<p>可能原因：LLM API 服务暂时不可用、网络连接异常或 API Key 配置错误。</p>"
        "<p>建议稍后重试，或检查 <code>data/config/llm_settings.json</code> 中 API 配置是否正确。</p>"
        "<hr/><p><em>数据获取时间：{timestamp}</em></p>"
    ),
    "health_check": (
        "<h3>🏥 持仓体检报告</h3>"
        "<p>⚠️ 当前无法生成持仓体检报告。</p>"
        "<p>可能原因：LLM API 服务暂时不可用、网络连接异常或 API Key 配置错误。</p>"
        "<p>建议稍后重试，或检查 <code>data/config/llm_settings.json</code> 中 API 配置是否正确。</p>"
        "<hr/><p><em>数据获取时间：{timestamp}</em></p>"
    ),
    "penetration_deep": (
        "<h3>🔍 穿透深度分析</h3>"
        "<p>⚠️ 当前无法生成穿透深度分析。</p>"
        "<p>可能原因：LLM API 服务暂时不可用、网络连接异常或 API Key 配置错误。</p>"
        "<p>建议稍后重试，或检查 <code>data/config/llm_settings.json</code> 中 API 配置是否正确。</p>"
        "<hr/><p><em>数据获取时间：{timestamp}</em></p>"
    ),
}

_MODULE_KEYS = ("global_macro", "expert_review", "health_check", "penetration_deep")

# 占位文本的稳定签名 —— 上面全部模板均含该片段。内容侧识别降级占位
# （如 LLM 输出质量分级）依赖此常量，模板改动时签名须同步。
_PLACEHOLDER_SIGNATURE = "⚠️ 当前无法"

__all__ = [
    "build_fallback_llm_content",
    "is_all_llm_failed",
    "is_placeholder_content",
    "get_placeholder_text",
]


def is_placeholder_content(html: str) -> bool:
    """判断给定 HTML 是否为 LLM 失败后的自动降级占位文本。

    仅识别 :data:`_PLACEHOLDER_TEXT` 中的模块占位模板；``get_placeholder_text``
    的通用兜底分支（含动态模块键）只会在未知模块键时触发，4 个正式模块不会
    走到，故不纳入签名。

    Args:
        html: 待判定的 LLM 输出 HTML

    Returns:
        True = 命中降级占位模板；空输入返回 False（空内容由调用方另行判定）
    """
    if not html:
        return False
    return _PLACEHOLDER_SIGNATURE in html


def get_placeholder_text(module_key: str, timestamp: str | None = None) -> str:
    """获取指定模块的占位文本。

    Args:
        module_key: 模块键名（global_macro / expert_review 等）
        timestamp: 可选时间戳，不传则自动生成

    Returns:
        占位 HTML 文本
    """
    ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M")
    template = _PLACEHOLDER_TEXT.get(module_key, "")
    if not template:
        return f"<p>⚠️ {module_key} 内容暂不可用（数据获取时间：{ts}）</p>"
    return template.format(timestamp=ts)


def is_all_llm_failed(llm_content: tuple) -> bool:
    """判断所有 LLM 模块是否全部失败。

    Args:
        llm_content: (global_macro_html, expert_review_html, health_check_html, penetration_deep_html)
                     其中每个元素为 str 或 None

    Returns:
        True = 全部为 None（全部失败）
    """
    if not llm_content or len(llm_content) < 4:
        return True
    return all(c is None for c in llm_content[:4])


def _disabled_module_keys() -> set[str]:
    """当前被 ``enabled_llm`` 显式禁用的模块键集合（运行时失败登记簿推导）。

    禁用是用户的配置选择，不是生成故障。占位文本写明「LLM API 服务暂时
    不可用、API Key 配置错误」，注入禁用槽位会把配置选择误报成 API 故障。
    禁用槽位保持 ``None``，由模板章级可见性（``section_visible`` ←
    ``get_llm_chapter_disabled()``）整章隐藏，Excel 端同口径不建页签。

    Returns:
        禁用模块键集合（登记簿中无记录时为空集，即全部按启用处理）
    """
    return {key for key in _MODULE_KEYS if LLM_MODULE_FAILURE.get(key) == FAIL_REASON_DISABLED}


def build_fallback_llm_content(
    llm_content: tuple,
    force: bool = False,
) -> tuple:
    """构建 LLM 降级内容。

    启用且生成失败的槽位注入占位文本；被禁用的槽位保持 ``None``
    （禁用不是故障，不伪装 API 故障，也不渲染「待生成」占位）。

    Args:
        llm_content: 原始 LLM 内容元组 (global_macro, expert_review, health_check, penetration_deep)
        force: 设为 True 时对全部非禁用槽位强制使用占位文本（用于测试/预览）

    Returns:
        处理后的 LLM 内容元组（禁用槽位恒为 None）
    """
    disabled = _disabled_module_keys()
    if not force and not is_all_llm_failed(llm_content):
        # 部分成功 → 仅替换「启用且失败」的槽位（禁用槽位保持 None）
        result = list(llm_content[:4])
        for i, module_key in enumerate(_MODULE_KEYS):
            if result[i] is None and module_key not in disabled:
                result[i] = get_placeholder_text(module_key)
        return tuple(result)

    if force or is_all_llm_failed(llm_content):
        # 全部失败 → 非禁用槽位使用占位文本（全部禁用时全部保持 None，整章隐藏）
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        return tuple(None if key in disabled else get_placeholder_text(key, timestamp=ts) for key in _MODULE_KEYS)

    return llm_content
