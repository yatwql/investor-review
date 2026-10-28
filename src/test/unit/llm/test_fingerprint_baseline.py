"""跨进程 LLM 指纹基线 — 换键归因不再依赖进程内存。

判定口径：键 = 生成输入的内容地址。键变 ⇒ 输入变（`fingerprint_changed`，并打出变化
组件）；键未变而读不到内容 ⇒ 只是老化（`ttl_expired`）；无任何上轮基线 ⇒ 冷启动
（`cache_miss`，不臆测）。基线快照只做诊断输入，读写失败一律降级为「无基线」。
"""

from __future__ import annotations


import pytest

from src.python.llm import fingerprint_baseline as fb

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm, pytest.mark.usefixtures("offline_external_sources")]


class TestSnapshotStorage:
    def test_save_then_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb, "BASELINE_FILE", str(tmp_path / "snap.json"))
        fb.reset_baseline_cache()
        assert fb.save_baseline({"holdings": "h1", "totals": "t1"}, {"expert_review": "llm_x_1"}) is True
        fb.reset_baseline_cache()  # 模拟新进程：只认落盘
        assert fb.baseline_components() == {"holdings": "h1", "totals": "t1"}
        assert fb.baseline_module_key("expert_review") == "llm_x_1"
        assert fb.baseline_module_key("global_macro") == ""

    def test_missing_file_is_empty_baseline(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb, "BASELINE_FILE", str(tmp_path / "absent.json"))
        fb.reset_baseline_cache()
        assert fb.baseline_components() == {}
        assert fb.baseline_module_key("expert_review") == ""

    def test_corrupt_file_degrades_silently(self, tmp_path, monkeypatch):
        path = tmp_path / "snap.json"
        path.write_text("{not json", encoding="utf-8")
        monkeypatch.setattr(fb, "BASELINE_FILE", str(path))
        fb.reset_baseline_cache()
        assert fb.load_baseline() == {}

    def test_empty_payload_not_written(self, tmp_path, monkeypatch):
        path = tmp_path / "snap.json"
        monkeypatch.setattr(fb, "BASELINE_FILE", str(path))
        fb.reset_baseline_cache()
        assert fb.save_baseline({}, {}) is False
        assert not path.exists()

    def test_changed_components_lists_names(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fb, "BASELINE_FILE", str(tmp_path / "snap.json"))
        fb.reset_baseline_cache()
        base = {"holdings": "a", "a_indices": "b", "totals": "c"}
        assert fb.changed_components({"holdings": "a", "a_indices": "B2", "totals": "c"}, base) == ["a_indices"]
        assert fb.changed_components({"holdings": "a"}, {}) == [], "无基线不臆测变化"


class TestResetClearsBothBaselines:
    """`reset_baseline_cache()` 必须同时清「跨进程快照」与「进程内上轮键」。

    回归场景：只清快照时，同进程里残留的上一轮键会让冷启动被误判为
    `fingerprint_changed`（整目录跑测试时表现为「单跑绿、合跑红」）。
    """

    def test_reset_clears_in_process_prev_keys(self, tmp_path, monkeypatch):
        from src.python.llm import fingerprint_baseline, skeleton
        from src.python.llm.generators_orchestrator import _key_changed_from_baseline

        monkeypatch.setattr(fingerprint_baseline, "BASELINE_FILE", str(tmp_path / "snap.json"))
        skeleton._PREV_MODULE_CACHE_KEY["penetration_deep"] = "llm_penetration_deep_OLD"
        fingerprint_baseline.reset_baseline_cache()
        assert skeleton._PREV_MODULE_CACHE_KEY == {}, "reset 须清空进程内上轮键"
        assert _key_changed_from_baseline("llm_penetration_deep_NEW", "penetration_deep") is None, (
            "无任何基线时不得臆测为「键变了」，应回落冷启动"
        )


class TestAttributionUsesKeyBaseline:
    """归因主信号是「键是否变化」，组件映射只作解释（可滞后于指纹函数入参）。"""

    def test_key_changed_across_process_is_fingerprint_changed(self, tmp_path, monkeypatch):
        from src.python.llm import fingerprint_baseline
        from src.python.llm.generators_orchestrator import _key_changed_from_baseline

        monkeypatch.setattr(fingerprint_baseline, "BASELINE_FILE", str(tmp_path / "snap.json"))
        fingerprint_baseline.reset_baseline_cache()
        fingerprint_baseline.save_baseline({}, {"expert_review": "llm_expert_review_OLD_deepseek-main"})
        fingerprint_baseline.reset_baseline_cache()
        assert _key_changed_from_baseline("llm_expert_review_NEW_deepseek-main", "expert_review") is True

    def test_same_key_across_process_means_only_ageing(self, tmp_path, monkeypatch):
        from src.python.llm import fingerprint_baseline
        from src.python.llm.generators_orchestrator import _key_changed_from_baseline

        monkeypatch.setattr(fingerprint_baseline, "BASELINE_FILE", str(tmp_path / "snap.json"))
        fingerprint_baseline.reset_baseline_cache()
        fingerprint_baseline.save_baseline({}, {"health_check": "llm_health_check_SAME"})
        fingerprint_baseline.reset_baseline_cache()
        assert _key_changed_from_baseline("llm_health_check_SAME", "health_check") is False

    def test_no_baseline_is_none_not_guess(self, tmp_path, monkeypatch):
        from src.python.llm import fingerprint_baseline
        from src.python.llm.generators_orchestrator import _key_changed_from_baseline

        monkeypatch.setattr(fingerprint_baseline, "BASELINE_FILE", str(tmp_path / "snap.json"))
        fingerprint_baseline.reset_baseline_cache()
        assert _key_changed_from_baseline("llm_penetration_deep_X", "penetration_deep") is None
        from src.python.llm.generators_orchestrator import _recompute_reason
        from src.python.llm.observation import RECOMPUTE_CACHE_MISS

        assert _recompute_reason({"can_cache": True}, None) == RECOMPUTE_CACHE_MISS


class TestBaselineWrittenByRun:
    """一次真实编排结束后基线落盘，供下个进程归因。"""

    def test_run_writes_snapshot(self, llm_cache_dir):
        from src.test.unit.llm._cache_fixtures import make_inputs, run_generate_all_llm

        fb.reset_baseline_cache()
        run_generate_all_llm(make_inputs())
        fb.reset_baseline_cache()  # 新进程视角
        keys = fb.load_baseline().get("keys") or {}
        assert "expert_review" in keys, "编排结束必须落盘各模块本轮缓存键"
        assert fb.baseline_components(), "同时落盘指纹组件哈希（解释哪一段输入变了）"

    def test_restart_with_changed_input_reports_fingerprint_changed(self, llm_cache_dir, caplog):
        import logging

        from src.test.unit.llm._cache_fixtures import make_inputs, run_generate_all_llm

        inputs = make_inputs()
        run_generate_all_llm(inputs)
        # 模拟进程重启：只有落盘基线，没有进程内上轮快照
        fb.reset_baseline_cache()
        from src.python.llm import generators_orchestrator as go

        go._LAST_FP_COMPONENTS = {}
        go._FINGERPRINT_CHANGED_MODULES.clear()
        from src.python.llm.skeleton import reset_prev_module_cache_keys

        reset_prev_module_cache_keys()

        changed = {**inputs, "a_indices": {"sh000300": {"name": "沪深300", "close": 4321.0, "change_pct": 1.5}}}
        with caplog.at_level(logging.INFO, logger="invest"):
            flags = run_generate_all_llm(changed)
        assert not all(flags), "输入变了应至少有一个模块未命中"
        assert any("相对上次进程" in r.getMessage() for r in caplog.records), "须说明基线来自上次进程"
        assert any("a_indices" in r.getMessage() for r in caplog.records), "须点名变化的组件"
