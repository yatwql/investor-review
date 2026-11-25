"""LLM 生成骨架的边角分支（`llm/skeleton`）。

本层集中了「正文处理 + 用量合并 + 重算原因归因」三簇纯函数，以及若干
「取不到就退回缺省」的 provider 解析分支。归因特别要锁死：原因判定必须用
**本轮写基线之前**的上一轮键，否则两个分支恒不可达、内容变化被误标成 TTL 到期。
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from src.python.llm import skeleton as sk
from src.python.llm.observation import LlmObservation, bind_llm_observation, clear_llm_observation

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.llm]


@pytest.fixture(autouse=True)
def _clean_state():
    yield
    clear_llm_observation()
    sk.reset_prev_module_cache_keys()


class TestStripLlmFooter:
    def test_empty_input_returned_as_is(self):
        assert sk.strip_llm_footer("") == ""

    def test_footer_removed_but_body_kept(self):
        html = '<p>正文</p><p style="color:#888;font-size:12px">模型：x</p>'

        assert sk.strip_llm_footer(html) == "<p>正文</p>"


class TestFinalizeAndCache:
    def _config(self):
        return {"model": "mock-model"}

    def test_empty_output_records_api_error(self):
        """模型返回空白 → 不写缓存、记 API 失败原因（下游据此出占位文案）。"""
        sk.LLM_MODULE_FAILURE.pop("global_macro", None)
        with (
            patch.object(sk, "markdown_to_html", return_value="   "),
            patch.object(sk, "cache_set") as cache_set,
        ):
            html, cached = sk._finalize_and_cache("   ", None, "k", "global_macro", "mock-model", self._config(), False)

        assert (html, cached) == (None, False)
        assert sk.LLM_MODULE_FAILURE["global_macro"] == sk.FAIL_REASON_API_ERROR
        cache_set.assert_not_called()
        sk.LLM_MODULE_FAILURE.pop("global_macro", None)

    def test_cache_hit_tokens_are_reported_in_footer(self):
        """用量含缓存命中 token → 页脚写明命中量（成本口径可追溯）。"""
        usage = {"input_tokens": 100, "output_tokens": 10, "cache_read_input_tokens": 800}
        with (
            patch.object(sk, "markdown_to_html", return_value="<p>正文</p>"),
            patch.object(sk, "cache_set"),
            patch.object(sk, "record_per_module"),
        ):
            html, cached = sk._finalize_and_cache(
                "正文", usage, "k", "global_macro", "mock-model", self._config(), False
            )

        assert cached is False
        assert "缓存命中：800 tokens" in html


class TestMergeUsage:
    def test_both_empty_returns_none(self):
        assert sk._merge_usage(None, None) is None

    def test_single_side_returned(self):
        assert sk._merge_usage({"a": 1}, None) == {"a": 1}
        assert sk._merge_usage(None, {"a": 1}) == {"a": 1}

    def test_numeric_fields_are_summed(self):
        merged = sk._merge_usage({"in": 10}, {"in": 5})

        assert merged["in"] == 15

    def test_nested_dicts_are_merged_recursively(self):
        merged = sk._merge_usage({"costs": {"CNY": 0.1}}, {"costs": {"CNY": 0.2}})

        assert merged["costs"]["CNY"] == pytest.approx(0.3)

    def test_mixed_types_override_with_latest(self):
        """类型不同（数值 vs 文本）→ 用重试侧覆盖，不做无意义相加。"""
        merged = sk._merge_usage({"model": "a"}, {"model": "b"})

        assert merged["model"] == "b"


class TestProviderResolutionFallbacks:
    def test_cache_key_falls_back_when_chain_resolution_fails(self, monkeypatch):
        """provider chain 解析异常 → 键后缀退成 `unknown`（不抛、不产生空后缀）。"""
        monkeypatch.setattr(
            "src.python.llm.strategy.resolve_provider_chain",
            MagicMock(side_effect=RuntimeError("probe fault")),
        )
        config = {"_provider_list": [{"name": "p1"}]}

        key = sk._build_provider_cache_key("llm_x_fp", config, "global_macro", resolved_first_name=None)

        assert key == "llm_x_fp_unknown"

    def test_credential_precheck_failure_returns_empty_triple(self, monkeypatch):
        """凭据预检异常 → (None, None, "")：调用链按无预检继续。"""
        monkeypatch.setattr(
            "src.python.llm.strategy.resolve_provider_chain",
            MagicMock(side_effect=RuntimeError("probe fault")),
        )

        assert sk._resolve_first_provider({"_provider_list": [{"name": "p1"}]}, "global_macro") == (None, None, "")

    def test_legacy_single_provider_returns_empty_triple(self):
        assert sk._resolve_first_provider({}, "global_macro") == (None, None, "")


class TestRawFilter:
    def test_filter_applied_before_markdown(self):
        """`raw_filter_fn` 作用于模型原始输出（带换行的 Markdown），而非拼接后的 HTML。"""
        seen: dict = {}

        def _filter(raw: str) -> str:
            seen["raw"] = raw
            return raw.replace("600900", "[已过滤]")

        with (
            patch.object(sk, "call_llm", return_value=("持仓 600900 估值", {"output_tokens": 1}, {})),
            patch.object(sk, "cache_set"),
            patch.object(sk, "record_per_module"),
        ):
            html, _cached = sk._execute_llm_with_finalize(
                "sys",
                "user",
                {},
                1.0,
                None,
                100,
                "model",
                None,
                "mock-model",
                "cache-key",
                "global_macro",
                False,
                raw_filter_fn=_filter,
            )

        assert seen["raw"] == "持仓 600900 估值"
        assert "600900" not in html
        assert "[已过滤]" in html


class TestRecomputeAttribution:
    """归因判据：三条原因分支各自可达（回归：写基线与比对顺序颠倒会让后两条成为死路）。"""

    def _attribution(self, prev_key: str | None, precheck_key: str) -> LlmObservation:
        sink = LlmObservation()

        sk._attribute_recompute_reason(sink, "self_review", precheck_key, prev_key)

        return sink

    def test_no_previous_key_is_cache_miss(self):
        assert self._attribution(None, "k1").module_recompute_reasons() == {"self_review": "cache_miss"}

    def test_same_key_is_ttl_expired(self):
        assert self._attribution("k1", "k1").module_recompute_reasons() == {"self_review": "ttl_expired"}

    def test_changed_key_is_fingerprint_changed(self):
        assert self._attribution("k1", "k2").module_recompute_reasons() == {"self_review": "fingerprint_changed"}

    def test_already_attributed_module_is_not_overwritten(self):
        """预检已归因的基础模块不二次归因（否则 TTL 判据被污染）。"""
        sink = LlmObservation()
        sink.note_recompute_reason("global_macro", "ttl_expired")

        sk._attribute_recompute_reason(sink, "global_macro", "k2", "k1")

        assert sink.module_recompute_reasons() == {"global_macro": "ttl_expired"}

    def test_none_sink_is_noop(self, caplog):
        """无观测汇聚器（未绑定）→ 静默跳过，不留任何日志噪声。"""
        sk._attribute_recompute_reason(None, "self_review", "k2", "k1")

        assert caplog.text == ""

    def test_generate_content_uses_previous_round_key(self):
        """端到端：同一进程两轮键不同 → 第二轮记 fingerprint_changed（而非恒记 ttl_expired）。

        观测汇聚器按轮独立（每份报告重新绑定），跨轮保留的是骨架记下的「上一轮键」。
        """

        def _run(cache_key: str) -> LlmObservation:
            sink = LlmObservation()
            bind_llm_observation(sink)
            with (
                patch.object(sk, "cache_get", return_value=None),
                patch.object(sk, "call_llm", return_value=("正文", {}, {})),
                patch.object(sk, "cache_set"),
                patch.object(sk, "record_per_module"),
            ):
                sk.generate_llm_content(
                    {},
                    cache_key,
                    3600,
                    "sys",
                    "user",
                    True,
                    False,
                    100,
                    1.0,
                    None,
                    "mock-model",
                    "model",
                    module_key="self_review",
                )
            return sink

        assert _run("k1").module_recompute_reasons()["self_review"] == "cache_miss", (
            "首轮无上轮记录 → 保守记 cache_miss"
        )
        assert _run("k2").module_recompute_reasons()["self_review"] == "fingerprint_changed"
        assert _run("k2").module_recompute_reasons()["self_review"] == "ttl_expired", "同键重跑 → TTL 到期"


class TestDisabledAndUnconfigured:
    def test_disabled_module_returns_empty_pair(self, monkeypatch):
        monkeypatch.setattr(sk, "is_llm_module_enabled", lambda config, mk: False)
        sk.LLM_MODULE_FAILURE.pop("expert_review", None)

        assert sk.generate_llm_module({}, "expert_review") == (None, False)
        assert sk.LLM_MODULE_FAILURE["expert_review"] == sk.FAIL_REASON_DISABLED
        sk.LLM_MODULE_FAILURE.pop("expert_review", None)

    def test_disabled_module_batch_mode_returns_empty_batch(self, monkeypatch):
        """禁用 + 批量模式 → 空批次四元组（调用方按「无结果」处理，不解析空 dict）。"""
        monkeypatch.setattr(sk, "is_llm_module_enabled", lambda config, mk: False)

        assert sk.generate_llm_module({}, "expert_review", batch_preparer=lambda: []) == ({}, False, {}, 0)

    def test_unconfigured_module_returns_placeholder_reason(self, monkeypatch):
        monkeypatch.setattr(sk, "get_llm_config", lambda: None)
        sk.LLM_MODULE_FAILURE.pop("expert_review", None)

        assert sk.generate_llm_module(None, "expert_review") == (None, False)
        assert sk.LLM_MODULE_FAILURE["expert_review"] == sk.FAIL_REASON_NOT_CONFIGURED
        sk.LLM_MODULE_FAILURE.pop("expert_review", None)

    def test_unconfigured_module_batch_mode_returns_empty_batch(self, monkeypatch):
        monkeypatch.setattr(sk, "get_llm_config", lambda: None)

        assert sk.generate_llm_module(None, "expert_review", batch_preparer=lambda: []) == ({}, False, {}, 0)


class TestChapterDisabledMatrix:
    def test_maps_gated_sections_to_disabled_flags(self, monkeypatch):
        """章级开关：受限章节按 enabled_llm 推导禁用态，其余章节不参与。"""
        from src.python.core.registry import LLM_MODULE_GATED_SECTIONS

        monkeypatch.setattr(sk, "get_llm_config", lambda: {"enabled_llm": {}})
        monkeypatch.setattr(sk, "is_llm_module_enabled", lambda cfg, mk: mk != "health_check")

        matrix = sk.get_llm_chapter_disabled()

        assert set(matrix) == set(LLM_MODULE_GATED_SECTIONS)
        assert matrix["health_check"] is True
        assert all(flag is False for key, flag in matrix.items() if key != "health_check")


class TestLedgerContextInjection:
    """账本上下文回灌：决策反思与确定性信号只在接收模块生效，无样本时不注入。"""

    def _capture_user_prompt(self, monkeypatch, *, decisions: str, signals: str, active: bool = True) -> str:
        captured: dict = {}

        def _generate_llm_content(llm_config, cache_key, cache_ttl, system_prompt, user_prompt, *args, **kwargs):
            captured["user"] = user_prompt
            return ("<p>ok</p>", False)

        monkeypatch.setattr(sk, "generate_llm_content", _generate_llm_content)
        monkeypatch.setattr("src.python.core.decision_ledger.is_active", lambda: active)
        monkeypatch.setattr("src.python.core.decision_ledger.lessons_block", lambda: decisions)
        monkeypatch.setattr("src.python.core.signal_ledger.summary_block", lambda: signals)

        sk.generate_llm_module({}, "expert_review", prompt_builder=lambda: "基础提示")

        return captured["user"]

    def test_both_blocks_appended(self, monkeypatch):
        user = self._capture_user_prompt(monkeypatch, decisions="历史教训", signals="确定性信号")

        assert "基础提示" in user
        assert "历史教训" in user
        assert "确定性信号" in user

    def test_empty_blocks_not_injected(self, monkeypatch):
        user = self._capture_user_prompt(monkeypatch, decisions="", signals="")

        assert "基础提示" in user
        assert user.count("\n\n") >= 1, "附录/口径声明仍应存在，但不得出现空回灌分段"

    def test_inactive_ledger_skips_lessons_but_keeps_signals(self, monkeypatch):
        """决策账本未激活 → 不注入教训块；信号块按自身开关独立判定。"""
        user = self._capture_user_prompt(monkeypatch, decisions="历史教训", signals="确定性信号", active=False)

        assert "历史教训" not in user
        assert "确定性信号" in user

    def test_other_modules_do_not_receive_ledger_context(self, monkeypatch):
        """非接收模块（如 global_macro）不注入账本上下文。"""
        captured: dict = {}

        def _generate_llm_content(llm_config, cache_key, cache_ttl, system_prompt, user_prompt, *args, **kwargs):
            captured["user"] = user_prompt
            return ("<p>ok</p>", False)

        monkeypatch.setattr(sk, "generate_llm_content", _generate_llm_content)
        monkeypatch.setattr("src.python.core.decision_ledger.lessons_block", lambda: "历史教训")
        monkeypatch.setattr("src.python.core.signal_ledger.summary_block", lambda: "确定性信号")

        sk.generate_llm_module({}, "global_macro", prompt_builder=lambda: "基础提示")

        assert "历史教训" not in captured["user"]
        assert "确定性信号" not in captured["user"]
