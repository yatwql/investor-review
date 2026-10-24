"""llm/force_scope.py — 模块级强刷范围解析。

覆盖：键集全域覆盖注册表、粒度优先于全局、子集归一（去重/空白）、
未知键报错并列可选值、空输入退空集。
"""

from __future__ import annotations

import contextlib
import io

import pytest

from src.python.core.registry import get_llm_module_names
from src.python.llm.force_scope import (
    FORCEABLE_LLM_MODULES,
    is_module_forced,
    resolve_force_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]


class TestForceScopeRegistry:
    """键集与中央注册表的一致性（结构关系断言，不写死条数）。"""

    def test_keys_are_unique(self):
        assert len(FORCEABLE_LLM_MODULES) == len(set(FORCEABLE_LLM_MODULES))

    def test_keys_subset_of_registry(self):
        """可强刷键必须全部是注册表 settings_suffix（键名单一来源纪律）。"""
        names = get_llm_module_names()
        assert set(FORCEABLE_LLM_MODULES) <= set(names)

    def test_covers_parallel_schedulers(self):
        """四个并行调度模块必须可强刷（核心覆盖面保障）。"""
        expected = {"global_macro", "expert_review", "health_check", "penetration_deep"}
        assert expected <= set(FORCEABLE_LLM_MODULES)


class TestResolveForceScope:
    def test_force_all_returns_full_set(self):
        scope = resolve_force_scope(True, None)
        assert scope == frozenset(FORCEABLE_LLM_MODULES)

    def test_neither_returns_empty(self):
        assert resolve_force_scope(False, None) == frozenset()
        assert resolve_force_scope(False, []) == frozenset()

    def test_subset_dedup_and_strip(self):
        scope = resolve_force_scope(False, [" expert_review ", "expert_review", "global_macro"])
        assert scope == frozenset({"expert_review", "global_macro"})

    def test_granularity_overrides_global(self):
        """显式模块列表优先于全局开关（粒度优先）。"""
        scope = resolve_force_scope(True, ["health_check"])
        assert scope == frozenset({"health_check"})

    def test_unknown_key_raises_with_choices(self):
        with pytest.raises(ValueError) as ei:
            resolve_force_scope(False, ["bogus_module"])
        msg = str(ei.value)
        assert "bogus_module" in msg
        assert FORCEABLE_LLM_MODULES[0] in msg  # 列出合法键

    def test_blank_entries_ignored(self):
        assert resolve_force_scope(False, ["", "  "]) == frozenset()


class TestIsModuleForced:
    def test_member(self):
        assert is_module_forced(frozenset({"expert_review"}), "expert_review")

    def test_non_member(self):
        assert not is_module_forced(frozenset({"expert_review"}), "health_check")

    def test_empty_scope(self):
        assert not is_module_forced(frozenset(), "global_macro")


# ── 共享层接线：generate_all_llm 的模块级 force 传递 ──────────────────


class TestOrchestratorForceModules:
    """generate_all_llm / _compute_module_cache_info / _build_module_fns 的接线。"""

    def test_cache_info_per_module_can_cache(self):
        """指定模块 can_cache=False，未指定模块照常 True。"""
        from src.python.llm.generators_orchestrator import _compute_module_cache_info

        info = _compute_module_cache_info(
            {},
            {},
            {},
            0.0,
            0.0,
            0.0,
            0.0,
            0,
            {},
            None,
            None,
            False,
            force_modules=frozenset({"expert_review"}),
        )
        assert info["expert_review"]["can_cache"] is False
        assert info["global_macro"]["can_cache"] is True
        assert info["health_check"]["can_cache"] is True
        assert info["penetration_deep"]["can_cache"] is True

    def test_cache_info_global_force_still_all(self):
        """全局 force=True 时四模块全部不可缓存（向后兼容）。"""
        from src.python.llm.generators_orchestrator import _compute_module_cache_info

        info = _compute_module_cache_info({}, {}, {}, 0.0, 0.0, 0.0, 0.0, 0, {}, None, None, True)
        assert all(not v["can_cache"] for v in info.values())

    def test_precheck_logs_skip_reason_at_info(self, caplog):
        """不可缓存时留一条 INFO：否则用户只看到「又调了一遍 LLM」，分不清是缓存
        没命中还是自己选了「重新生成」。"""
        import logging

        from src.python.llm.generators_orchestrator import _precheck_one_cache

        info = {"key": "llm_expert_review_deadbeef", "ttl": 60, "can_cache": False, "thinking_key": "x"}
        with caplog.at_level(logging.INFO, logger="invest"):
            assert _precheck_one_cache(info, {}, "expert_review") == (None, False)
        records = [r for r in caplog.records if "跳过缓存读" in r.getMessage()]
        assert len(records) == 1
        assert records[0].levelno == logging.INFO

    def test_cache_info_default_unchanged(self):
        """未指定任何 force 时全部可缓存（缺省行为逐字节不变）。"""
        from src.python.llm.generators_orchestrator import _compute_module_cache_info

        info = _compute_module_cache_info({}, {}, {}, 0.0, 0.0, 0.0, 0.0, 0, {}, None, None, False)
        assert all(v["can_cache"] for v in info.values())

    def test_build_module_fns_per_module_force(self):
        """_build_module_fns 闭包逐模块取 force：指定模块 True、其余 False。"""
        from unittest.mock import patch

        from src.python.llm._llm_dispatch import _build_module_fns

        captured: dict[str, bool] = {}

        def _fake_gen(*args, **kwargs):
            captured[kwargs.get("_tag", "?")] = kwargs.get("force")
            return (None, False)

        with (
            patch(
                "src.python.llm._llm_dispatch.generate_global_macro",
                lambda *a, **k: _fake_gen(*a, **{**k, "_tag": "gm"}),
            ),
            patch(
                "src.python.llm._llm_dispatch.generate_expert_review",
                lambda *a, **k: _fake_gen(*a, **{**k, "_tag": "er"}),
            ),
            patch(
                "src.python.llm._llm_dispatch.generate_health_check",
                lambda *a, **k: _fake_gen(*a, **{**k, "_tag": "hc"}),
            ),
            patch(
                "src.python.llm._llm_dispatch.generate_penetration_deep_analysis",
                lambda *a, **k: _fake_gen(*a, **{**k, "_tag": "pd"}),
            ),
        ):
            fns = _build_module_fns(
                a_indices={},
                us_indices={},
                total_mv=0.0,
                total_cost=0.0,
                total_profit=0.0,
                total_today_profit=0.0,
                holdings_count=0,
                categories={},
                penetrated_assets=None,
                holdings_details=None,
                sector_flow=None,
                force=False,
                force_modules=frozenset({"health_check"}),
            )
            for fn in fns.values():
                fn(None, {})

        assert captured["hc"] is True
        assert captured["gm"] is False
        assert captured["er"] is False
        assert captured["pd"] is False

    def test_dispatch_passes_force_modules_to_build(self):
        """_dispatch_llm_workers 透传 force_modules 到 _build_module_fns。"""
        from unittest.mock import MagicMock, patch

        from src.python.llm.generators_orchestrator import _dispatch_llm_workers

        with (
            patch("src.python.llm._llm_dispatch._build_module_fns", return_value={}) as mock_build,
            patch("src.python.llm._llm_dispatch.make_http_client", return_value=MagicMock()),
        ):
            _dispatch_llm_workers(
                {"health_check": True},
                {},
                False,
                {},
                {},
                0,
                0,
                0,
                0,
                0,
                {},
                None,
                None,
                None,
                force_modules=frozenset({"global_macro"}),
            )
        assert mock_build.call_args.kwargs.get("force_modules") == frozenset({"global_macro"})


class TestNewsForceModules:
    """_fetch_llm_and_news / _submit_news_future 的新闻模块级强刷接线。"""

    def test_submit_news_future_passes_force(self):
        """force_news=True 时透传给 build_news_data 末位参数。"""
        from unittest.mock import MagicMock, patch

        from src.python.report._llm_news import _submit_news_future

        pool = MagicMock()
        with patch("src.python.report.news_correlation.build_news_data") as mock_build:
            _submit_news_future(pool, [], {"news_top_count": 10, "penetrated_assets": None}, True, "", True)
        args = pool.submit.call_args.args
        # args = (计时包装器, span_recorder, build_news_data, …)
        assert args[2] is mock_build
        assert args[-1] is True

    def test_submit_news_future_default_false(self):
        from unittest.mock import MagicMock, patch

        from src.python.report._llm_news import _submit_news_future

        pool = MagicMock()
        with patch("src.python.report.news_correlation.build_news_data"):
            _submit_news_future(pool, [], {"news_top_count": 10, "penetrated_assets": None}, True, "")
        assert pool.submit.call_args.args[-1] is False

    def test_fetch_llm_and_news_forces_news_when_in_scope(self):
        """news_correlation ∈ 强刷集合 → news future 收到 force=True。"""
        from unittest.mock import MagicMock, patch

        from src.python.report._llm_news import _fetch_llm_and_news

        reporter = MagicMock()
        with (
            patch("src.python.report._llm_news._submit_news_future", return_value=None) as mock_news,
            patch("src.python.report._llm_news._submit_llm_future", return_value=None),
            patch("src.python.config.features.is_feature_enabled", return_value=False),
        ):
            _fetch_llm_and_news(
                [],
                {},
                None,
                False,
                None,
                True,
                True,
                reporter,
                force_llm_modules=frozenset({"news_correlation"}),
            )
        assert mock_news.call_args.args[5] is True

    def test_fetch_llm_and_news_default_news_not_forced(self):
        from unittest.mock import MagicMock, patch

        from src.python.report._llm_news import _fetch_llm_and_news

        reporter = MagicMock()
        with (
            patch("src.python.report._llm_news._submit_news_future", return_value=None) as mock_news,
            patch("src.python.report._llm_news._submit_llm_future", return_value=None),
            patch("src.python.config.features.is_feature_enabled", return_value=False),
        ):
            _fetch_llm_and_news([], {}, None, False, None, True, True, reporter)
        assert mock_news.call_args.args[5] is False


class TestCliParserForceModules:
    """--llm-module 参数注册与取值。"""

    def test_parser_accepts_llm_module(self):
        from src.python.cli._parser import _build_parser

        parser = _build_parser()
        args = parser.parse_args(
            ["report", "--type", "full", "--llm-module", "expert_review", "--llm-module", "global_macro"]
        )
        assert args.llm_module == ["expert_review", "global_macro"]

    def test_parser_default_none(self):
        from src.python.cli._parser import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["report", "--type", "basic"])
        assert args.llm_module is None

    def test_parser_rejects_unknown_module(self):
        from src.python.cli._parser import _build_parser

        parser = _build_parser()
        with pytest.raises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parser.parse_args(["report", "--llm-module", "bogus"])
