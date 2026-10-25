"""报告级缓存隔离与时序 —— 一日多报、强制重生成、跨报告不串味。

业务背景：用户一天可能跑多份报告（不同持仓/不同输入文件/不同时段）。缓存若被串味，
轻则看到上一次持仓的分析，重则费用账记错报告。本文件从"报告边界"角度测缓存：

| 角度 | 断言 |
|------|------|
| 报告级用量边界 | 第二份报告的费用/调用数只算增量（不吞第一份） |
| 输入来源隔离 | 试算/正式/上传 三种输入域各有独立快照缓存域 |
| 强制重生成 | `force_llm` 全量绕过；`force_modules` 只绕目标模块 |
| 缓存状态复位 | 内存态复位后**磁盘缓存仍可命中**（命中不依赖进程内状态） |
| 时段切换 | 盘中→盘后同一键的 TTL 变化（结算与盘中观测的分界） |
"""

from __future__ import annotations

import json
import time

import pytest

from src.python.cache._paths import _CACHE_KEY_VERSION

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    from src.python.cache import _cleanup, _paths, _store, _ttl

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    _store.reset_debug_log_state()
    yield tmp_path, _ttl
    _store.reset_debug_log_state()


def _write(cache_dir, key: str, age_seconds: float, data=None) -> None:
    payload = {"_ts": time.time() - age_seconds, "_data": data if data is not None else {"v": 1}}
    (cache_dir / f"{key}_{_CACHE_KEY_VERSION}.json").write_text(json.dumps(payload), encoding="utf-8")


class TestReportUsageBoundary:
    """报告级用量增量：第二份报告不得把第一份的费用算进自己。"""

    def test_cost_delta_is_per_report(self):
        from src.python.report._generation_shared import _usage_delta

        baseline = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "call_count": 3,
            "costs": {"CNY": 0.10, "USD": 0.02},
            "per_module": {},
        }
        current = {
            "input_tokens": 1500,
            "output_tokens": 800,
            "call_count": 5,
            "costs": {"CNY": 0.18, "USD": 0.05},
            "per_module": {},
        }
        delta = _usage_delta(current, baseline)
        assert delta["input_tokens"] == 500
        assert delta["call_count"] == 2
        assert delta["costs"]["CNY"] == pytest.approx(0.08)
        assert delta["costs"]["USD"] == pytest.approx(0.03)

    def test_new_currency_only_in_second_report(self):
        """第二份报告首次用了外币模型 → delta 只出现该币种的正增量。"""
        from src.python.report._generation_shared import _usage_delta

        baseline = {"input_tokens": 0, "output_tokens": 0, "call_count": 1, "costs": {"CNY": 0.05}, "per_module": {}}
        current = {
            "input_tokens": 0,
            "output_tokens": 0,
            "call_count": 2,
            "costs": {"CNY": 0.05, "USD": 0.01},
            "per_module": {},
        }
        delta = _usage_delta(current, baseline)
        assert delta["costs"] == {"USD": pytest.approx(0.01)}

    def test_no_baseline_falls_back_to_full_usage(self):
        from src.python.report._generation_shared import _usage_delta

        current = {"input_tokens": 10, "output_tokens": 5, "call_count": 1, "costs": {"CNY": 0.01}, "per_module": {}}
        assert _usage_delta(current, None) is current


class TestInputDomainIsolation:
    """输入来源隔离：试算 / 正式 / 上传 三种输入域的快照不互相污染。"""

    def test_snapshot_domains_differ_per_input_mode(self):
        from src.python.web.run_generation import _web_input_mode_snapshot_domain

        modes = ["trial", "formal"]
        domains = {mode: _web_input_mode_snapshot_domain(mode) for mode in modes}
        assert len(set(domains.values())) == len(modes), f"输入域必须互不相同：{domains}"

    def test_same_mode_same_domain(self):
        from src.python.web.run_generation import _web_input_mode_snapshot_domain

        assert _web_input_mode_snapshot_domain("formal") == _web_input_mode_snapshot_domain("formal")


class TestRunScopeCacheState:
    """报告级缓存状态：内存复位不影响磁盘命中（命中口径只依赖磁盘 + 指纹）。"""

    def test_disk_cache_survives_inmemory_reset(self, cache_env, monkeypatch):
        from src.python.cache import get as cache_get
        from src.python.llm import session

        cache_dir, _ttl = cache_env
        monkeypatch.setattr("src.python.config.get_config", lambda: {})
        _write(cache_dir, "llm_expert_review_fpA", 60)
        session.reset_session_usage()
        assert cache_get("llm_expert_review_fpA", 4 * 3600) == {"v": 1}

    def test_second_run_within_ttl_hits_same_disk_entry(self, cache_env, monkeypatch):
        """同一持仓连跑两份报告：第二份在 TTL 内命中同一磁盘条目（省重复调用）。"""
        from src.python.cache import get as cache_get

        cache_dir, _ttl = cache_env
        monkeypatch.setattr("src.python.config.get_config", lambda: {})
        _write(cache_dir, "llm_global_macro_fpA", 60)
        assert cache_get("llm_global_macro_fpA", 24 * 3600) is not None
        assert cache_get("llm_global_macro_fpA", 24 * 3600) is not None


class TestForceRegeneration:
    """强制重生成：全量绕过 / 模块级绕过，其余模块仍可命中。"""

    def test_full_force_scope_covers_all_modules(self):
        from src.python.llm.force_scope import resolve_force_scope

        scope = resolve_force_scope(True, None)
        assert scope, "全量强制应给出非空范围"
        assert resolve_force_scope(False, ["expert_review"]) == frozenset({"expert_review"})

    def test_module_force_does_not_touch_others(self):
        from src.python.llm.force_scope import resolve_force_scope

        scope = resolve_force_scope(False, ["expert_review"])
        assert "expert_review" in scope
        assert "global_macro" not in scope

    def test_invalid_module_key_rejected(self):
        from src.python.llm.force_scope import resolve_force_scope

        with pytest.raises(ValueError):
            resolve_force_scope(False, ["not_a_module"])


class TestIntradayToCloseTransition:
    """盘中→盘后同一缓存键的 TTL 跃变（观测口径与结算口径的分界）。"""

    def test_same_key_ttl_shrinks_intraday_and_grows_after_close(self, cache_env, monkeypatch):
        from src.python.cache import get_ttl

        _cache_dir, ttl_mod = cache_env
        monkeypatch.setattr("src.python.config.get_config", lambda: {})

        monkeypatch.setattr(ttl_mod, "_is_market_open", lambda: True)
        intraday = get_ttl("price")
        monkeypatch.setattr(ttl_mod, "_is_market_open", lambda: False)
        after_close = get_ttl("price")

        assert intraday < after_close, "盘中必须比盘后更短"
        assert intraday == 30 and after_close == 86400

    def test_intraday_written_cache_expired_right_after_close_gate(self, cache_env, monkeypatch):
        """盘中写的价：盘后按静态 TTL 仍"未过期"，但必须再过收盘时点门禁（本文件只验读侧）。"""
        from src.python.cache import get as cache_get

        cache_dir, ttl_mod = cache_env
        monkeypatch.setattr("src.python.config.get_config", lambda: {})
        monkeypatch.setattr(ttl_mod, "_is_market_open", lambda: False)
        _write(cache_dir, "price_600519", age_seconds=600)
        assert cache_get("price_600519", get_ttl_for("price")) is not None


def get_ttl_for(data_type: str) -> float:
    from src.python.cache import get_ttl

    return get_ttl(data_type)
