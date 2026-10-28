"""负缓存探针 — 「确定性缺失」结论的读写与命中计数的单一样板。

财报取数有三类「源侧确实没有」的结论需要跨报告复用（标的正文缺失 / 章节清单不可得 /
某文档某章节无正文），provider 侧还有一类（章节探测 404）。此前每类各写一遍
「键前缀 + lock + 命中计数 + reset + get/set」，新增一类就要再抄一遍，命名与日志口径
还会漂移。这里抽成一个小工具：调用点只声明「标签 + 键前缀 + TTL 类型」，计数与汇总
日志由统一清单派生。

设计约束（负缓存纪律，见 `technical.md`「负缓存同源」）：

- **只登记确定性结论**：调用点在「确实没有」时调用 :meth:`NegativeCache.mark`；
  传输级失败（超时/断连/5xx/429）不得调用——那可能只是瞬时不可用，缓存会延长恢复期。
- **TTL 走注册表**：`ttl_type` 必须是 `core/data_registry.py` 登记的缓存类型，
  读侧与清理判定同源（`cache.get_ttl`）。
- **命中是省请求而非错误**：计数只用于报告级一行 INFO 汇总，不参与降级统计。
"""

from __future__ import annotations

import threading
from typing import Any

from ._store import clear, get, set
from ._ttl import get_ttl

#: 全量实例清单（模块级注册顺序即日志输出顺序）：供「一轮开始清零」与「报告级汇总」枚举，
#: 新增一类负缓存只需在此登记，不再各自维护 lock/counter/reset 样板。
_REGISTRY: list[NegativeCache] = []  # type: ignore[name-defined]  # noqa: F821 — 先声明后填充
_REGISTRY_LOCK = threading.Lock()


class NegativeCache:
    """一类负缓存：键构造 + 命中计数 + 汇总文案。

    Args:
        label: 报告级汇总文案中的中文标签（如「章节清单不可得」）。
        prefix: 缓存键前缀（与 `core/data_registry.py` 登记的前缀一致）。
        ttl_type: 注册表缓存类型（决定读侧 TTL 与清理判定），如 ``report_symbol_miss``。
        hit_note: 命中时的补充说明（可选，用于解释「跳过的是什么请求」）。
    """

    def __init__(self, label: str, prefix: str, ttl_type: str, *, hit_note: str = "") -> None:
        self.label = label
        self.prefix = prefix
        self.ttl_type = ttl_type
        self.hit_note = hit_note
        self._hits = 0
        self._lock = threading.Lock()
        with _REGISTRY_LOCK:
            _REGISTRY.append(self)

    # ── 键 ────────────────────────────────────────────────
    def key(self, *parts: Any) -> str:
        """拼出该类的缓存键（前缀 + 业务标识）。"""
        return self.prefix + "".join(str(p) for p in parts)

    # ── 读 ────────────────────────────────────────────────
    def probe(self, key: str) -> Any | None:
        """读取负缓存；命中时累计一次命中并返回缓存值（未命中返回 None）。"""
        value = get(key, get_ttl(self.ttl_type))
        if value is not None:
            with self._lock:
                self._hits += 1
        return value

    def is_missing(self, key: str) -> bool:
        """该键是否已判定为确定性缺失（命中计数同 :meth:`probe`）。"""
        return self.probe(key) is not None

    # ── 写/清 ─────────────────────────────────────────────
    def mark(self, key: str, reason: str = "确定性缺失") -> None:
        """登记确定性缺失结论（只应在确认「源侧确实没有」时调用）。"""
        set(key, reason)

    def clear(self, key: str) -> None:
        """清除该键的负缓存（源侧状态可能变化时调用，与正缓存同清）。"""
        clear(key)

    # ── 计数与汇总 ────────────────────────────────────────
    def hits(self) -> int:
        """本轮命中次数。"""
        with self._lock:
            return self._hits

    def reset(self) -> None:
        with self._lock:
            self._hits = 0

    def summary_text(self) -> str:
        """报告级汇总文案（仅在命中次数非零时使用）。"""
        count = self.hits()
        note = f"（{self.hit_note}）" if self.hit_note else ""
        return f"{self.label}命中负缓存 {count} 次{note}"


def negative_cache_entries() -> tuple[NegativeCache, ...]:
    """全量负缓存实例（枚举顺序 = 登记顺序）。"""
    with _REGISTRY_LOCK:
        return tuple(_REGISTRY)


def reset_all_negative_hits() -> None:
    """清零全部负缓存的命中计数（每份报告开头调用）。"""
    for entry in negative_cache_entries():
        entry.reset()


def nonzero_summaries() -> list[str]:
    """本轮有命中（次数 > 0）的负缓存汇总文案。"""
    return [entry.summary_text() for entry in negative_cache_entries() if entry.hits()]


__all__ = [
    "NegativeCache",
    "negative_cache_entries",
    "nonzero_summaries",
    "reset_all_negative_hits",
]
