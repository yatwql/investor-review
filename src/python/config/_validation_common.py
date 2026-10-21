"""配置校验共用原语：未提及哨兵、分区取值助手、枚举取值表。

三个校验域（标量 / LLM / 章节）与入口 `validate_config` 共用本模块，
避免各域各存一份哨兵与取值表（哨兵身份必须唯一，否则「显式 null」判定会分叉）。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("invest")


_MISSING = object()


def _section(config: dict, key: str, expected_type: type, warn_msg: str, issues: int = 0) -> tuple[Any, int]:
    """读取配置段，校验类型。"""
    val = config.get(key)
    if val is None:
        return _MISSING, issues
    if not isinstance(val, expected_type):
        logger.warning("config.json %s = %r 不是 %s，%s", key, val, expected_type.__name__, warn_msg)
        return _MISSING, issues + 1
    return val, issues


_FETCH_MODES = frozenset({"off", "prompt", "auto"})  # history.fetch_mode 合法取值
