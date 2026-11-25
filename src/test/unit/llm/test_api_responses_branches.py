# -*- coding: utf-8 -*-
"""LLM 响应解析（_api_responses）：Gemini 截断/正文提取、Anthropic 非字符串 text 块、
成功响应的 usageMetadata 归一。

这几条分支直接决定「截断告警是否上屏」与「usage 是否记进成本台账」，写错会让
费用统计静默缺项或让截断被当成正常完成，故逐条锁定返回值与日志文案。

零网络：只喂构造好的响应 dict，`_log_token_usage`/`track_session_usage` 用替身。
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.python.llm import _api_responses as api

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestGeminiTruncation:
    def test_no_candidates_returns_false(self):
        assert api._check_gemini_truncation({"candidates": []}, 1024, "标签") is False

    def test_max_tokens_logs_error_and_returns_true(self, caplog):
        data = {"candidates": [{"finishReason": "MAX_TOKENS"}], "usageMetadata": {"candidatesTokenCount": 8000}}
        with caplog.at_level("ERROR"):
            assert api._check_gemini_truncation(data, 4096, "全球政经局势", "gemini_max_tokens") is True
        message = caplog.records[0].getMessage()
        assert "LLM 输出被截断 [全球政经局势]" in message
        assert "gemini_max_tokens=4096" in message
        assert "实际输出=8000 tokens" in message

    def test_stop_returns_false(self):
        assert api._check_gemini_truncation({"candidates": [{"finishReason": "STOP"}]}, 4096, "标签") is False

    def test_malformed_candidates_returns_false(self):
        assert api._check_gemini_truncation({"candidates": "bad"}, 4096, "标签") is False


class TestExtractContent:
    def test_non_string_text_block_is_stringified(self):
        data = {"content": [{"type": "text", "text": 12345}]}
        assert api._extract_content(data) == "12345"

    def test_multiple_text_blocks_joined(self):
        data = {"content": [{"text": "第一段"}, {"text": "第二段"}]}
        assert api._extract_content(data) == "第一段\n第二段"

    def test_error_payload_marks_server_error(self, caplog):
        with caplog.at_level("WARNING"):
            assert api._extract_content({"error": {"message": "overloaded"}}) is None
        assert api._server_error_local.last is True
        assert any("LLM API 返回错误" in rec.getMessage() for rec in caplog.records)


class TestGeminiContent:
    def test_error_payload_returns_none(self, caplog):
        with caplog.at_level("WARNING"):
            assert api._extract_content_from_gemini({"error": {"code": 429}}) is None
        assert any("Gemini API 返回错误" in rec.getMessage() for rec in caplog.records)

    def test_no_candidates_returns_empty_string(self):
        assert api._extract_content_from_gemini({"candidates": []}) == ""

    def test_parts_joined_skipping_empty(self):
        data = {"candidates": [{"content": {"parts": [{"text": "甲"}, {"text": ""}, {"not_text": 1}, {"text": "乙"}]}}]}
        assert api._extract_content_from_gemini(data) == "甲\n乙"

    def test_parts_without_text_returns_empty(self):
        data = {"candidates": [{"content": {"parts": [{"inlineData": {}}]}}]}
        assert api._extract_content_from_gemini(data) == ""

    def test_malformed_candidates_logs_and_returns_none(self, caplog):
        with caplog.at_level("WARNING"):
            assert api._extract_content_from_gemini({"candidates": "oops"}) is None
        assert any("Gemini API 响应格式异常" in rec.getMessage() for rec in caplog.records)


class TestSuccessResponseUsage:
    def test_usage_metadata_converted_when_usage_missing(self):
        data = {
            "candidates": [{"content": {"parts": [{"text": "回答"}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30},
        }
        with (
            patch.object(api, "_log_token_usage") as logged,
            patch.object(api, "track_session_usage") as tracked,
        ):
            content, usage = api._process_success_response(
                data,
                api._extract_content_from_gemini,
                lambda d, m: api._check_gemini_truncation(d, m, "标签"),
                4096,
                "gemini_max_tokens",
                "gemini",
                "gemini-2.5-pro",
                "标签",
                "https://example.invalid",
            )
        assert content == "回答"
        assert usage == {"prompt_tokens": 120, "completion_tokens": 30}
        logged.assert_called_once_with("gemini", usage, "标签", model_name="gemini-2.5-pro")
        tracked.assert_called_once()
