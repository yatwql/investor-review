"""文本安全边界 — 孤立代理项（lone surrogate）净化。

**成因**：POSIX 下 ``sys.stdin`` 的 ``errors`` 是 ``surrogateescape``，终端/管道
传入的非法 UTF-8 字节会被解码成 U+D800~U+DFFF 的孤立代理项；JSON 里的
``\\ud800`` 转义、HTML 数字字符引用（如 ``&#55357;``）同样会产出这类字符。
它们不是可编码的 Unicode 标量值：一旦进入 LLM 请求体，httpx 的 JSON 序列化
（``ensure_ascii=False``）会在 ``.encode("utf-8")`` 处抛 ``UnicodeEncodeError``，
被上层误分类成「响应解析失败」，整条 provider 链无谓失败。

**净化口径**：合法代理对折叠为对应码点（emoji 等星平面字符不丢），孤立代理项
替换为 U+FFFD（与 UTF-8 解码的 ``errors="replace"`` 语义一致）。

**使用边界**：LLM 请求/响应文本是唯一必须净化的关口（``llm.api_base`` 与
``llm._api_responses``），用户输入在进入会话（``qa.session``）时同样净化一次，
保证日志与历史记录里不留不可编码字符。其余纯内文（报告渲染、提示词常量）
无须调用。
"""

from __future__ import annotations

from typing import Any


def has_lone_surrogates(text: str) -> bool:
    """判断文本中是否含无法 UTF-8 编码的字符（孤立代理项）。"""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def sanitize_lone_surrogates(text: str) -> str:
    """净化孤立代理项；本来就干净（或非 ``str``）时原样返回。

    Args:
        text: 待净化文本（非 ``str`` 输入原样返回，便于在递归净化中复用）。

    Returns:
        合法代理对折叠为星平面字符、孤立代理项替换为 U+FFFD 后的文本。
    """
    if not isinstance(text, str) or not has_lone_surrogates(text):
        return text
    # utf-16 + surrogatepass 能原样承载孤立代理项；解码 errors="replace" 时
    # 相邻的高/低代理会先被组合成星平面字符，落单的才变成 U+FFFD。
    return text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def sanitize_llm_payload(value: Any) -> Any:
    """递归净化 LLM 请求体中的全部字符串（dict/list/tuple 内联，其余原样）。"""
    if isinstance(value, str):
        return sanitize_lone_surrogates(value)
    if isinstance(value, dict):
        return {key: sanitize_llm_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_llm_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_llm_payload(item) for item in value)
    return value


__all__ = [
    "has_lone_surrogates",
    "sanitize_lone_surrogates",
    "sanitize_llm_payload",
]
