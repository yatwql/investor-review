"""缓存引擎 — TTL / 缓存年龄子模块。

职责：TTL 查询（交易时段感知）、缓存年龄查询。
"""

from __future__ import annotations

import logging
import time

from src.python.core.constants import CACHE_DAILY
from src.python.core.market_hours import is_market_open as _is_market_open
from src.python.core.registry import get_cache_ttl_defaults, get_market_ttl_map

from ._io import _read_cache_data
from ._paths import _GZIP_SUFFIX, _cache_path

logger = logging.getLogger("invest")

#: 已提示过「盘中 TTL 优先于 cache_ttl」的类型（每类型只提示一次，避免每份报告刷屏）
_INTRADAY_OVERRIDE_NOTIFIED: set[str] = set()


def get_cache_age(key: str) -> float | None:
    """返回缓存数据年龄（秒），无缓存或损坏时返回 None。

    同时检查 .json 和 .json.gz 变体，返回最先找到的有效缓存年龄。

    Args:
        key: 缓存键名

    Returns:
        缓存数据距今的秒数，缓存不存在/损坏时返回 None
    """
    path = _cache_path(key)
    gz_path = path + _GZIP_SUFFIX

    for fpath in (gz_path, path):
        data = _read_cache_data(fpath, key)
        if data is not None:
            ts = data.get("_ts", 0)
            if isinstance(ts, (int, float)) and ts > 0:
                return time.time() - ts
    return None


def get_cache_age_by_data_type(
    data_type: str,
    identifier: str | None = None,
) -> float | None:
    """按 registry 数据类型获取缓存年龄，替换硬编码 get_cache_age() 调用。

    从 registry 查找数据类型的缓存前缀，拼接 identifier 组成完整键名。
    适用于前缀+代码/标识符结构的缓存键（如 ``"index_sh000001"``）。

    特殊处理：
      - ``"profit_forecast"``：缓存键含动态指数指纹，无需 identifier，
        内部委托给 :func:`get_profit_forecast_cache_key` 获取键名。

    Args:
        data_type: registry 中注册的数据类型，如 ``"index"``
        identifier: 拼接在缓存前缀后的标识符，
                    如 ``"sh000001"`` → 完整键名 ``"index_sh000001"``

    Returns:
        缓存年龄（秒），无缓存或类型未注册时返回 None
    """
    # 特殊处理：profit_forecast 使用动态指纹，不走 prefix+identifier 模式
    if data_type == "profit_forecast":
        from src.python.fetcher.akshare import get_profit_forecast_cache_key

        return get_cache_age(get_profit_forecast_cache_key())
    # 标准路径：prefix + identifier
    from src.python.core.registry import get_registry  # 延迟导入避免循环依赖

    for module in get_registry():
        if module.data_type == data_type and identifier is not None and module.cache_prefixes:
            key = f"{module.cache_prefixes[0]}{identifier}"
            return get_cache_age(key)
    return None


def get_ttl(data_type: str) -> float:
    """获取指定数据类型的缓存过期时间（秒）—— **同一类型恒返回同一值**。

    解析顺序（单一来源 + 两种覆盖）：

    1. **盘中敏感类型**（注册表 `DataModuleDef.market_ttl`，价/指 = 30s）且当前处于
       交易时段 → 返回盘中 TTL；数值可被 `config.json → market_hour_ttl` 全局覆盖，
       钳制在 [30, 86400]。
    2. 否则返回静态 TTL：`config.json → cache_ttl.{type}`（正数）优先，未配置取注册表默认。

    盘中敏感性由注册表声明（数据属性），不再由配置列表决定——避免非行情类型被误配成
    盘中 30s 高频打源。若用户同时配了 `cache_ttl.{type}` 而该类型盘中敏感，打一条 INFO
    说明「盘中以 market_hour_ttl 为准」，把静默失效变成可观测。

    读侧（`cache.get`）与清理侧（`cleanup_expired`）取到的是同一个数——这是
    「读写两侧判定期一致」的前提，不需要两侧各自对齐。

    Args:
        data_type: 数据类型键名，如 "price"、"rank"、"hold"

    Returns:
        过期时间（秒）
    """
    defaults = get_cache_ttl_defaults()
    try:
        from src.python.config import get_config  # lazy import

        config = get_config()
        market_ttl = get_market_ttl_map().get(data_type)
        if market_ttl is not None and _is_market_open():
            override = config.get("market_hour_ttl", market_ttl)
            try:
                ttl = max(30.0, min(86400.0, float(override)))
            except (TypeError, ValueError):
                ttl = max(30.0, min(86400.0, float(market_ttl)))
            if data_type in (config.get("cache_ttl") or {}) and data_type not in _INTRADAY_OVERRIDE_NOTIFIED:
                _INTRADAY_OVERRIDE_NOTIFIED.add(data_type)
                logger.info(
                    "[cache] 交易时段内 %s 使用盘中 TTL（%.0fs），cache_ttl.%s 仅在盘后生效；"
                    "如需调整盘中频率请改 market_hour_ttl",
                    data_type,
                    ttl,
                    data_type,
                )
            return ttl
        ttl_config = config.get("cache_ttl") or {}
        if data_type in ttl_config:
            val = float(ttl_config[data_type])
            return val if val > 0 else defaults.get(data_type, CACHE_DAILY)
        return defaults.get(data_type, CACHE_DAILY)
    except (ImportError, TypeError, ValueError, KeyError, AttributeError, RuntimeError):
        logger.debug("get_ttl: 配置读取失败，使用默认值")
        return defaults.get(data_type, CACHE_DAILY)
