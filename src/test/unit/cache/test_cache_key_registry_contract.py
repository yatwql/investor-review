"""缓存键形状 ↔ 注册表覆盖契约 —— 阻止「键名漂移 → 落 default 日档被误删」。

背景（两类实测缺陷同根因）：

- 跟踪基线快照 `fund_manager_snapshot` 落在 `fund_manager_` 前缀里，按上报域 24h 裁，
  报告生成入口每次先自动清理 → 相隔一天的报告之间基线消失，永远显示「首次运行」；
- 增量历史缓存曾拼成 `history_history_stock_*`（多一层 `history_`），既不命中
  `history_stock_` 前缀也不命中精确键 → 落进 default 日档（24h），K 线文件与
  `_correction_streak` 计数每天被删，纠偏冷却永远累计不到阈值。

守卫：**任何键构造器产出的键都必须命中注册表声明的类型**（前缀或精确键），
不得落 `default`；生命周期至少覆盖读侧需要的窗口。
"""

from __future__ import annotations

import pytest

from src.python.core.constants import CACHE_NEAR_PERMANENT, CACHE_WEEKLY
from src.python.core.data_registry import _CACHE_ONLY_REGISTRY, TRACKING_SNAPSHOT_KEYS, get_exact_ttl_map
from src.python.core.registry import get_cache_registry

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_MODULES = list(get_cache_registry()) + list(_CACHE_ONLY_REGISTRY)
_EXACT_TYPES = {key: m.data_type for m in _MODULES for key in m.exact_cache_keys}
_PREFIX_TYPES = {p: m.data_type for m in _MODULES for p in m.cache_prefixes}


def _data_type_of(key: str) -> str | None:
    """键 → 注册表数据类型；None = 未登记（清理器按 default 日档裁）。"""
    if key in _EXACT_TYPES:
        return _EXACT_TYPES[key]
    for prefix in sorted(_PREFIX_TYPES, key=len, reverse=True):
        if key.startswith(prefix):
            return _PREFIX_TYPES[prefix]
    return None


_HISTORY_CHAINS = ["history_stock", "history_index", "history_index_us", "history_fund_otc"]

#: chain → 注册表类型（US 指数没有独立条目，共用 `history_index` 的 `history_index_` 前缀）
_REGISTERED_TYPE = {"history_index_us": "history_index"}


class TestHistoryKeyFamily:
    """增量历史缓存键必须是唯一构造器的产物，且命中注册表前缀。"""

    @pytest.mark.parametrize("chain", _HISTORY_CHAINS)
    def test_chain_key_resolves_to_registered_type(self, chain):
        from src.python.fetcher.chain_incremental import history_cache_key

        key = history_cache_key(chain, "600519")
        assert _data_type_of(key) is not None, f"{key} 未命中注册表前缀 → 按 default 日档清理"
        assert _data_type_of(key) == _REGISTERED_TYPE.get(chain, chain)

    @pytest.mark.parametrize("chain", _HISTORY_CHAINS)
    def test_correction_streak_key_stays_in_family(self, chain):
        """纠偏计数键随主键同族：被删会让「连续检出→跳过全量刷新」冷却失效。"""
        from src.python.fetcher.chain_incremental import _correction_streak_key, history_cache_key

        key = _correction_streak_key(history_cache_key(chain, "600519"))
        assert _data_type_of(key) == _REGISTERED_TYPE.get(chain, chain)

    def test_history_cleanup_window_covers_read_ttl(self):
        """清理窗口不短于读侧窗口（读侧按 CACHE_WEEKLY 取增量缓存）。"""
        from src.python.cache._ttl import get_cleanup_ttl
        from src.python.fetcher.chain_incremental import history_cache_key

        for chain in _HISTORY_CHAINS:
            key = history_cache_key(chain, "600519")
            data_type = _data_type_of(key)
            assert data_type is not None
            assert get_cleanup_ttl(data_type) >= CACHE_WEEKLY, f"{chain} 清理窗口短于读侧 TTL"


class TestBaselineAndStateKeys:
    """基线与运行状态键必须显式登记（不得靠前缀默认值兜底）。"""

    @pytest.mark.parametrize("key", sorted(TRACKING_SNAPSHOT_KEYS) + ["market_hours", "holdings_tracking"])
    def test_key_is_registered(self, key):
        assert _data_type_of(key) is not None, f"{key} 未登记 → 清理按 default 日档裁"

    @pytest.mark.parametrize("key", sorted(TRACKING_SNAPSHOT_KEYS))
    def test_snapshot_has_own_ttl_outside_domain(self, key):
        """跟踪基线必须有独立精确键 TTL，不随上报域（日档）裁。"""
        exact = get_exact_ttl_map()
        assert exact[key] == CACHE_NEAR_PERMANENT
