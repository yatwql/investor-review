"""缓存引擎 — 命中率统计 + 目录统计子模块。

职责：缓存命中/未命中计数、命中率查询、目录级统计（文件数/大小/前缀分组）。
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from ._paths import _CACHE_DIR

logger = logging.getLogger("invest")

# ── 缓存命中率统计（线程安全） ───────────────────────────────
_cache_stats_lock = threading.Lock()
_cache_hits: int = 0
_cache_misses: int = 0
#: 未命中按键前缀分桶：逐键明细只到 DEBUG，运行收尾用这一份汇总代替逐条 INFO。
_cache_miss_prefixes: dict[str, int] = {}
#: 未命中键名计数（有界）——「同前缀未命中 ≥N 次」时列出具体键，否则看到告警还得
#: 自己翻 DEBUG 才知道是哪几个。
_cache_miss_keys: dict[str, int] = {}
_MISS_KEY_TRACK_LIMIT = 500

#: 同一**键**在一次运行内未命中达到该次数 → 视为异常信号（每轮重取/缓存键失效），
#: 单独升为 WARNING。判据取「同键」而非「同前缀」：冷启动时一批新资产各取一次
#: （如 20 只基金各未命中 1 次）属正常首次取数，按前缀累计会把它误报成故障。
_SUSPICIOUS_KEY_MISSES = 3

#: 负缓存与纠偏计数探测键：未命中即「尚无该记录」，属预期缺失（命中反而是坏消息），
#: 不计入未命中分桶——否则每轮都会把 `report_symbol_miss_*` / `*_correction_streak`
#: 这类正常探测报成「同前缀未命中」。
_PROBE_KEY_MARKERS = ("_miss_", "_correction_streak")


def is_probe_key(key: str) -> bool:
    """该键是否为「预期缺失」探测键（负缓存查询 / 纠偏计数读取）。"""
    return any(marker in key for marker in _PROBE_KEY_MARKERS)


def _key_prefix(key: str) -> str:
    """缓存键 → 统计前缀（取前两段：``llm_expert_review_…`` → ``llm_expert_review``）。"""
    segments = [seg for seg in key.split("_") if seg]
    return "_".join(segments[:2]) if len(segments) >= 2 else (segments[0] if segments else "other")


def _record_cache_hit() -> None:
    """记录一次缓存命中（线程安全）。"""
    global _cache_hits
    with _cache_stats_lock:
        _cache_hits += 1


def _record_cache_miss(key: str = "") -> None:
    """记录一次缓存未命中（线程安全，可按 key 前缀分桶）。"""
    global _cache_misses
    with _cache_stats_lock:
        _cache_misses += 1
        if key and not is_probe_key(key):
            prefix = _key_prefix(key)
            _cache_miss_prefixes[prefix] = _cache_miss_prefixes.get(prefix, 0) + 1
            if len(_cache_miss_keys) < _MISS_KEY_TRACK_LIMIT:
                _cache_miss_keys[key] = _cache_miss_keys.get(key, 0) + 1


def get_cache_hit_rate() -> dict[str, int | float]:
    """返回缓存命中率统计。

    Returns:
        {hits, misses, total, rate}
        rate 为 0.0~1.0 的浮点数，无可观测数据时返回 0.0
    """
    with _cache_stats_lock:
        hits = _cache_hits
        misses = _cache_misses
    total = hits + misses
    rate = round(hits / total, 4) if total > 0 else 0.0
    return {"hits": hits, "misses": misses, "total": total, "rate": rate}


def reset_cache_stats() -> None:
    """重置缓存命中率计数器与未命中前缀分布。"""
    global _cache_hits, _cache_misses
    with _cache_stats_lock:
        _cache_hits = 0
        _cache_misses = 0
        _cache_miss_prefixes.clear()
        _cache_miss_keys.clear()


def get_cache_miss_prefixes() -> dict[str, int]:
    """返回未命中按键前缀的分布快照（副本）。"""
    with _cache_stats_lock:
        return dict(_cache_miss_prefixes)


def log_cache_summary(top: int = 5, salts_note: str = "") -> str:
    """以**一行 INFO** 汇总本次运行的缓存命中情况，取代逐键未命中日志。

    逐键「缓存未命中（无此缓存文件）: <key>」在真实运行里占日志的 10%~30%
    （逐文档 × 逐缓存键刷屏），但单条几乎不携带信息——有价值的是「命中率」与
    「哪一类键在反复未命中」。故逐键明细降到 DEBUG（排查时调级别即可），INFO 只留：
    命中/未命中总量 + 未命中最多前缀 Top N；**同一键**未命中达
    `_SUSPICIOUS_KEY_MISSES` 次时另打一条 WARNING（那是缓存键设计或 TTL 出问题的信号，
    如「每份报告都为同一文档重探章节清单」）。负缓存探测键（`_miss_` / `_correction_streak`）
    不计入分桶——它们未命中即「尚无该记录」，属预期缺失。

    Args:
        top: 摘要里列出的前缀数量。
        salts_note: 追加到汇总行尾的补充说明（缓存键版本盐）。**由调用方传入**——
            `cache` 是基础层，不得反向 import `llm` 取版本号（分层纪律：只能依赖
            下层与贯穿层）；报告层为本函数的调用方，版本信息由它组织。

    Returns:
        摘要文本（无可观测数据时为空串）。
    """
    stats = get_cache_hit_rate()
    if not stats["total"]:
        return ""
    prefixes = get_cache_miss_prefixes()
    ranked = sorted(prefixes.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
    detail = "、".join(f"{prefix} {count}" for prefix, count in ranked) or "无"
    _note = f"；{salts_note}" if salts_note else ""
    logger.info(
        "[cache] 本次命中 %d / 未命中 %d（命中率 %.0f%%）；未命中前缀 Top%d：%s%s",
        stats["hits"],
        stats["misses"],
        stats["rate"] * 100,
        len(ranked),
        detail,
        _note,
    )
    suspicious = sorted(
        ((key, count) for key, count in _cache_miss_keys.items() if count >= _SUSPICIOUS_KEY_MISSES),
        key=lambda kv: (-kv[1], kv[0]),
    )[:5]
    if suspicious:
        logger.warning(
            "[cache] 同键未命中 ≥%d 次（疑似每轮重取或缓存键失效）：%s",
            _SUSPICIOUS_KEY_MISSES,
            "、".join(f"{key}×{count}" for key, count in suspicious),
        )
    return detail


def get_cache_stats() -> dict:
    """统计缓存目录：文件总数、总大小、按前缀分组数量、最大文件 TOP 10。

    同时统计 .json 和 .json.gz 文件。

    Returns:
        {total_files, total_size_bytes, by_prefix: {prefix: count},
         top_by_size: [(key, size_bytes), ...]}
    """
    stats: dict[str, Any] = {
        "total_files": 0,
        "total_size_bytes": 0,
        "by_prefix": {},
        "top_by_size": [],
    }
    if not os.path.isdir(_CACHE_DIR):
        return stats
    _sized_items: list[tuple[str, int]] = []
    try:
        _names = os.listdir(_CACHE_DIR)
    except OSError:
        # isdir 与 listdir 之间目录可能被删/无权限（TOCTOU）：统计是旁路，
        # 取不到就按空目录返回，不向上抛。
        return stats
    for fname in _names:
        if fname.endswith(".json.gz"):
            stem = fname[:-8]  # 去掉 .json.gz
        elif fname.endswith(".json"):
            stem = fname[:-5]  # 去掉 .json
        else:
            continue
        fpath = os.path.join(_CACHE_DIR, fname)
        try:
            size = os.path.getsize(fpath)
            stats["total_files"] += 1
            stats["total_size_bytes"] += size
            prefix = stem.split("_", 1)[0] if "_" in stem else "other"
            stats["by_prefix"][prefix] = stats["by_prefix"].get(prefix, 0) + 1
            _sized_items.append((stem, size))
        except OSError:
            pass
    _sized_items.sort(key=lambda x: -x[1])
    stats["top_by_size"] = _sized_items[:10]
    return stats
