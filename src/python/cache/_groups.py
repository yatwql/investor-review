"""缓存引擎 — 组管理子模块。

职责：按前缀/组批量清除缓存。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable

from src.python.core.registry import get_cache_registry

from ._paths import _CACHE_DIR, _GZIP_SUFFIX, _cache_path, cache_key_from_file_name
from ._store import _cache_lock, clear

logger = logging.getLogger("invest")


def clear_by_prefix(key_prefix: str, exclude_keys: Iterable[str] = ()) -> int:
    """清除所有键名以指定前缀开头的缓存文件（同时处理 .json 和 .json.gz）。

    Args:
        key_prefix: 缓存键名前缀，如 ``"fund_perf_"``
        exclude_keys: 不清的逻辑缓存键名（剥掉版本戳后比对）。前缀是粗粒度选择器，
            同前缀下可有**不属于本域语义**的键（如 ``fund_manager_snapshot`` 落在
            ``fund_manager_`` 前缀里但属跟踪基线）——这类键由调用方点名保留。

    Returns:
        已清除的文件数量
    """
    excluded = frozenset(exclude_keys)
    with _cache_lock:
        count = 0
        if not os.path.isdir(_CACHE_DIR):
            return 0
        for fname in os.listdir(_CACHE_DIR):
            # 识别 .json 和 .json.gz
            if fname.endswith(".json.gz"):
                fkey = fname[:-8]  # 去掉 .json.gz
            elif fname.endswith(".json"):
                fkey = fname[:-5]  # 去掉 .json
            else:
                continue
            if fkey.startswith(key_prefix):
                if excluded and cache_key_from_file_name(fname) in excluded:
                    logger.debug("缓存清除跳过（保留键）: %s", fkey)
                    continue
                try:
                    os.remove(os.path.join(_CACHE_DIR, fname))
                    count += 1
                    logger.debug("缓存已清除: %s", fkey)
                except OSError as e:
                    logger.warning("缓存清除失败 %s: %s", fkey, e)
    return count


def clear_by_group(
    group_name: str, only: Iterable[str] | None = None, exclude_keys: Iterable[str] = ()
) -> dict[str, int]:
    """清除指定缓存组的所有缓存文件。

    从缓存域注册表（含注册表外缓存专属项）自动推导该组的缓存前缀与精确键名，
    逐一调用 clear_by_prefix / clear。

    Args:
        group_name: 缓存组名，对应 DataModuleDef.cache_groups 中的值
        only: 只清这些缓存键前缀/精确键名所属的模块；None（默认）清整组。
            用于「刷新基础缓存」这类**只回填部分域**的流程：整组清空会把本流程
            不回填的域（财报索引/正文、财务指标等）一并作废，下一次出报告全部
            回源——实测一次「刷新基础缓存」后紧接的报告多付 267 次请求、墙钟翻倍。
        exclude_keys: 点名保留的逻辑缓存键名（见 ``clear_by_prefix``）——用于
            「只清不重建」的域里夹带的跟踪基线：清掉基线会让下一次报告退化成首检。

    Returns:
        {模块名: 清除的文件数} 字典，方便日志/UI 展示
    """
    allowed = set(only) if only is not None else None
    excluded = frozenset(exclude_keys)
    result: dict[str, int] = {}
    for m in get_cache_registry():
        if group_name not in m.cache_groups:
            continue
        if allowed is not None and not (allowed & (set(m.cache_prefixes) | set(m.exact_cache_keys))):
            continue
        total = 0
        for prefix in m.cache_prefixes:
            total += clear_by_prefix(prefix, exclude_keys=excluded)
        for exact_key in m.exact_cache_keys:
            if exact_key in excluded:
                continue
            path = _cache_path(exact_key)
            gz_path = path + _GZIP_SUFFIX
            file_exists = os.path.exists(path) or os.path.exists(gz_path)
            clear(exact_key)
            if file_exists:
                total += 1
        if total > 0:
            result[m.name] = total
    return result
