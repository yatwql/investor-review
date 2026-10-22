"""Excel 报告 LLM 用量页签单元测试 — `_build_llm_usage_sheet` 状态判定。

从 `test_excel_generator.py` 分出：本文件只覆盖缓存/成功/禁用/失败四态
与表头/行内容契约，其余（生成主路径、模块缺失降级、页签创建）留在主分片。
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import pytest

from src.python.report.progress import SilentProgressReporter

pytestmark = [pytest.mark.unit, pytest.mark.unit_report]


class TestBuildLlmUsageSheet(unittest.TestCase):
    """测试 _build_llm_usage_sheet 中缓存/成功/禁用/失败的状态判定。"""

    def setUp(self):
        self.wb = MagicMock()
        self.prog = SilentProgressReporter()
        self._name_map = {
            "global_macro": "全球政经局势",
            "expert_review": "智囊团深度复盘",
            "health_check": "持仓体检报告",
            "penetration_deep": "穿透深度分析",
        }

    def _run(self, raw_session: dict, formatted: dict, module_failure: dict | None = None) -> MagicMock:
        """执行 build_llm_usage_sheet 并返回 write_llm_usage_sheet 的 mock。"""
        if module_failure is None:
            module_failure = {}
        from contextlib import ExitStack

        with ExitStack() as stack:
            mock_write = stack.enter_context(patch("src.python.report.summary.write_llm_usage_sheet"))
            stack.enter_context(patch("src.python.llm.get_session_usage", return_value=raw_session))
            stack.enter_context(patch("src.python.llm.format_session_usage", return_value=formatted))
            stack.enter_context(patch("src.python.llm.prompts.LLM_MODULE_FAILURE", module_failure))
            stack.enter_context(patch("src.python.core.registry.get_llm_module_names", return_value=self._name_map))
            from src.python.report.excel_llm_usage import build_llm_usage_sheet

            build_llm_usage_sheet(self.wb, self.prog)
        return mock_write

    def test_cache_hit_all_modules(self):
        """全部模块缓存命中 → 各模块状态均为 'cached'、标签为 '缓存'。"""
        formatted = {
            "has_usage": True,
            "call_count": 0,
            "per_module": {
                "global_macro": {
                    "model": "deepseek-v4-flash",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 500,
                    "cost": 0.0,
                    "thinking": False,
                    "endpoint": "",
                },
                "expert_review": {
                    "model": "claude-sonnet-4",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 1200,
                    "cost": 0.0,
                    "thinking": True,
                    "endpoint": "",
                },
                "health_check": {
                    "model": "gpt-4o",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 800,
                    "cost": 0.0,
                    "thinking": False,
                    "endpoint": "",
                },
                "penetration_deep": {
                    "model": "deepseek-v4-flash",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 600,
                    "cost": 0.0,
                    "thinking": False,
                    "endpoint": "",
                },
            },
        }
        mock_write = self._run({}, formatted)
        mock_write.assert_called_once()
        excel_module_info = mock_write.call_args[0][2]

        by_key = {e["key"]: e for e in excel_module_info}
        for mk in ["global_macro", "expert_review", "health_check", "penetration_deep"]:
            with self.subTest(module=mk):
                self.assertEqual(by_key[mk]["status"], "cached")
                self.assertEqual(by_key[mk]["status_label"], "缓存")
                self.assertTrue(by_key[mk]["cached"])
        self.assertTrue(by_key["expert_review"]["thinking"])

    def test_mixed_cache_and_success(self):
        """混合缓存和真实调用 → 各自正确的状态。"""
        formatted = {
            "has_usage": True,
            "call_count": 2,
            "per_module": {
                "global_macro": {
                    "model": "deepseek-v4-flash",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 500,
                    "cost": 0.0,
                    "thinking": False,
                    "endpoint": "",
                },
                "expert_review": {
                    "model": "claude-sonnet-4",
                    "cached": False,
                    "input_tokens": 1500,
                    "output_tokens": 800,
                    "cache_hit_tokens": 0,
                    "cost": 0.005,
                    "thinking": True,
                    "endpoint": "https://api.test.com",
                },
            },
        }
        mock_write = self._run({}, formatted)
        mock_write.assert_called_once()
        excel_module_info = mock_write.call_args[0][2]
        by_key = {e["key"]: e for e in excel_module_info}

        self.assertEqual(by_key["global_macro"]["status"], "cached")
        self.assertEqual(by_key["global_macro"]["total_tokens"], 0)
        self.assertEqual(by_key["expert_review"]["status"], "success")
        self.assertEqual(by_key["expert_review"]["status_label"], "成功")
        self.assertEqual(by_key["expert_review"]["total_tokens"], 2300)
        self.assertEqual(by_key["expert_review"]["input_tokens"], 1500)
        self.assertEqual(by_key["expert_review"]["output_tokens"], 800)
        self.assertTrue(by_key["expert_review"]["thinking"])
        self.assertEqual(by_key["expert_review"]["endpoint"], "https://api.test.com")

    def test_disabled_module(self):
        """禁用模块 → excel_module_info 含已禁用状态。"""
        from src.python.llm import FAIL_REASON_DISABLED

        formatted = {"has_usage": True, "per_module": {}}
        mock_write = self._run(
            {},
            formatted,
            module_failure={"global_macro": FAIL_REASON_DISABLED},
        )
        mock_write.assert_called_once()
        excel_module_info = mock_write.call_args[0][2]
        by_key = {e["key"]: e for e in excel_module_info}

        self.assertIn("global_macro", by_key)
        self.assertEqual(by_key["global_macro"]["status"], "disabled")
        self.assertEqual(by_key["global_macro"]["status_label"], "已禁用")
        self.assertEqual(by_key["global_macro"]["model"], "")

    def test_failed_module(self):
        """失败模块 → excel_module_info 含失败描述。"""
        from src.python.llm import FAIL_REASON_API_ERROR

        formatted = {"has_usage": True, "per_module": {}}
        mock_write = self._run(
            {},
            formatted,
            module_failure={"health_check": FAIL_REASON_API_ERROR},
        )
        mock_write.assert_called_once()
        excel_module_info = mock_write.call_args[0][2]
        by_key = {e["key"]: e for e in excel_module_info}

        self.assertIn("health_check", by_key)
        self.assertEqual(by_key["health_check"]["status"], "failed")
        self.assertEqual(by_key["health_check"]["status_label"], "LLM API 调用失败")

    def test_disabled_overrides_per_module(self):
        """禁用标记优先于 per_module 数据（即使有缓存数据也不显示）。"""
        from src.python.llm import FAIL_REASON_DISABLED

        formatted = {
            "has_usage": True,
            "per_module": {
                "global_macro": {
                    "model": "deepseek-v4-flash",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 500,
                    "cost": 0.0,
                    "thinking": False,
                    "endpoint": "",
                },
            },
        }
        mock_write = self._run(
            {},
            formatted,
            module_failure={"global_macro": FAIL_REASON_DISABLED},
        )
        excel_module_info = mock_write.call_args[0][2]
        gm = next(e for e in excel_module_info if e["key"] == "global_macro")
        # 即使有缓存数据，禁用标记优先
        self.assertEqual(gm["status"], "disabled")
        self.assertEqual(gm["status_label"], "已禁用")

    def test_unknown_modules_skipped(self):
        """无 per_module 且无失败原因 → excel_module_info 为空，不调用 write_llm_usage_sheet。"""
        formatted = {"has_usage": True, "per_module": {}}
        mock_write = self._run({}, formatted)
        # 当 excel_module_info 为空时 build_llm_usage_sheet 直接 return，不调用 write_llm_usage_sheet
        mock_write.assert_not_called()

    def test_no_usage_returns_early(self):
        """format_session_usage 无 has_usage → 不调用 write_llm_usage_sheet。"""
        formatted = {"has_usage": False, "per_module": {}}
        mock_write = self._run({}, formatted)
        mock_write.assert_not_called()

    def test_raw_session_per_module_fallback(self):
        """raw_session 有 per_module 数据但 formatted 无 per_module → 仍应正确写入。

        回归验证：format_session_usage 在 call_count=0 且 per_module 有数据时返回
        has_usage=True（含 per_module），但如果时序/状态导致返回 {"has_usage": False}
        （不含 per_module），build_llm_usage_sheet 应通过 raw_session 拿到数据。
        """
        raw_session = {
            "per_module": {
                "global_macro": {
                    "model": "deepseek-v4-flash",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 500,
                    "cost": 0.0,
                    "thinking": False,
                    "endpoint": "",
                },
            },
        }
        # format_session_usage 返回无 per_module 的"空"结果（模拟边界情况）
        formatted = {"has_usage": False}
        mock_write = self._run(raw_session, formatted)
        # 必须仍被调用，而非因 excel_module_info 为空而跳过
        mock_write.assert_called_once()
        excel_module_info = mock_write.call_args[0][2]
        self.assertEqual(len(excel_module_info), 1)
        self.assertEqual(excel_module_info[0]["key"], "global_macro")
        self.assertEqual(excel_module_info[0]["status"], "cached")

    def test_all_states_mixed(self):
        """禁用、失败、缓存、成功混合 → 各模块正确渲染且数量正确。"""
        from src.python.llm import FAIL_REASON_DISABLED, FAIL_REASON_TIMEOUT

        formatted = {
            "has_usage": True,
            "call_count": 1,
            "per_module": {
                "global_macro": {
                    "model": "deepseek-v4-flash",
                    "cached": False,
                    "input_tokens": 500,
                    "output_tokens": 300,
                    "cache_hit_tokens": 0,
                    "cost": 0.002,
                    "thinking": False,
                    "endpoint": "",
                },
                "expert_review": {
                    "model": "claude-sonnet-4",
                    "cached": True,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_hit_tokens": 1000,
                    "cost": 0.0,
                    "thinking": True,
                    "endpoint": "",
                },
            },
        }
        mock_write = self._run(
            {},
            formatted,
            module_failure={
                "health_check": FAIL_REASON_DISABLED,
                "penetration_deep": FAIL_REASON_TIMEOUT,
            },
        )
        mock_write.assert_called_once()
        excel_module_info = mock_write.call_args[0][2]
        # 4 个模块都应出现在表格中
        by_key = {e["key"]: e for e in excel_module_info}

        self.assertEqual(by_key["global_macro"]["status"], "success")
        self.assertEqual(by_key["global_macro"]["status_label"], "成功")
        self.assertEqual(by_key["expert_review"]["status"], "cached")
        self.assertEqual(by_key["expert_review"]["status_label"], "缓存")
        self.assertEqual(by_key["health_check"]["status"], "disabled")
        self.assertEqual(by_key["health_check"]["status_label"], "已禁用")
        self.assertEqual(by_key["penetration_deep"]["status"], "failed")
        self.assertIn("请求超时", by_key["penetration_deep"]["status_label"])
        self.assertEqual(len(excel_module_info), 4)
