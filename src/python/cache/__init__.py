"""缓存引擎子包 — 提供 get/set/clear 及 TTL 管理等统一接口。"""

import logging

from src.python.core.constants import CACHE_DAILY

from ._cleanup import auto_cleanup_expired, cleanup_expired, clean_sensitive
from ._groups import clear_by_group, clear_by_prefix
from ._paths import (
    _cache_path,
    _GZIP_SUFFIX,
    cache_key_from_file_name,
    check_cache_dir_permissions,
    get_cache_dir,
)
from ._stats import (
    get_cache_hit_rate,
    get_cache_stats,
    reset_cache_stats,
)
from ._store import clear, get, set
from ._ttl import get_cache_age, get_cache_age_by_data_type, get_ttl
from .services.holdings_tracker import (
    check_and_refresh_caches,
    compute_holdings_codes,
    compute_holdings_fingerprint,
)


def get_cache_path(key: str) -> str:
    """缓存键 → 缓存文件路径（公开只读入口，供 core 等到期检查复用）。"""
    return _cache_path(key)


#: 缓存文件 gzip 变体后缀（与 ``get_cache_path`` 配套的公开只读常量）
CACHE_GZIP_SUFFIX = _GZIP_SUFFIX

__all__ = [
    "get",
    "set",
    "clear",
    "get_cache_hit_rate",
    "reset_cache_stats",
    "get_cache_stats",
    "get_ttl",
    "get_cache_age",
    "get_cache_age_by_data_type",
    "cleanup_expired",
    "auto_cleanup_expired",
    "clean_sensitive",
    "clear_by_prefix",
    "clear_by_group",
    "check_and_refresh_caches",
    "compute_holdings_fingerprint",
    "compute_holdings_codes",
    "get_cache_dir",
    "get_cache_path",
    "cache_key_from_file_name",
    "CACHE_GZIP_SUFFIX",
    "check_cache_dir_permissions",
    "CACHE_DAILY",
]


# ── 启动时自动清理过期敏感缓存（静默执行，仅日志记录）──
_logger = logging.getLogger("invest")
_cleaned = 0
try:
    _cleaned = clean_sensitive(older_than_days=90, dry_run=False)
    if _cleaned > 0:
        _logger.info("[cache] 启动清理: 移除 %d 个过期敏感缓存文件", _cleaned)
except Exception:
    _logger.debug("[cache] 启动敏感缓存清理失败（非关键）", exc_info=True)
del _logger, _cleaned
