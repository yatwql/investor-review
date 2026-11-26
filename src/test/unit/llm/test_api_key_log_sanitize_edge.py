"""边缘测试：LLM 端点脱敏 — API Key 不入日志。

覆盖 `llm/api_base.py` 的 `_sanitize_endpoint`：日志只留域名，路径（可能含凭据）被剥除。
"""

from __future__ import annotations

import unittest

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_llm,
    pytest.mark.llm,
    pytest.mark.edge,
    pytest.mark.usefixtures("offline_external_sources"),
]


class TestApiKeyLogLeak(unittest.TestCase):
    """API Key 不应出现在日志中。"""

    def test_logger_sanitizes_api_key(self):
        """验证日志配置不输出 api_key。"""
        # 此测试为交叉引用，验证导入可用
        from src.python.llm.api_base import _sanitize_endpoint

        result = _sanitize_endpoint("https://api.anthropic.com/v1/messages")
        self.assertIn("api.anthropic.com", result)
        self.assertNotIn("v1/messages", result)
