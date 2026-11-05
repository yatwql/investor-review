"""缓存测试共享夹具 — 写「指定写入时刻 / 指定年龄」的缓存载荷。

三个缓存测试文件（TTL 对齐矩阵、业务矩阵、版本戳与清理）都需要构造带 `_ts` 的缓存
文件：清理侧要按**写入时刻**判定「盘中快照 vs 收盘后数据」，因此不能只用相对年龄，
必须能精确指定时间戳。这类样板曾各文件一份，改判定口径时要同步改三处，故收敛到本模块。

约定：
  - 只做文件落地，不碰模块级 `_CACHE_DIR`（各用例自带的 fixture 负责重定向）。
  - 文件名自动补当前缓存键版本戳（`{key}_v{N}.json`），与生产读写路径一致。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from src.python.core.constants import BEIJING_TZ


def _payload_path(cache_dir, key: str) -> Path:
    from src.python.cache._paths import _CACHE_KEY_VERSION

    return Path(cache_dir) / f"{key}_{_CACHE_KEY_VERSION}.json"


def write_cache(cache_dir, key: str, age_seconds: float) -> None:
    """写入一份「距今 age_seconds 秒」的缓存（按当前时刻倒推写入时刻）。"""
    write_cache_at(cache_dir, key, time.time() - age_seconds)


def write_cache_at(cache_dir, key: str, moment: float) -> None:
    """写入一份**指定写入时刻**的缓存（`moment` 为 Unix 时间戳）。

    用于「盘中快照（10:05 写入）盘后应被回收、收盘后（15:30 写入）应保留」这类判定，
    相对年龄无法表达该语义。
    """
    payload = {"_ts": moment, "_data": {"v": 1}}
    _payload_path(cache_dir, key).write_text(json.dumps(payload), encoding="utf-8")


def today_at(hour: int, minute: int) -> float:
    """今天（北京时间）某时某刻的时间戳。"""
    now = datetime.now(BEIJING_TZ)
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()


def pre_open_ts() -> float:
    """今天盘前 08:00（北京时间）的时间戳：非交易时段，清理侧按静态 TTL 判。"""
    return today_at(8, 0)
