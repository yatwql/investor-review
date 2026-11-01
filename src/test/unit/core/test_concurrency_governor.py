"""进程级并发预算（core/concurrency）：分配、缩池、释放与观测。

回归背景：各池只做「自己不超 max_total_workers」的逐池钳位，进程里多池叠加实际
可达 15+ 线程；弱机器（4 核）上就是互相争 CPU。预算层只兜底、不改各模块取值。
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from src.python.core import concurrency as cc

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


def _patch_budget(monkeypatch, *, max_total: int, cpu: int | None):
    monkeypatch.setattr(
        "src.python.config.get_config",
        lambda: {"batch": {"max_total_workers": max_total}},
    )
    monkeypatch.setattr(cc.os, "cpu_count", lambda: cpu)
    cc.GOVERNOR.reset()


class TestBudgetResolution:
    def test_budget_is_min_of_config_and_cores(self, monkeypatch):
        _patch_budget(monkeypatch, max_total=15, cpu=4)
        assert cc.ConcurrencyGovernor.resolve_budget() == 4

    def test_unknown_cpu_count_degrades_to_one(self, monkeypatch):
        _patch_budget(monkeypatch, max_total=15, cpu=None)
        assert cc.ConcurrencyGovernor.resolve_budget() == 1

    def test_broken_config_falls_back_to_default(self, monkeypatch):
        def _boom():
            raise RuntimeError("config broken")

        monkeypatch.setattr("src.python.config.get_config", _boom)
        monkeypatch.setattr(cc.os, "cpu_count", lambda: 8)
        # 配置读不到 → 用默认预算 15，再按核数钳位 → 8
        assert cc.ConcurrencyGovernor.resolve_budget() == 8


class TestLeaseAccounting:
    def test_acquire_within_budget_grants_requested(self, monkeypatch):
        _patch_budget(monkeypatch, max_total=15, cpu=8)
        cc.GOVERNOR.begin_run()
        assert cc.GOVERNOR.acquire("batch:a", 3) == 3
        snapshot = cc.GOVERNOR.snapshot()
        assert snapshot["budget"] == 8
        assert snapshot["granted"] == 3
        assert snapshot["pools"] == {"batch:a": 3}

    def test_over_budget_shrinks_to_remaining_with_warning(self, monkeypatch, caplog):
        _patch_budget(monkeypatch, max_total=15, cpu=4)
        cc.GOVERNOR.begin_run()
        assert cc.GOVERNOR.acquire("batch:a", 3) == 3
        with caplog.at_level(logging.WARNING, logger="invest"):
            granted = cc.GOVERNOR.acquire("batch:b", 8)
        assert granted == 1, "剩余额度 1 → 缩到 1（保底可用）"
        assert any("缩至 1" in r.getMessage() for r in caplog.records)
        assert cc.GOVERNOR.snapshot()["clamps"] == 1

    def test_same_name_lease_is_idempotent(self, monkeypatch):
        _patch_budget(monkeypatch, max_total=15, cpu=8)
        cc.GOVERNOR.begin_run()
        assert cc.GOVERNOR.acquire("batch:a", 2) == 2
        assert cc.GOVERNOR.acquire("batch:a", 5) == 2, "同名池重复申请返回既有额度，不重复占预算"
        assert cc.GOVERNOR.snapshot()["granted"] == 2

    def test_release_frees_budget(self, monkeypatch):
        _patch_budget(monkeypatch, max_total=15, cpu=3)
        cc.GOVERNOR.begin_run()
        assert cc.GOVERNOR.acquire("batch:a", 3) == 3
        cc.GOVERNOR.release("batch:a")
        assert cc.GOVERNOR.snapshot()["granted"] == 0
        assert cc.GOVERNOR.acquire("batch:b", 3) == 3

    def test_worker_pool_releases_on_exit(self, monkeypatch):
        _patch_budget(monkeypatch, max_total=15, cpu=4)
        cc.GOVERNOR.begin_run()
        with cc.worker_pool("batch:wp", 3, thread_name_prefix="wp") as pool:
            assert pool._max_workers == 3
            assert cc.GOVERNOR.snapshot()["pools"] == {"batch:wp": 3}
        assert cc.GOVERNOR.snapshot()["granted"] == 0


class TestPerfObservation:
    def test_snapshot_carries_governor_counters(self, monkeypatch):
        _patch_budget(monkeypatch, max_total=15, cpu=4)
        from src.python.core.perf import PerfCollector

        perf = PerfCollector(report_type="full", holdings=[])
        cc.GOVERNOR.acquire("batch:a", 3)
        cc.GOVERNOR.acquire("batch:b", 8)  # 超预算 → 缩到 1，计一次 clamp
        counters = perf.snapshot().counters
        assert counters["concurrency_budget"] == 4
        assert counters["concurrency_peak"] == 4
        assert counters["concurrency_clamps"] == 1


class TestProfileScaling:
    """并发档位（借鉴 test-runner 的 high/medium/low 系数）：只缩申请值，不改相对权重。"""

    @staticmethod
    def _patch_profile(monkeypatch, profile: str | None):
        cfg: dict[str, dict[str, Any]] = {"batch": {"max_total_workers": 15}}
        if profile is not None:
            cfg["batch"]["profile"] = profile
        monkeypatch.setattr("src.python.config.get_config", lambda: cfg)
        monkeypatch.setattr(cc.os, "cpu_count", lambda: 16)
        cc.GOVERNOR.reset()

    def test_high_is_noop(self, monkeypatch):
        self._patch_profile(monkeypatch, "high")
        assert cc.scale_workers(8) == 8

    def test_medium_halves(self, monkeypatch):
        self._patch_profile(monkeypatch, "medium")
        assert cc.scale_workers(8) == 4

    def test_low_quarters_with_floor_one(self, monkeypatch):
        self._patch_profile(monkeypatch, "low")
        assert cc.scale_workers(8) == 2
        assert cc.scale_workers(2) == 1, "小池子缩到 1，不会归零"

    def test_invalid_or_missing_profile_falls_back_to_high(self, monkeypatch):
        self._patch_profile(monkeypatch, None)
        assert cc.GOVERNOR.resolve_profile() == "high"
        self._patch_profile(monkeypatch, "turbo")
        assert cc.GOVERNOR.resolve_profile() == "high"

    def test_explicit_profile_argument(self):
        assert cc.scale_workers(6, profile="medium") == 3
        assert cc.scale_workers(6, profile="low") == 1

    def test_batch_worker_count_applies_profile(self, monkeypatch):
        from src.python.fetcher.batch import get_batch_worker_count

        monkeypatch.setattr(
            "src.python.config.get_config",
            lambda: {"batch": {"profile": "medium", "industry_workers": 8, "max_total_workers": 15}},
        )
        monkeypatch.setattr(cc.os, "cpu_count", lambda: 16)
        assert get_batch_worker_count("industry_workers", 8) == 4
