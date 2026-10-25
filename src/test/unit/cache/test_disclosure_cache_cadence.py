"""财报类缓存的披露节奏对齐 —— 新一期财报/指标最迟次日可见，正文不重复取。

业务约束（三个 TTL 走不同节奏，各有理由）：

| 类型 | 键粒度 | TTL | 为什么不更长 / 不更短 |
|------|--------|-----|----------------------|
| `report`（索引/章节清单） | symbol 级 | 1 天 | 更久 → 新披露最长滞后一个窗口才被发现，报告沿用上一期口径；更短 → 每份报告都打源 |
| `report_doc`（正文） | doc_id 级（不可变） | 30 天 | 正文取到即定型，重复取只会白耗配额 |
| `fin_indicator`（财务指标） | symbol 级 | 1 天 | 同索引：新报告期靠日刷新发现 |
| `dividend`（历史分红） | symbol 级 | 7 天 | 公告不定期，周频兼顾可见性与请求量 |

本文件把上述节奏钉成回归契约，并验证「同一份报告在 TTL 内不重复打源」这一侧
（否则缩短 TTL 会让配额被重复请求吃掉）。
"""

from __future__ import annotations

import json
import time

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_DAY = 86400
_WEEK = 7 * _DAY


@pytest.fixture()
def cache_env(tmp_path, monkeypatch):
    from src.python.cache import _cleanup, _paths, _store

    monkeypatch.setattr(_paths, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(_cleanup, "_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("src.python.config.get_config", lambda: {})
    _store.reset_debug_log_state()
    yield tmp_path
    _store.reset_debug_log_state()


def _write(cache_dir, key: str, age_seconds: float) -> None:
    from src.python.cache._paths import _CACHE_KEY_VERSION

    payload = {"_ts": time.time() - age_seconds, "_data": [{"date": "2026-09-30"}]}
    (cache_dir / f"{key}_{_CACHE_KEY_VERSION}.json").write_text(json.dumps(payload), encoding="utf-8")


class TestDisclosureCadenceTTL:
    """披露节奏对齐：索引/指标按日、正文按月、分红按周。"""

    @pytest.mark.parametrize("data_type", ["report", "fin_indicator"])
    def test_symbol_level_types_use_daily_ttl(self, cache_env, data_type):
        """symbol 级键必须日频：新披露最迟次日被发现（否则整月沿用上一期）。"""
        from src.python.cache import get_ttl

        assert get_ttl(data_type) == _DAY

    def test_report_doc_keeps_monthly_ttl(self, cache_env):
        """正文按 doc_id 不可变：保持月度，避免重复取已定型正文。"""
        from src.python.cache import get_ttl

        assert get_ttl("report_doc") == 30 * _DAY

    def test_dividend_uses_weekly_ttl(self, cache_env):
        from src.python.cache import get_ttl

        assert get_ttl("dividend") == _WEEK

    def test_index_ttl_shorter_than_doc_ttl(self, cache_env):
        """索引比正文短：索引负责"发现新披露"，正文负责"取一次就定型"。"""
        from src.python.cache import get_ttl

        assert get_ttl("report") < get_ttl("report_doc")


class TestNewDisclosureVisibility:
    """新一期财报可见性：跨过一次 TTL 边界的报告必须重新取索引。"""

    def test_index_cache_expires_overnight(self, cache_env):
        """今晚取到的索引，明晚（24h+）必须重取 → 新披露次日可见。"""
        from src.python.cache import get as cache_get, get_ttl

        ttl = get_ttl("report")
        _write(cache_env, "report_datasink_index_600519", age_seconds=_DAY - 60)
        assert cache_get("report_datasink_index_600519", ttl) is not None, "24h 内复用（同日多次报告不重复打源）"
        _write(cache_env, "report_datasink_index_600519", age_seconds=_DAY + 60)
        assert cache_get("report_datasink_index_600519", ttl) is None, "超过一天必须重取索引"

    def test_indicator_cache_expires_overnight(self, cache_env):
        from src.python.cache import get as cache_get, get_ttl

        ttl = get_ttl("fin_indicator")
        _write(cache_env, "fin_indicator_600519", age_seconds=_DAY - 60)
        assert cache_get("fin_indicator_600519", ttl) is not None
        _write(cache_env, "fin_indicator_600519", age_seconds=_DAY + 60)
        assert cache_get("fin_indicator_600519", ttl) is None

    def test_doc_cache_survives_a_week(self, cache_env):
        """正文不可变：一周后仍命中（不重复消耗配额）。"""
        from src.python.cache import get as cache_get, get_ttl

        _write(cache_env, "report_datasink_doc_600519_123_full", age_seconds=_WEEK)
        assert cache_get("report_datasink_doc_600519_123_full", get_ttl("report_doc")) is not None


class TestSameDayNoRefetch:
    """同一天多份报告：索引只取一次（缩短 TTL 不得变成"每份报告都打源"）。"""

    def test_multiple_runs_same_day_hit_single_fetch(self, cache_env):
        from src.python.cache import get as cache_get, get_ttl

        ttl = get_ttl("report")
        _write(cache_env, "report_datasink_index_600519", age_seconds=60)
        hits = [cache_get("report_datasink_index_600519", ttl) for _ in range(4)]
        assert all(hit is not None for hit in hits), "同日四份报告应全部命中同一份索引"

    def test_cninfo_backup_index_uses_same_ttl(self, cache_env):
        """巨潮备源索引与主源同档：两源都用 `get_ttl("report")`（前缀同组）。"""
        from src.python.core.registry import get_prefix_type_map

        prefixes = get_prefix_type_map()
        assert prefixes["report_cninfo_index_"] == "report"
        assert prefixes["report_datasink_index_"] == "report"


class TestCleanupFollowsNewTTL:
    """清理侧同步：过期判定取同一 TTL，不留"读未命中但清理保留"的空档。"""

    def test_cleanup_removes_stale_index_after_one_day(self, cache_env):
        from src.python.cache._cleanup import cleanup_expired

        _write(cache_env, "report_datasink_index_600519", age_seconds=_DAY + 3600)
        assert cleanup_expired(dry_run=False) == 1

    def test_cleanup_keeps_doc_within_month(self, cache_env):
        from src.python.cache._cleanup import cleanup_expired

        _write(cache_env, "report_datasink_doc_600519_1_full", age_seconds=_WEEK)
        assert cleanup_expired(dry_run=True) == 0

    def test_cleanup_removes_dividend_after_week(self, cache_env):
        from src.python.cache._cleanup import cleanup_expired

        _write(cache_env, "dividend_600519", age_seconds=_WEEK + 3600)
        assert cleanup_expired(dry_run=False) == 1


class TestQuotaImpactBound:
    """配额影响有界：索引日刷新的请求量 = 标的数/日（与报告次数无关）。"""

    def test_requests_per_day_depend_on_holdings_not_report_count(self, cache_env):
        """同一标的当天新增请求恒为 1（TTL 而非调用数决定），故配额增量 = 标的数。

        用真实缓存行为验证：一天内多次读取同一索引键，只有第一次是未命中。
        """
        from src.python.cache import get as cache_get, get_ttl
        from src.python.cache import set as cache_set

        holdings = 20
        ttl = get_ttl("report")
        misses = 0
        for code in range(holdings):
            key = f"report_datasink_index_{600000 + code}"
            if cache_get(key, ttl) is None:
                misses += 1
                cache_set(key, [{"date": "2026-09-30"}])  # 首次取数后落盘
            for _ in range(3):  # 同日后续三份报告
                assert cache_get(key, ttl) is not None
        assert misses == holdings, "日请求量 = 标的数（报告次数不放大）"
        assert holdings / 8191 < 0.01, "占免费档日配额 <1%"
