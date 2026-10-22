"""文本安全边界（core.text_safety）— 孤立代理项净化的单元测试。

回归背景：TUI 追问经 ``input()`` 读到的非法 UTF-8 字节被 ``surrogateescape``
解成孤立代理项，httpx 序列化请求体时 ``.encode("utf-8")`` 抛
``UnicodeEncodeError``，整条 LLM provider 链被误判为「响应解析失败」。
"""

from __future__ import annotations

import pytest

from src.python.core.text_safety import (
    has_lone_surrogates,
    sanitize_llm_payload,
    sanitize_lone_surrogates,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestSanitizeLoneSurrogates:
    """单字符串净化：干净原样、孤立替换、代理对折叠。"""

    def test_clean_text_is_returned_unchanged(self):
        text = "本期汇率风险如何？😀"

        assert sanitize_lone_surrogates(text) == text
        assert has_lone_surrogates(text) is False

    def test_lone_surrogate_becomes_replacement_char(self):
        text = "\ud800本期仓位结构"

        cleaned = sanitize_lone_surrogates(text)

        assert cleaned == "\ufffd本期仓位结构"
        assert has_lone_surrogates(cleaned) is False
        assert cleaned.encode("utf-8")  # 不再抛 UnicodeEncodeError

    def test_surrogate_pair_collapses_to_astral_char(self):
        """高/低代理相邻时应组合成星平面字符（emoji 不丢）。"""
        text = "结论\ud83d\ude00"

        assert sanitize_lone_surrogates(text) == "结论😀"

    def test_non_string_is_returned_as_is(self):
        assert sanitize_lone_surrogates(None) is None  # type: ignore[arg-type]


class TestSanitizeLlmPayload:
    """请求体递归净化：嵌套 dict/list/tuple 中的字符串全覆盖。"""

    def test_nested_payload_strings_are_sanitized(self):
        payload = {
            "system": [{"type": "text", "text": "\ud800规则"}],
            "messages": [{"role": "user", "content": "问题\udc00"}],
            "meta": ("\ud800", 3),
        }

        cleaned = sanitize_llm_payload(payload)

        assert cleaned["system"][0]["text"] == "\ufffd规则"
        assert cleaned["messages"][0]["content"] == "问题\ufffd"
        assert cleaned["meta"] == ("\ufffd", 3)
        assert not has_lone_surrogates(str(cleaned))

    def test_non_text_values_pass_through(self):
        payload = {"max_tokens": 2048, "stream": False, "cache_control": None}

        assert sanitize_llm_payload(payload) == payload
