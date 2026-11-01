"""进程级并发预算 —— 多个池共享的天花板（只兜底，不改各模块打磨过的取值）。

背景：各模块的并发数是按「上游配额 + 本机算力 + 数据形状」各自打磨出来的（基金 3、
行业 8、财报 3、akshare 2、行情回退 8……），不应统一；但每个池只做「自己不超
`batch.max_total_workers`」的**逐池**钳位，进程里同时活跃的池加起来仍可能远超预算
（实测数据准备阶段：穿透 2 + 基金 3 + 行业 8 + akshare 2 ≈ 15 线程；4 核机器上就是
互相争 CPU）。本模块只补这一层：

  - **预算** = `batch.max_total_workers`，再按本机核数钳一次（弱机器按核数收敛）；
  - **只在池创建时生效**：申请的池按顺序分配剩余额度，不足则缩到至少 1 并告警；
    **不抢占**（已经跑起来的池不会被中途缩容——那只会让账实不符）；
  - **不改任何模块的请求值**：参与是显式的（`BatchDispatcher` 与 `worker_pool`），
    未参与的池（结构性固定，如新闻 5 源）行为与从前一致。

观测：`begin_run()` 由每次报告的 `PerfCollector` 触发，计数器随快照写入
`perf_history.jsonl` 的 `counters`（`concurrency_budget` / `concurrency_peak` /
`concurrency_clamps`），另有一条 INFO 汇总与逐次缩容 WARNING。
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("invest")

#: 配置缺失时的默认预算（与 `batch.max_total_workers` 默认值同源）
DEFAULT_BUDGET = 15

#: 优先级（仅用于观测与告警排序，不做抢占）：数值小 = 更关键
PRIORITY_INTERACTIVE = 10  # 交互/报告关键路径（基金持仓、财报、行情回退）
PRIORITY_BATCH = 30  # 常规批量（行业分类、akshare 指标）
PRIORITY_PREFETCH = 60  # 预取/可选增强


@dataclass
class _Lease:
    """一个池占用的额度（申请值 / 实授值 / 优先级）。"""

    requested: int
    granted: int
    priority: int


class ConcurrencyGovernor:
    """进程级预算账本（线程安全；同名池重复申请视为同一租约）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._leases: dict[str, _Lease] = {}
        self._budget: int | None = None
        self._announced = False
        self._run_clamps = 0
        self._run_grants = 0
        self._run_peak = 0

    # ── 预算 ──────────────────────────────────────────────

    @staticmethod
    def resolve_budget() -> int:
        """预算 = min(配置 max_total_workers, 本机核数)；配置不可读时回落默认值。"""
        requested = DEFAULT_BUDGET
        try:
            from src.python.config import get_config

            batch_cfg = (get_config() or {}).get("batch") or {}
            raw = batch_cfg.get("max_total_workers", DEFAULT_BUDGET)
            if isinstance(raw, (int, float)) and raw >= 1:
                requested = int(raw)
        except Exception:  # 配置损坏不应让并发层抛错（降级为默认预算）
            logger.debug("[并发] 读取 batch.max_total_workers 失败，回落默认预算 %d", DEFAULT_BUDGET)
        cpu = os.cpu_count() or 1
        return max(1, min(requested, cpu))

    def budget(self) -> int:
        with self._lock:
            if self._budget is None:
                self._budget = self.resolve_budget()
            return self._budget

    def begin_run(self) -> None:
        """每次报告开始时重置运行期观测计数（租约本身不重置——池可能仍在用）。"""
        with self._lock:
            self._budget = self.resolve_budget()
            self._run_clamps = 0
            self._run_grants = 0
            self._run_peak = 0
            self._announced = False

    # ── 租约 ──────────────────────────────────────────────

    def acquire(self, name: str, requested: int, *, priority: int = PRIORITY_BATCH) -> int:
        """为池 ``name`` 申请 ``requested`` 个 worker，返回**实授值**（至少 1）。

        同名池重复申请直接返回既有额度（嵌套/重入不重复占预算）。
        """
        requested = max(1, int(requested))
        with self._lock:
            existing = self._leases.get(name)
            if existing is not None:
                return existing.granted
            budget = self._budget if self._budget is not None else self.resolve_budget()
            self._budget = budget
            used = sum(lease.granted for lease in self._leases.values())
            granted = max(1, min(requested, budget - used))
            self._leases[name] = _Lease(requested, granted, priority)
            self._run_grants += 1
            self._run_peak = max(self._run_peak, used + granted)
            if not self._announced:
                self._announced = True
                logger.info(
                    "[并发] 预算 %d（本机 %d 核，配置 max_total_workers），按池顺序分配、不抢占",
                    budget,
                    os.cpu_count() or 1,
                )
            if granted < requested:
                self._run_clamps += 1
                logger.warning(
                    "[并发] %s 申请 %d worker 缩至 %d（预算 %d，已占 %d）——弱机器/多池叠加时按剩余额度收敛",
                    name,
                    requested,
                    granted,
                    budget,
                    used,
                )
            return granted

    def release(self, name: str) -> None:
        """释放池 ``name`` 的额度（幂等）。"""
        with self._lock:
            self._leases.pop(name, None)

    def reset(self) -> None:
        """清空全部租约与观测计数（测试隔离用）。"""
        with self._lock:
            self._leases.clear()
            self._budget = None
            self._announced = False
            self._run_clamps = 0
            self._run_grants = 0
            self._run_peak = 0

    def snapshot(self) -> dict[str, Any]:
        """当前账本快照（供 perf 计数与诊断）。"""
        with self._lock:
            used = sum(lease.granted for lease in self._leases.values())
            return {
                "budget": self._budget if self._budget is not None else self.resolve_budget(),
                "granted": used,
                "pools": {name: lease.granted for name, lease in sorted(self._leases.items())},
                "peak": self._run_peak,
                "clamps": self._run_clamps,
            }


#: 进程级单例（TUI 常驻进程复用；测试由 conftest 的 autouse fixture 重置）
GOVERNOR = ConcurrencyGovernor()


@contextmanager
def worker_pool(
    name: str,
    requested: int,
    *,
    priority: int = PRIORITY_BATCH,
    thread_name_prefix: str | None = None,
):
    """按预算分配创建线程池并在退出时释放额度（替代裸 ``ThreadPoolExecutor``）。"""
    from concurrent.futures import ThreadPoolExecutor

    granted = GOVERNOR.acquire(name, requested, priority=priority)
    pool = ThreadPoolExecutor(max_workers=granted, thread_name_prefix=thread_name_prefix or name)
    try:
        yield pool
    finally:
        pool.shutdown(wait=True)
        GOVERNOR.release(name)


__all__ = [
    "GOVERNOR",
    "DEFAULT_BUDGET",
    "PRIORITY_BATCH",
    "PRIORITY_INTERACTIVE",
    "PRIORITY_PREFETCH",
    "ConcurrencyGovernor",
    "worker_pool",
]
