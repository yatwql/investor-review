# -*- coding: utf-8 -*-
"""LLM 模块「结果行」与失败原因文案（回归：失败被记成「跳过」、报告与日志两套文案）。

钉住三条：
  1. 模块结果行的分级：成功 / 开关关闭 / 预算跳过 走 INFO，**真失败必为 ERROR** 且带原因；
  2. 失败原因文案单源（`FAIL_REASON_LABELS`），报告模块状态与日志共用同一份；
  3. 未知原因码原样回显、None 返回空串（不得抛错、不得静默吞掉原因）。
"""

from __future__ import annotations

import logging

import pytest

from src.python.llm import failure_reasons

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


@pytest.fixture(autouse=True)
def _clean_failure_map(monkeypatch: pytest.MonkeyPatch):
    """每个用例用空的失败原因表，避免跨用例污染（模块级可变字典）。"""
    monkeypatch.setattr(failure_reasons, "LLM_MODULE_FAILURE", {})


class TestDescribeFailureReason:
    """失败原因码 → 上屏文案（单源标签表）。"""

    def test_known_codes_have_labels(self):
        """每个非 disabled 原因码都在标签表里（新增原因码必须同步文案）。"""
        codes = {
            failure_reasons.FAIL_REASON_NOT_CONFIGURED,
            failure_reasons.FAIL_REASON_API_ERROR,
            failure_reasons.FAIL_REASON_NETWORK_ERROR,
            failure_reasons.FAIL_REASON_TIMEOUT,
            failure_reasons.FAIL_REASON_CIRCUIT_OPEN,
            failure_reasons.FAIL_REASON_QUOTA_EXCEEDED,
        }
        missing = codes - set(failure_reasons.FAIL_REASON_LABELS)
        assert not missing, f"缺少上屏文案：{sorted(missing)}"

    def test_report_reuses_same_label_table(self):
        """报告模块状态与日志共用同一份标签表（防两处文案漂移）。"""
        from src.python.report import llm_module_info

        assert llm_module_info._DISPLAY_REASON is failure_reasons.FAIL_REASON_LABELS

    def test_unknown_code_passes_through(self):
        assert failure_reasons.describe_failure_reason("weird_code") == "weird_code"

    def test_none_is_empty(self):
        assert failure_reasons.describe_failure_reason(None) == ""


class TestModuleOutcomeLogging:
    """`_log_module_outcome` 的四条分支（成功 / 关开关 / 预算跳过 / 真失败）。"""

    @staticmethod
    def _labels():
        return {"global_macro": "全球政经局势"}

    def test_success_logs_info(self, caplog: pytest.LogCaptureFixture):
        from src.python.llm._llm_dispatch import _log_module_outcome

        with caplog.at_level(logging.INFO, logger="invest"):
            _log_module_outcome("global_macro", "<p>正文</p>", self._labels(), [])

        assert "全球政经局势生成完成" in caplog.text
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_disabled_switch_logs_info_not_error(self, caplog: pytest.LogCaptureFixture):
        from src.python.llm._llm_dispatch import _log_module_outcome

        failure_reasons.LLM_MODULE_FAILURE["global_macro"] = failure_reasons.FAIL_REASON_DISABLED
        with caplog.at_level(logging.INFO, logger="invest"):
            _log_module_outcome("global_macro", None, self._labels(), [])

        assert "开关关闭" in caplog.text
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_budget_skip_logs_info_not_error(self, caplog: pytest.LogCaptureFixture):
        from src.python.llm._llm_dispatch import _log_module_outcome

        with caplog.at_level(logging.INFO, logger="invest"):
            _log_module_outcome("global_macro", None, self._labels(), ["global_macro"])

        assert "总时间预算跳过" in caplog.text
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_provider_failure_logs_error_with_reason(self, caplog: pytest.LogCaptureFixture):
        """provider 全挂导致无内容 → ERROR，且带模块名与可读原因（不再混成「跳过」）。"""
        from src.python.llm._llm_dispatch import _log_module_outcome

        failure_reasons.LLM_MODULE_FAILURE["global_macro"] = {
            "attempted": ["deepseek-main: network_error"],
            "final_status": failure_reasons.FAIL_REASON_NETWORK_ERROR,
        }
        with caplog.at_level(logging.INFO, logger="invest"):
            _log_module_outcome("global_macro", None, self._labels(), [])

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) == 1
        message = errors[0].getMessage()
        assert "全球政经局势生成失败" in message
        assert "网络连接失败" in message
        assert "降级/占位" in message

    def test_unknown_reason_still_errors(self, caplog: pytest.LogCaptureFixture):
        """原因未记录（表中无该键）也要 ERROR，文案回退「原因未记录」。"""
        from src.python.llm._llm_dispatch import _log_module_outcome

        with caplog.at_level(logging.INFO, logger="invest"):
            _log_module_outcome("global_macro", None, self._labels(), [])

        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert errors and "原因未记录" in errors[0].getMessage()
