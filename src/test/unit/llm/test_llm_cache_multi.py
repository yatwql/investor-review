"""LLM Multi-Provider — 缓存适配。

测试 provider-aware cache key 构建、乐观预检、按实际 provider 落盘。

运行：
  pytest src/test/unit/llm/test_llm_cache_multi.py -v
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


class TestBuildProviderCacheKey(unittest.TestCase):
    """_build_provider_cache_key 单元测试。"""

    def test_legacy_mode_unchanged(self) -> None:
        """无 _provider_list → 返回原 key。"""
        from src.python.llm.skeleton import _build_provider_cache_key

        key = _build_provider_cache_key(
            "llm_global_macro_fp123",
            {"provider": "claude"},
            "global_macro",
        )
        self.assertEqual(key, "llm_global_macro_fp123")

    def test_chain_mode_appends_provider(self) -> None:
        """有 _provider_list + resolved_first_name → key 含 provider name。"""
        from src.python.llm.skeleton import _build_provider_cache_key

        key = _build_provider_cache_key(
            "llm_global_macro_fp123",
            {"_provider_list": [{"name": "p1"}, {"name": "p2"}]},
            "global_macro",
            resolved_first_name="p1",
        )
        self.assertEqual(key, "llm_global_macro_fp123_p1")

    def test_diff_providers_diff_keys(self) -> None:
        """不同 provider → 不同 cache key。"""
        from src.python.llm.skeleton import _build_provider_cache_key

        base_config = {"_provider_list": [{"name": "p1"}, {"name": "p2"}]}
        key1 = _build_provider_cache_key("llm_m_fp", base_config, "m", resolved_first_name="p1")
        key2 = _build_provider_cache_key("llm_m_fp", base_config, "m", resolved_first_name="p2")
        self.assertNotEqual(key1, key2)

    def test_same_provider_same_key(self) -> None:
        """相同 provider + 相同 fingerprint → 相同 key。"""
        from src.python.llm.skeleton import _build_provider_cache_key

        base_config = {"_provider_list": [{"name": "p1"}]}
        key1 = _build_provider_cache_key("llm_m_fp", base_config, "m", resolved_first_name="p1")
        key2 = _build_provider_cache_key("llm_m_fp", base_config, "m", resolved_first_name="p1")
        self.assertEqual(key1, key2)


class TestCachePrecheckAndWrite(unittest.TestCase):
    """乐观预检 + 按实际 provider 落盘。"""

    def test_orchestrator_precheck_key_matches_write_side(self) -> None:
        """**读写键同源**：编排层预检键必须与写侧（skeleton）逐字节相同。

        chain 模式下写侧会在裸键后追加 `_{provider}`，预检侧不追加时读的是不存在的短键：
        每份报告四模块全判 miss、全量派发，并虚报 `cache_misses`（真正命中发生在
        skeleton 的第二次预检）——观测上看起来就是「缓存没起作用」。
        """
        from src.python.llm.generators_orchestrator import _compute_module_cache_info

        chain_config = {
            "_provider_list": [{"name": "p1"}, {"name": "p2"}],
            "_strategy": "priority",
            "_preferred_providers": {},
        }
        info = _compute_module_cache_info(chain_config, {}, {}, 1.0, 1.0, 0.0, 0.0, 1, {}, None, None, False)
        for module_key in info:
            assert info[module_key]["key"].endswith("_p1"), module_key
        # 非链式配置（legacy）不加后缀——旧缓存不因本修复整体失效
        legacy = _compute_module_cache_info({}, {}, {}, 1.0, 1.0, 0.0, 0.0, 1, {}, None, None, False)
        assert all(not v["key"].endswith("_p1") for v in legacy.values())

    def test_orchestrator_precheck_hits_skeleton_written_cache(self) -> None:
        """端到端：写侧（skeleton）落盘的键，编排层预检必须命中。

        直接比较两侧各自构造出的键字串——这才是「真正会读到同一个文件」的断言；
        两边各拼一份字符串时，任何一侧漏一段后缀都不会报错，只表现为永久 miss。
        """
        from unittest.mock import patch

        from src.python.llm.generators_orchestrator import _compute_module_cache_info

        chain_config = {
            "_provider_list": [{"name": "p1", "provider": "claude", "api_key": "sk-1"}],
            "_strategy": "priority",
            "_preferred_providers": {},
        }
        info = _compute_module_cache_info(chain_config, {}, {}, 1.0, 1.0, 0.0, 0.0, 1, {}, None, None, False)
        bare_key = info["global_macro"]["key"].removesuffix("_p1")

        with (
            patch("src.python.llm.skeleton.cache_get", return_value=None),
            patch("src.python.llm.skeleton.cache_set") as mock_set,
            patch("src.python.llm.skeleton.call_llm") as mock_call,
            patch("src.python.llm.skeleton.clear_last_llm_failure"),
        ):
            from src.python.llm.skeleton import generate_llm_content

            mock_call.return_value = ("<p>x</p>", {"input_tokens": 1}, {"name": "p1", "model": "", "endpoint": ""})
            generate_llm_content(
                llm_config=chain_config,
                cache_key=bare_key,
                cache_ttl=3600,
                system_prompt="sys",
                user_prompt="user",
                cache_enabled=True,
                force=False,
                max_tokens=100,
                timeout=30,
                temperature=None,
                model=None,
                config_field="max_tokens_test",
                http_client=None,
                module_key="global_macro",
            )
        assert mock_set.call_args[0][0] == info["global_macro"]["key"]

    @patch("src.python.llm.skeleton.cache_get")
    @patch("src.python.llm.skeleton.call_llm")
    @patch("src.python.llm.skeleton.clear_last_llm_failure")
    def test_optimistic_precheck_hit(
        self,
        mock_clear: MagicMock,
        mock_call: MagicMock,
        mock_cache_get: MagicMock,
    ) -> None:
        """乐观预检命中 → 不调用 call_llm。"""
        from src.python.llm.skeleton import generate_llm_content

        mock_cache_get.return_value = "cached content"

        config = {
            "_provider_list": [
                {"name": "p1", "provider": "claude", "api_key": "sk-1"},
            ],
        }
        result, from_cache = generate_llm_content(
            llm_config=config,
            cache_key="llm_test_fp",
            cache_ttl=3600,
            system_prompt="sys",
            user_prompt="user",
            cache_enabled=True,
            force=False,
            max_tokens=100,
            timeout=30,
            temperature=None,
            model=None,
            config_field="max_tokens_test",
            http_client=None,
            module_key="test",
        )
        self.assertTrue(from_cache)
        mock_call.assert_not_called()
        # 验证预检 key 含 provider name
        precheck_key = mock_cache_get.call_args[0][0]
        self.assertIn("p1", precheck_key)

    @patch("src.python.llm.skeleton.cache_get")
    @patch("src.python.llm.skeleton.cache_set")
    @patch("src.python.llm.skeleton.call_llm")
    @patch("src.python.llm.skeleton.clear_last_llm_failure")
    def test_cache_write_with_provider(
        self,
        mock_clear: MagicMock,
        mock_call: MagicMock,
        mock_cache_set: MagicMock,
        mock_cache_get: MagicMock,
    ) -> None:
        """call_llm 成功后按实际 provider_name 落盘。"""
        from src.python.llm.skeleton import generate_llm_content

        mock_cache_get.return_value = None  # 未命中
        mock_call.return_value = ("生成的内容", {"input_tokens": 10}, {"name": "p2", "model": "", "endpoint": ""})

        config = {
            "_provider_list": [
                {"name": "p1", "provider": "claude", "api_key": "sk-1"},
                {"name": "p2", "provider": "openai", "api_key": "sk-2"},
            ],
        }
        result, from_cache = generate_llm_content(
            llm_config=config,
            cache_key="llm_test_fp",
            cache_ttl=3600,
            system_prompt="sys",
            user_prompt="user",
            cache_enabled=True,
            force=False,
            max_tokens=100,
            timeout=30,
            temperature=None,
            model=None,
            config_field="max_tokens_test",
            http_client=None,
            module_key="test",
        )
        self.assertFalse(from_cache)
        mock_call.assert_called_once()
        # 验证落盘 key 含实际 provider
        write_key = mock_cache_set.call_args[0][0]
        self.assertIn("p2", write_key)
        self.assertNotIn("p1", write_key)  # 不是乐观预检的 p1

    @patch("src.python.llm.skeleton.cache_get")
    @patch("src.python.llm.skeleton.cache_set")
    @patch("src.python.llm.skeleton.call_llm")
    @patch("src.python.llm.skeleton.clear_last_llm_failure")
    def test_legacy_cache_key_unchanged(
        self,
        mock_clear: MagicMock,
        mock_call: MagicMock,
        mock_cache_set: MagicMock,
        mock_cache_get: MagicMock,
    ) -> None:
        """无 _provider_list → cache key 不变。"""
        from src.python.llm.skeleton import generate_llm_content

        mock_cache_get.return_value = None
        mock_call.return_value = ("内容", {"prompt_tokens": 5}, None)

        config = {"provider": "claude", "api_key": "sk-1"}
        result, from_cache = generate_llm_content(
            llm_config=config,
            cache_key="llm_test_fp",
            cache_ttl=3600,
            system_prompt="sys",
            user_prompt="user",
            cache_enabled=True,
            force=False,
            max_tokens=100,
            timeout=30,
            temperature=None,
            model=None,
            config_field="max_tokens_test",
            http_client=None,
            module_key="test",
        )
        # 读 key = 原 cache_key
        get_key = mock_cache_get.call_args[0][0]
        self.assertEqual(get_key, "llm_test_fp")
        # 写 key = 原 cache_key
        write_key = mock_cache_set.call_args[0][0]
        self.assertEqual(write_key, "llm_test_fp")


if __name__ == "__main__":
    unittest.main()


class TestPrecheckSummaryLog:
    """每份报告一行缓存概况：命中/真未命中/重新生成跳过，三类可区分。"""

    def test_summary_line_reports_hits_misses_and_bypass(self, caplog):
        import logging

        from src.python.llm.generators_orchestrator import _log_precheck_summary

        results = {
            "global_macro": {"result": "<p>x</p>", "cached": True},
            "expert_review": {"result": None, "cached": False},
            "health_check": {"result": None, "cached": False},
        }
        cache_info = {
            "global_macro": {"can_cache": True},
            "expert_review": {"can_cache": True},
            "health_check": {"can_cache": False},
        }
        with caplog.at_level(logging.INFO, logger="invest"):
            _log_precheck_summary(results, {}, cache_info)
        line = next(r.getMessage() for r in caplog.records if "[LLM 预检]" in r.getMessage())
        assert "命中 1/3" in line
        assert "global_macro" in line
        assert "expert_review" in line  # 真未命中
        assert "health_check" in line  # 跳过缓存
