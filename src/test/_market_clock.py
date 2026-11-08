"""测试共用：把「行情口径桶」冻结成指定档位。

LLM 缓存指纹里的桶键随钟面变化（盘中 / 上午收盘 / 当日收盘 / 上一交易日收盘），
而针对指纹的断言都只关心「同档下键的增减」。档位字面量（key/label/as_of）若在
各测试文件里各写一份，口径调整时就会互相漂移，故收口到本模块单源。
"""

from __future__ import annotations

from typing import Any

from src.python.core import market_hours

#: 黄金基线与多数用例使用的固定档位（收盘档，日期取一个真实交易日）
CLOSED_KEY = "close:2026-11-06"
CLOSED_LABEL = "当日收盘（2026-11-06）"
INTRADAY_KEY = "intraday:2026-11-06"
INTRADAY_LABEL = "盘中（2026-11-06 10:00）"


def freeze_market_bucket(
    monkeypatch: Any,
    *,
    key: str = CLOSED_KEY,
    label: str | None = None,
    intraday: bool = False,
    as_of: str = "2026-11-06",
) -> market_hours.MarketSnapshot:
    """把 ``market_hours.market_snapshot_bucket`` 钉在指定档位，返回该档位对象。

    Args:
        monkeypatch: pytest 的 monkeypatch（用后自动还原）
        key: 桶键（默认收盘档 ``close:2026-11-06``）
        label: 人读口径；缺省按 ``key`` 前缀推导（close→当日收盘 / noon→上午收盘 /
            intraday→盘中）
        intraday: 是否盘中档（盘中档的复用策略不同，须显式给）
        as_of: 行情基准日

    Returns:
        冻结后的 :class:`market_hours.MarketSnapshot`（便于断言 label 等）
    """
    if label is None:
        prefix = key.split(":", 1)[0]
        label = {
            "close": f"当日收盘（{as_of}）",
            "noon": f"上午收盘（{as_of} 11:30）",
            "intraday": f"盘中（{as_of} 10:00）",
        }.get(prefix, key)
    frozen = market_hours.MarketSnapshot(key=key, label=label, as_of=as_of, intraday=intraday)
    monkeypatch.setattr(market_hours, "market_snapshot_bucket", lambda now=None: frozen)
    return frozen


def freeze_intraday(monkeypatch: Any) -> market_hours.MarketSnapshot:
    """钉在盘中档（价格还在变 ⇒ 价格相关模块不复用）。"""
    return freeze_market_bucket(monkeypatch, key=INTRADAY_KEY, label=INTRADAY_LABEL, intraday=True)
