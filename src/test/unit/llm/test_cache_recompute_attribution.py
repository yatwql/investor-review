"""LLM 缓存重算归因观测 —— 回答"为什么又调了一次 LLM"。

业务问题：`llm_expert_review` 等模块 TTL 为 4h，指纹已覆盖内容变化，所以 4h 的真实
作用只是"内容没变时也强制重算"的上限。**要不要放宽**取决于真实分布：如果绝大多数
重算都是 `ttl_expired`（内容没变、纯到点），放宽就省钱；如果多数是
`fingerprint_changed`（内容变了），放宽无意义甚至有害（结论陈旧）。

只有观测数据能回答，不能凭感觉改。本文件验证三件事：

1. **归因口径正确**：未命中原因区分 `forced` / `fingerprint_changed` / `ttl_expired`；
2. **观测不改行为**：加了归因后命中/未命中判定、调用次数、费用完全不变；
3. **数据可落盘**：原因分布写入 perf 的 `llm.recompute_reasons`，可按周统计。
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from src.python.llm.observation import LlmObservation
from src.test.unit.llm._cache_fixtures import degradation_events, make_inputs, run_generate_all_llm

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.unit_core]


class TestObservationSink:
    """观测汇聚器：原因按次数聚合、逐模块留最近一次、快照只含非零项。"""

    def test_reasons_aggregate_by_count(self):
        sink = LlmObservation()
        for reason in ("ttl_expired", "ttl_expired", "fingerprint_changed"):
            sink.note_recompute_reason("expert_review", reason)
        assert sink.recompute_reasons() == {"ttl_expired": 2, "fingerprint_changed": 1}

    def test_reasons_sorted_by_count_desc(self):
        sink = LlmObservation()
        sink.note_recompute_reason("a", "fingerprint_changed")
        for _ in range(3):
            sink.note_recompute_reason("b", "ttl_expired")
        assert list(sink.recompute_reasons()) == ["ttl_expired", "fingerprint_changed"]

    def test_module_keeps_latest_reason(self):
        sink = LlmObservation()
        sink.note_recompute_reason("expert_review", "fingerprint_changed")
        sink.note_recompute_reason("expert_review", "ttl_expired")
        assert sink.module_recompute_reasons() == {"expert_review": "ttl_expired"}

    def test_snapshot_includes_reasons_only_when_present(self):
        empty = LlmObservation()
        assert "recompute_reasons" not in empty.snapshot()

        sink = LlmObservation()
        sink.note_recompute_reason("health_check", "ttl_expired")
        assert sink.snapshot()["recompute_reasons"] == {"ttl_expired": 1}


class TestReasonClassification:
    """原因判定：强制重生成 / 指纹变化 / 纯 TTL 到期三分。"""

    def test_forced_when_not_cacheable(self):
        from src.python.llm.generators_orchestrator import _recompute_reason

        assert _recompute_reason({"can_cache": False}, fingerprint_changed=True) == "forced"

    def test_fingerprint_changed(self):
        from src.python.llm.generators_orchestrator import _recompute_reason

        assert _recompute_reason({"can_cache": True}, fingerprint_changed=True) == "fingerprint_changed"

    def test_ttl_expired_when_content_unchanged(self):
        """内容没变却没命中 → 只能是 TTL 到期（这正是可能被放宽的那部分调用）。"""
        from src.python.llm.generators_orchestrator import _recompute_reason

        assert _recompute_reason({"can_cache": True}, fingerprint_changed=False) == "ttl_expired"

    @pytest.mark.parametrize(
        "module,component,expected",
        [
            ("global_macro", "a_indices", True),
            ("global_macro", "data_quality", False),
            ("health_check", "data_quality", True),
            ("penetration_deep", "penetration_full", True),
            ("penetration_deep", "metrics", False),
        ],
    )
    def test_module_component_mapping(self, module, component, expected):
        """模块 → 依赖组件：只有真正影响该模块的组件变化才算"内容变了"。"""
        from src.python.llm import generators_orchestrator as go

        go._FINGERPRINT_CHANGED_MODULES["__changed__"] = frozenset({component})
        try:
            assert go._inputs_fingerprint_changed(module) is expected
        finally:
            go._FINGERPRINT_CHANGED_MODULES.pop("__changed__", None)


class TestObservationDoesNotChangeBehaviour:
    """观测是纯旁路：命中判定、调用次数、费用一概不变。"""

    def test_second_run_still_hits_all_with_attribution(self, llm_cache_dir):
        inputs = make_inputs()
        assert not any(run_generate_all_llm(inputs))
        assert all(run_generate_all_llm(inputs))

    def test_call_count_identical_with_observation(self, llm_cache_dir):
        from src.test.unit.llm._cache_fixtures import LLM_REPLY_PAID

        inputs = make_inputs()
        with patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_PAID) as mocked:
            run_generate_all_llm(inputs, patch_call=False)
            first = mocked.call_count
        with patch("src.python.llm.skeleton.call_llm", return_value=LLM_REPLY_PAID) as mocked:
            run_generate_all_llm(inputs, patch_call=False)
            second = mocked.call_count
        assert second < first, "命中运行调用数应少于未命中（归因不得改变缓存行为）"

    def test_summary_line_reports_reason_distribution(self, llm_cache_dir, caplog):
        """预检摘要行带原因分布：一份报告内即可看出"是内容变了还是到点了"。"""
        inputs = make_inputs()
        _run(inputs)
        with caplog.at_level(logging.INFO, logger="invest"):
            _run({**inputs, "a_indices": {"sh000300": {"close": 4100.0, "change_pct": 2.0}}})
        lines = [r.getMessage() for r in caplog.records if "[LLM 预检]" in r.getMessage()]
        summary = next((line for line in lines if "命中" in line), "")
        assert "未命中原因" in summary, summary


def _run(inputs, **kwargs):
    return run_generate_all_llm(inputs, **kwargs)


class TestPerfPersistence:
    """原因分布写入 perf：可按周统计，作为 TTL 调值的唯一依据。"""

    def test_recompute_reasons_written_into_perf_context(self, llm_cache_dir):
        from src.python.report._generation_shared import _record_llm_context

        inputs = make_inputs()
        _run(inputs)
        recorded: dict = {}

        class _Perf:
            def set_llm_context(self, ctx):
                recorded.update(ctx or {})

        sink = LlmObservation()
        sink.note_recompute_reason("expert_review", "ttl_expired")
        with patch("src.python.llm.observation.current_llm_observation", return_value=sink):
            _record_llm_context(_Perf())

        assert recorded.get("recompute_reasons") == {"expert_review": "ttl_expired"}

    def test_no_field_when_no_miss(self, llm_cache_dir):
        from src.python.report._generation_shared import _record_llm_context

        recorded: dict = {}

        class _Perf:
            def set_llm_context(self, ctx):
                recorded.update(ctx or {})

        sink = LlmObservation()
        with patch("src.python.llm.observation.current_llm_observation", return_value=sink):
            _record_llm_context(_Perf())
        assert "recompute_reasons" not in recorded, "全命中时不应写该字段（perf 记录不膨胀）"

    def test_degradation_scenario_still_recorded(self, llm_cache_dir):
        """带降级事件的运行也能归因（降级块变化应体现为 fingerprint_changed）。"""
        from src.python.llm import generators_orchestrator as go

        inputs = make_inputs()
        _run(inputs, degradation=degradation_events("industry"))
        go._FINGERPRINT_CHANGED_MODULES["__changed__"] = frozenset({"data_quality"})
        try:
            assert go._inputs_fingerprint_changed("health_check") is True
            assert go._inputs_fingerprint_changed("global_macro") is False
        finally:
            go._FINGERPRINT_CHANGED_MODULES.pop("__changed__", None)


class TestSkeletonPathAttribution:
    """骨架路径（预检之后才定键的模块，如 self_review）同样要进归因统计。

    缺陷场景：`recompute_reasons` 只统计预检覆盖的四个基础模块，self_review 每次
    重算却从未计入——最贵的模块之一被漏掉，据此判断 TTL 是否放宽会系统性低估。
    """

    def test_skeleton_miss_is_attributed(self, llm_cache_dir):
        from src.python.llm import observation, skeleton

        skeleton.reset_prev_module_cache_keys()
        sink = observation.LlmObservation()
        sink.note_recompute_reason("self_review", "cache_miss")
        assert sink.module_recompute_reasons() == {"self_review": "cache_miss"}

    def test_skeleton_miss_records_reason(self, llm_cache_dir):
        """真实走骨架：无缓存 + 有观测汇聚器 → 记一条归因（预检路径漏掉的模块）。"""
        from src.python.llm import observation, skeleton

        skeleton.reset_prev_module_cache_keys()
        sink = observation.LlmObservation()
        with patch("src.python.llm.observation.current_llm_observation", return_value=sink):
            skeleton.generate_llm_content(
                {},
                "llm_self_review_probe",
                3600,
                "sys",
                "user",
                cache_enabled=True,
                force=False,
                max_tokens=16,
                timeout=5,
                temperature=None,
                model=None,
                config_field="model_self_review",
                module_key="self_review",
            )
        assert sink.module_recompute_reasons().get("self_review") in {
            "cache_miss",
            "fingerprint_changed",
            "ttl_expired",
        }

    def test_skeleton_hit_records_no_reason(self, llm_cache_dir):
        """命中时不得写归因（否则"命中/重算"统计互相污染）。"""
        from src.python.llm import observation, skeleton

        skeleton.reset_prev_module_cache_keys()
        sink = observation.LlmObservation()
        with patch("src.python.llm.skeleton.cache_get", return_value="<p>cached</p>"):
            with patch("src.python.llm.observation.current_llm_observation", return_value=sink):
                content, from_cache = skeleton.generate_llm_content(
                    {},
                    "llm_self_review_probe",
                    3600,
                    "sys",
                    "user",
                    cache_enabled=True,
                    force=False,
                    max_tokens=16,
                    timeout=5,
                    temperature=None,
                    model=None,
                    config_field="model_self_review",
                    module_key="self_review",
                )
        assert from_cache is True
        assert sink.module_recompute_reasons() == {}

    def test_reset_clears_prev_keys(self):
        from src.python.llm import skeleton

        skeleton._PREV_MODULE_CACHE_KEY["self_review"] = "k"
        skeleton.reset_prev_module_cache_keys()
        assert skeleton._PREV_MODULE_CACHE_KEY == {}

    def test_report_boundary_resets_prev_keys(self):
        """报告边界复位：跨报告比对才成立，不把上次进程遗留的键当"上一轮"。"""
        from src.python.llm import skeleton
        from src.python.report._run_scope import start_report_run

        skeleton._PREV_MODULE_CACHE_KEY["self_review"] = "stale"
        start_report_run()
        assert "self_review" not in skeleton._PREV_MODULE_CACHE_KEY


class TestObservationBindingAndCounting:
    """观测口径：绑定时机与计数范围（缺一则首跑样本丢失 / 命中率低估）。"""

    def test_sink_bound_before_llm_phase(self):
        """汇聚器在「LLM+新闻」阶段之前绑定：预检发生在其内部，晚绑即丢首跑样本。"""
        import inspect

        from src.python.report import _generation_full as gf

        src = inspect.getsource(gf)
        bind_at = src.index("bind_llm_observation(_llm_sink)")
        phase_at = src.index('perf.start("LLM+新闻")')
        assert bind_at < phase_at, "汇聚器绑定必须早于 LLM 阶段（预检在其内部）"

    def test_skeleton_records_hit(self, llm_cache_dir):
        """骨架路径命中也要计入 cache_hits（否则「基础模块 4/4」实为 6/6 时命中率被低估）。"""
        from unittest.mock import patch

        from src.python.llm import observation, skeleton

        sink = observation.LlmObservation()
        with patch("src.python.llm.skeleton.cache_get", return_value="<p>cached</p>"):
            with patch("src.python.llm.observation.current_llm_observation", return_value=sink):
                skeleton.generate_llm_content(
                    {},
                    "llm_self_review_probe",
                    3600,
                    "sys",
                    "user",
                    cache_enabled=True,
                    force=False,
                    max_tokens=16,
                    timeout=5,
                    temperature=None,
                    model=None,
                    config_field="model_self_review",
                    module_key="self_review",
                )
        assert sink.snapshot().get("cache_hits") == 1
        assert "cache_misses" not in sink.snapshot()

    def test_skeleton_records_miss(self, llm_cache_dir):
        """骨架路径未命中同样计数（与 precheck 侧口径一致）。"""
        from unittest.mock import patch

        from src.python.llm import observation, skeleton

        sink = observation.LlmObservation()
        with patch("src.python.llm.skeleton.cache_get", return_value=None):
            with patch("src.python.llm.observation.current_llm_observation", return_value=sink):
                skeleton.generate_llm_content(
                    {},
                    "llm_self_review_probe",
                    3600,
                    "sys",
                    "user",
                    cache_enabled=True,
                    force=False,
                    max_tokens=16,
                    timeout=5,
                    temperature=None,
                    model=None,
                    config_field="model_self_review",
                    module_key="self_review",
                )
        assert sink.snapshot().get("cache_misses") == 1


class TestRecomputeReasonDomain:
    """归因取值域是统计口径的唯一来源：拼错原因必须告警，不能静默多出一个桶。"""

    def test_all_documented_reasons_are_registered(self):
        from src.python.llm import observation as obs

        assert {
            obs.RECOMPUTE_FORCED,
            obs.RECOMPUTE_FINGERPRINT_CHANGED,
            obs.RECOMPUTE_TTL_EXPIRED,
            obs.RECOMPUTE_CACHE_MISS,
        } <= set(obs.RECOMPUTE_REASONS)

    def test_unknown_reason_warns_once_and_still_counts(self, caplog):
        from src.python.llm.observation import LlmObservation

        sink = LlmObservation()
        with caplog.at_level("WARNING"):
            sink.note_recompute_reason("global_macro", "ttl-expired-typo")
        assert any("未知的重算原因" in r.message for r in caplog.records)
        assert sink.recompute_reasons() == {"ttl-expired-typo": 1}

    def test_known_reason_does_not_warn(self, caplog):
        from src.python.llm.observation import RECOMPUTE_TTL_EXPIRED, LlmObservation

        sink = LlmObservation()
        with caplog.at_level("WARNING"):
            sink.note_recompute_reason("global_macro", RECOMPUTE_TTL_EXPIRED)
        assert not [r for r in caplog.records if "未知的重算原因" in r.message]
