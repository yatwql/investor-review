"""LLM worker 装配：client 生命周期、HTTP/2 降级、thinking 并发闸门与等待记账。

为什么要独立成模块（而不是留在 `_llm_dispatch`）：派发函数里这一层是**闭包套闭包**
（`_make_runner` → `_run` → `_execute`），三条最关键的运行契约都藏在这里——

  - client 由 `core.http_client.make_http_client` 统一创建，缺 h2 包时去掉 `http2`
    降级重试一次（能力判定单点，不得散落到各生成函数）；
  - thinking 模块（`thinking_enabled_{label}`）额外受信号量约束：同一时刻最多
    `llm_max_thinking_concurrency` 个请求（相邻并发会让端点返回 200 + 空 content）；
  - 等待时长累加到总账（`record_thinking_wait`），供派发侧判断「提到 2 能省多少」。

本模块不持线程池、不做预算判定、不写结果字典——那些留在派发侧。
`make_http_client` 的调用点在本模块，测试对该 seam 的 patch 目标随之落在
`src.python.llm._worker_runner.make_http_client`。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from src.python.core.http_client import make_http_client
from src.python.llm.api_base import LLM_TIMEOUT

logger = logging.getLogger("invest")

#: 信号量等待超过该阈值才打一行 INFO（静默串行时只能靠时间轴发现）
_DEFAULT_WAIT_LOG_SECONDS = 5.0


def thinking_concurrency_limit(llm_config: dict | None) -> int:
    """thinking 并发上限：配置值非法（<=0/非数值）时回落 1。"""
    from src.python.config import get_llm_setting_default

    try:
        limit = int(
            (llm_config or {}).get(
                "llm_max_thinking_concurrency", get_llm_setting_default("llm_max_thinking_concurrency")
            )
        )
    except (TypeError, ValueError):
        return 1
    return max(1, limit)


def is_thinking_module(llm_config: dict | None, label: str) -> bool:
    """该模块是否开启了 Extended Thinking（`thinking_enabled_{label}`）。"""
    return bool((llm_config or {}).get(f"thinking_enabled_{label}", False))


def _build_client() -> Any:
    """创建本轮 client：HTTP/2 + 连接池；缺 h2 包时去掉 `http2` 降级重试一次。"""
    from src.python.llm._llm_dispatch import _LLM_CLIENT_SETTINGS

    try:
        return make_http_client(timeout=LLM_TIMEOUT, **_LLM_CLIENT_SETTINGS)
    except ImportError:
        logger.info("h2 包未安装，降级到 HTTP/1.1")
        settings = dict(_LLM_CLIENT_SETTINGS)
        settings.pop("http2", None)
        return make_http_client(timeout=LLM_TIMEOUT, **settings)


def make_module_runner(
    *,
    label: str,
    fn: Callable,
    llm_config: dict | None,
    label_map: dict[str, str],
    thinking_sem: Any,
    thinking_limit: int,
    span_recorder: Any,
    record_thinking_wait: Callable[[float], None],
    wait_log_seconds: float = _DEFAULT_WAIT_LOG_SECONDS,
) -> Callable[[], tuple[str | None, bool]]:
    """构造一个模块的 worker：thinking 闸门 → client 装配 → 调用生成函数。

    Args:
        label: 模块键（`global_macro` 等）。
        fn: 生成函数 `fn(client, llm_config) -> (content, from_cache)`。
        llm_config: LLM 配置（thinking 开关与并发上限的来源）。
        label_map: 模块键 → 中文标签（日志可读）。
        thinking_sem: thinking 并发信号量（由派发侧按上限创建）。
        thinking_limit: 上限值（仅用于日志）。
        span_recorder: 逐模块耗时记录器（None 时零行为变化）。
        record_thinking_wait: 等待时长记账回调（由派发侧注入，保证总账单源）。
        wait_log_seconds: 等待超过该阈值打一行 INFO。

    Returns:
        无参可调用对象，返回 `(content, from_cache)`。
    """

    def _run() -> tuple[str | None, bool]:
        if not is_thinking_module(llm_config, label):
            return _execute()
        waited_from = time.monotonic()
        with thinking_sem:
            waited = time.monotonic() - waited_from
            record_thinking_wait(waited)
            # 信号量等待完全静默时，只有对时间轴才能发现「thinking 模块被串行」
            # （实测两个 thinking 模块各 37s/51s 被上限=1 完全串行，白等 38s 却无日志线索）
            if waited >= wait_log_seconds:
                logger.info(
                    "[llm/thinking] %s 等待 thinking 并发槽 %.1fs（上限 %d，已并发占满时串行化）",
                    label_map.get(label, label),
                    waited,
                    thinking_limit,
                )
            return _execute()

    def _execute() -> tuple[str | None, bool]:
        logger.info("正在生成：%s...", label_map.get(label, label))
        client = _build_client()
        started = time.perf_counter()
        try:
            return fn(client, llm_config)
        finally:
            client.close()
            if span_recorder is not None:
                span_recorder.record(label_map.get(label, label), time.perf_counter() - started)

    return _run


__all__ = [
    "is_thinking_module",
    "make_module_runner",
    "thinking_concurrency_limit",
]
