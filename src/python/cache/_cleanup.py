"""缓存引擎 — 过期清理子模块。

职责：过期缓存扫描、清理、预览。
"""

from __future__ import annotations

import logging
import os
import time

from src.python.core.registry import get_exact_type_map, get_prefix_type_map

from ._io import _read_cache_data
from ._paths import _CACHE_DIR, _CACHE_KEY_VERSION
from ._store import _cache_lock
from ._ttl import get_ttl

logger = logging.getLogger("invest")


def _fmt_span(seconds: float) -> str:
    """时长自适应单位（<60s 用 s、<60min 用 min、其余 h）。

    盘中 price 类 TTL 为 30s（market_hour_ttl），统一按小时 двух位小数会印成
    `ttl=0.0h`，配 `age=0.1h` 读起来像配置错误（实测日志复现）。
    """
    value = max(0.0, float(seconds))
    if value < 60:
        return f"{value:.1f}s"
    if value < 3600:
        return f"{value / 60:.1f}min"
    return f"{value / 3600:.1f}h"


def _process_cache_file(
    fname: str,
    dry_run: bool,
    prefix_type_map: dict[str, str],
    exact_map: dict[str, str],
) -> int:
    """处理单个缓存文件：判断类型、检查过期、删除。returns 是否删除（0/1）。"""
    if fname.endswith(".json.gz"):
        fkey = fname[:-8]
    elif fname.endswith(".json"):
        fkey = fname[:-5]
    else:
        return 0
    fpath = os.path.join(_CACHE_DIR, fname)

    # 文件名带缓存键版本戳（`{key}_v{N}.json`），逻辑键是读侧使用的那个串：
    # 剥掉版本戳后才能命中精确键映射表（精确键在注册表里按逻辑键登记）。
    logical_key = fkey
    if fkey.endswith(f"_{_CACHE_KEY_VERSION}"):
        logical_key = fkey[: -(len(_CACHE_KEY_VERSION) + 1)]

    data_type = "default"
    if logical_key in exact_map:
        data_type = exact_map[logical_key]
    else:
        for pfx, dtype in prefix_type_map.items():
            if logical_key.startswith(pfx):
                data_type = dtype
                break

    ttl = get_ttl(data_type)
    payload = _read_cache_data(fpath, fkey, dry_run=dry_run)
    if payload is None:
        return 1  # 损坏也算清理

    raw_ts = payload.get("_ts")
    try:
        ts = float(raw_ts) if raw_ts is not None else 0.0
    except (TypeError, ValueError):
        ts = 0.0
    if ts <= 0:
        # 非缓存引擎写入的文件（无 `_ts` 包封）：不能拿 epoch 当写入时间，否则算出
        # 「57 年陈货」每轮当过期删（实测脚本自管的性能缓存就因此白做）。
        # 属托管边界之外，跳过 TTL 判定，只留 DEBUG 痕迹，不打 INFO 刷屏。
        logger.debug("缓存清理跳过（无 _ts 包封，非缓存引擎托管）: %s", fname)
        return 0

    now = time.time()
    age = now - ts
    if age <= ttl:
        return 0

    if not dry_run:
        try:
            os.remove(fpath)
        except OSError:
            return 0
    # 逐文件明细降 DEBUG：单日数百行 INFO 只会把真正的告警冲走（汇总见 cleanup_expired）。
    logger.debug(
        "缓存清理%s %s (age=%s > ttl=%s)",
        "预览" if dry_run else "删除",
        fname,
        _fmt_span(age),
        _fmt_span(ttl),
    )
    return 1


def cleanup_expired(dry_run: bool = False) -> int:
    """扫描缓存目录，删除已过期的缓存文件。

    每个缓存文件内含 _ts 时间戳，读取后与当前时间比对，
    根据文件名的类型前缀查表确定 TTL，过期则删除。
    同时处理 .json 和 .json.gz 文件。

    Args:
        dry_run: True 时仅打印不删除；False 时实际删除

    Returns:
        已删除（或待删除）的文件数
    """
    with _cache_lock:
        prefix_type_map: dict[str, str] = get_prefix_type_map()
        exact_map: dict[str, str] = get_exact_type_map()

        if not os.path.isdir(_CACHE_DIR):
            logger.info("缓存目录不存在，跳过清理")
            return 0

        removed = 0
        free_bytes = 0
        for fname in sorted(os.listdir(_CACHE_DIR)):
            fpath = os.path.join(_CACHE_DIR, fname)
            try:
                size = os.path.getsize(fpath)
            except OSError:
                size = 0
            hit = _process_cache_file(fname, dry_run, prefix_type_map, exact_map)
            removed += hit
            free_bytes += size if hit else 0

        label = "预览" if dry_run else "完成"
        if removed:
            logger.info(
                "缓存清理%s: 共 %d 个文件（释放 %.1f KB）——逐文件明细见 DEBUG",
                label,
                removed,
                free_bytes / 1024,
            )
        else:
            logger.info("缓存清理%s: 共 0 个文件", label)
        return removed


def auto_cleanup_expired() -> int:
    """生成等入口的静默自动清理（尽力而为）。

    包装 :func:`cleanup_expired`：任何异常一律吞掉（记 debug 日志）并返回 0，
    保证无人值守调用方（CLI 定时任务等）不会因清理失败而影响主流程。

    Returns:
        已删除的过期文件数；清理失败时为 0
    """
    try:
        return cleanup_expired(dry_run=False)
    except Exception:  # noqa: BLE001 —— 自动清理绝不影响调用方
        logger.debug("过期缓存自动清理失败（忽略，不影响主流程）", exc_info=True)
        return 0


_SENSITIVE_PREFIXES: tuple[str, ...] = (
    "holding_",
    "penetration_",
    "fund_hold_",
    "fund_manager_",
)


def clean_sensitive(older_than_days: int = 90, dry_run: bool = False) -> int:
    """清理超过指定天数的敏感缓存文件。

    敏感缓存包括可能包含持仓明细的数据：
      - holding_* (持仓数据)
      - penetration_* (穿透数据)
      - fund_hold_* (基金持仓)
      - fund_manager_* (基金经理 — 可能含持仓)

    Args:
        older_than_days: 超过此天数的缓存将被清理
        dry_run: True 时仅打印不删除

    Returns:
        已删除（或待删除）的文件数
    """
    with _cache_lock:
        if not os.path.isdir(_CACHE_DIR):
            logger.info("缓存目录不存在，跳过敏感缓存清理")
            return 0

        older_than_secs = older_than_days * 86400
        now = time.time()
        removed = 0

        for fname in sorted(os.listdir(_CACHE_DIR)):
            if not any(fname.startswith(pfx) for pfx in _SENSITIVE_PREFIXES):
                continue

            if fname.endswith(".json.gz"):
                fkey = fname[:-8]
            elif fname.endswith(".json"):
                fkey = fname[:-5]
            else:
                continue

            fpath = os.path.join(_CACHE_DIR, fname)
            payload = _read_cache_data(fpath, fkey, dry_run=dry_run)
            if payload is None:
                # 损坏文件已在 _read_cache_data 中处理（dry_run=False 时删除）
                removed += 1
                continue

            ts = payload.get("_ts", 0)
            age = now - ts
            if age <= older_than_secs:
                continue

            if not dry_run:
                try:
                    os.remove(fpath)
                except OSError:
                    continue
            logger.info(
                "敏感缓存清理: %s %s (age=%.1fd > %dd)",
                "预览" if dry_run else "删除",
                fname,
                age / 86400,
                older_than_days,
            )
            removed += 1

        logger.info("敏感缓存清理%s: 共 %d 个文件", "预览" if dry_run else "完成", removed)
        return removed
