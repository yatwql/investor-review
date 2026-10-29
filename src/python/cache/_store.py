"""缓存引擎 — 核心存取子模块。

职责：缓存读取（get）、写入（set）、删除（clear）三个核心公开 API。
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
import threading
import time
from typing import Any

from ._io import _read_cache_data, _write_atomic
from ._paths import _GZIP_SUFFIX, _GZIP_THRESHOLD, _cache_path
from ._stats import _record_cache_hit, _record_cache_miss

logger = logging.getLogger("invest")

_cache_lock = threading.Lock()

# 命中/写入的 DEBUG 追踪按 key **每进程首见一次**：同一 key 反复命中是常态
# （实测单周 1.8 万行），全量逐条记录只会挤掉真正有用的日志；命中率汇总另有
# `_stats` 计数与报告「缓存命中率」行，追踪粒度不受影响。
_log_seen: set[str] = set()
_log_seen_lock = threading.Lock()


def _debug_once(kind: str, key: str, *args: Any) -> None:
    """同一 (kind, key) 每进程只记一条 DEBUG。"""
    marker = f"{kind}:{key}"
    with _log_seen_lock:
        if marker in _log_seen:
            return
        _log_seen.add(marker)
    # 带 age/max 实参的（命中/过期）才附时间窗后缀；无实参的（缺文件）只打键名。
    template = f"{kind}: %s" + (" (age=%.1fs, max=%.1fs)" if args else "")
    logger.debug(template, key, *args)


def reset_debug_log_state() -> None:
    """清空 DEBUG 首见记录（测试与长驻进程手动复位用）。"""
    with _log_seen_lock:
        _log_seen.clear()


def get(key: str, max_age_seconds: float, *, record_stats: bool = True) -> Any | None:
    """读取缓存，过期或不存在时返回 None。

    Args:
        key: 缓存键名（对应文件名，不含扩展名）
        max_age_seconds: 最大有效期（秒）
        record_stats: 是否计入全局命中率统计。**负缓存探测器传 False**——
            「负缓存里没有这条记录」是正常预期（说明该缺失不存在），把它记成
            缓存未命中会让命中率与未命中前缀分布失真（实测 7~13 次/轮），
            并误触发「同前缀未命中 ≥N 次」告警。负缓存自身命中另有
            `NegativeCache` 计数与报告级汇总。

    Returns:
        缓存的数据（反序列化后的 Python 对象），过期/不存在返回 None
    """
    path = _cache_path(key)
    gz_path = path + _GZIP_SUFFIX

    # 优先读取 .json.gz，不存在则回退到 .json
    for fpath in (gz_path, path):
        data = _read_cache_data(fpath, key)
        if data is None:
            continue
        if not isinstance(data, dict):
            # 顶层非对象的载荷（如 `[]` / 标量）视为损坏：后续按 `_ts` 判定会抛
            # AttributeError，而缓存的契约是「坏了就当没缓存」，不得中断调用链
            logger.warning("缓存 %s 载荷形状非法（%s），删除后按未命中处理", key, type(data).__name__)
            try:
                os.remove(fpath)
            except OSError:
                pass
            if record_stats:
                _record_cache_miss(key)
            return None

        timestamp = data.get("_ts", 0)
        age = time.time() - timestamp
        if age > max_age_seconds:
            _debug_once("缓存已过期", key, age, max_age_seconds)
            if record_stats:
                _record_cache_miss(key)
            return None

        _debug_once("缓存命中", key, age, max_age_seconds)
        if record_stats:
            _record_cache_hit()
        return data.get("_data")

    # 文件不存在与「读失败」在此合流：逐键明细只到 DEBUG——运行收尾的
    # `_stats.log_cache_summary()` 以一行 INFO 给出命中率与未命中前缀分布，
    # 逐键刷屏（真实运行占日志 10%~30%）不再占用 INFO 通道。
    _debug_once("缓存未命中（无此缓存文件）", key)
    if record_stats:
        _record_cache_miss(key)
    return None


def set(key: str, data: Any) -> None:
    """写入缓存。使用临时文件 + 原子替换保证线程安全。

    Args:
        key: 缓存键名
        data: 任意可 JSON 序列化的数据
    """
    path = _cache_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    payload = {"_ts": time.time(), "_data": data}
    try:
        json_str = json.dumps(payload, ensure_ascii=False, indent=2)
        raw_bytes = json_str.encode("utf-8")
        use_gzip = len(raw_bytes) > _GZIP_THRESHOLD
        final_path = path + _GZIP_SUFFIX if use_gzip else path
    except (TypeError, ValueError, OverflowError):
        logger.warning("缓存序列化失败 %s: 数据无法 JSON 序列化", key)
        return

    # 先写临时文件，再 os.replace 原子替换，防止并发读取时读到不完整的 JSON
    try:
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    except OSError:
        # tempfile.mkstemp 失败（如磁盘满、权限不足），直接返回
        logger.warning("缓存写入失败 %s: 无法创建临时文件", key)
        return

    try:
        _write_atomic(fd, tmp_path, final_path, path, json_str, raw_bytes, use_gzip)
        _debug_once("缓存已写入", key)
    except FileNotFoundError:
        # 目录可能在 makedirs 后被外部删除，重试一次
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd2, tmp_path2 = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
            try:
                _write_atomic(fd2, tmp_path2, final_path, path, json_str, raw_bytes, use_gzip)
                _debug_once("缓存已写入(重试成功)", key)
            except OSError as e2:
                logger.warning("缓存写入失败(重试后) %s: %s", key, e2)
                with contextlib.suppress(OSError):
                    os.remove(tmp_path2)
        except OSError as e2:
            logger.warning("缓存写入失败(重试后) %s: %s", key, e2)
    except OSError as e:
        logger.warning("缓存写入失败 %s: %s", key, e)
        with contextlib.suppress(OSError):
            os.remove(tmp_path)


def clear(key: str) -> None:
    """删除指定缓存文件（同时处理 .json 和 .json.gz）。"""
    with _cache_lock:
        path = _cache_path(key)
        gz_path = path + _GZIP_SUFFIX
        for p in (path, gz_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
                    logger.debug("缓存已清除: %s", key)
            except OSError as e:  # noqa: PERF203
                logger.warning("缓存清除失败 %s: %s", key, e)
