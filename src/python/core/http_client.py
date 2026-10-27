"""HTTP 客户端工厂 — 统一控制 SSL 验证策略。

所有 provider 模块通过 ``make_http_client()`` 创建 httpx.Client，
确保 SSL 验证策略统一管理。

SSL 验证由环境变量 ``SSL_VERIFY`` 控制（默认 ``true``）：
  - ``true`` / ``1`` / ``yes`` → 验证证书（生产环境推荐）
  - ``false`` / ``0`` / ``no`` → 跳过验证（开发/调试环境）

用法::

    from src.python.core.http_client import make_http_client

    with make_http_client(timeout=30.0) as client:
        resp = client.get(url)

另提供传输层注入点 ``use_transport_factory``：测试基建（数据源记录-回放）
在此处替换「响应从哪来」，从而**不改动任何 provider** 即可离线回放真实响应体。
见 ``core/cassette.py``。
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx

logger = logging.getLogger("invest")


def _should_verify() -> bool:
    """读取环境变量 ``SSL_VERIFY``，返回是否验证 SSL 证书。"""
    val = os.getenv("SSL_VERIFY", "true").strip().lower()
    return val in ("true", "1", "yes")


_SSL_VERIFY = _should_verify()

# 当前生效的传输层工厂；None 表示未安装（走 httpx 默认传输）
_TRANSPORT_FACTORY: Callable[[], httpx.BaseTransport | None] | None = None


@contextmanager
def use_transport_factory(factory: Callable[[], httpx.BaseTransport | None]) -> Iterator[None]:
    """在 ``with`` 块内为 ``make_http_client()`` 安装自定义传输层工厂。

    工厂每次被调用都应返回一个**新的**传输实例：``httpx.Client`` 关闭时会连带
    关闭其传输，若多次调用复用同一实例，前一个客户端退出后后续请求会打到已关闭
    的传输上。

    未安装（或工厂返回 ``None``）时，``make_http_client()`` 的行为与没有本机制
    时完全一致（``transport`` 参数不传 → httpx 默认传输）。

    Args:
        factory: 无参可调用对象，返回 ``httpx.BaseTransport`` 或 ``None``。
    """
    global _TRANSPORT_FACTORY
    previous = _TRANSPORT_FACTORY
    _TRANSPORT_FACTORY = factory
    try:
        yield
    finally:
        _TRANSPORT_FACTORY = previous


def _installed_transport() -> httpx.BaseTransport | None:
    """取当前工厂产出的传输；未安装工厂时返回 ``None``。"""
    if _TRANSPORT_FACTORY is None:
        return None
    return _TRANSPORT_FACTORY()


def make_http_client(**kwargs) -> httpx.Client:
    """创建一个 ``httpx.Client``，自动从环境变量读取 SSL 验证策略。

    若已通过 ``use_transport_factory()`` 安装传输层工厂，则以其产物作为传输
    （显式传入 ``transport`` 时以调用方为准）。

    Args:
        **kwargs: 传递给 ``httpx.Client`` 的额外参数（如 ``timeout``、
            ``follow_redirects``、``headers`` 等）。

    Returns:
        配置好的 ``httpx.Client`` 实例。
    """
    if "verify" not in kwargs:
        kwargs["verify"] = _SSL_VERIFY
    if "transport" not in kwargs:
        transport = _installed_transport()
        if transport is not None:
            kwargs["transport"] = transport
    return httpx.Client(**kwargs)


def post_with_deadline(
    client: httpx.Client,
    url: str,
    headers: dict,
    payload: dict,
    timeout: float,
    *,
    form: bool = False,
) -> Any:
    """执行 HTTP POST，附带端到端墙钟截止，防 read 超时被服务端滴流骗过。

    httpx 的 read 超时度量「相邻两次收到数据的间隔」而非请求总时长：服务端
    网关排队期间若滴流字节（或提前返回响应头），计时器被不断重置，配置的
    timeout 完全不生效（实测上游服务过载时单请求挂足其 900s 上限）。

    此处把 POST 放进独立 daemon 线程执行，主线程 join 等待；到点未返回即放弃，
    归一为 ``httpx.ReadTimeout``，与既有 read 超时走同一分类路径（调用方的
    重试/切换逻辑无需感知两种超时）。被放弃的线程继续挂至服务端返回后自然
    消亡（daemon 线程不阻塞进程退出）；共享 ``httpx.Client`` 线程安全，挂起
    连接由其连接池自行回收。

    ``timeout <= 0`` 时不设墙钟，保持纯 httpx 超时行为。

    Args:
        form: True 时按表单编码提交（``data=payload``），否则按 JSON 提交。
    """

    def _send() -> Any:
        if form:
            return client.post(url, data=payload, headers=headers, timeout=timeout)
        return client.post(url, json=payload, headers=headers, timeout=timeout)

    if timeout <= 0:
        return _send()

    box: dict[str, Any] = {}

    def _run() -> None:
        try:
            box["resp"] = _send()
        except BaseException as exc:  # 异常须跨线程原样上抛，由调用方按类型分流
            box["exc"] = exc

    worker = threading.Thread(target=_run, name="http-post-deadline", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        # 不回显完整 URL：通用层避免潜在敏感查询串入日志，调用方自带标签/端点上下文
        logger.warning("POST 总时长超过墙钟上限 %.0fs，放弃等待", timeout)
        raise httpx.ReadTimeout(f"wall-clock deadline exceeded ({timeout}s)")
    if "exc" in box:
        raise box["exc"]
    return box["resp"]


def make_transport(**kwargs) -> httpx.HTTPTransport:
    """创建一个 ``httpx.HTTPTransport``，沿用与 ``make_http_client`` 相同的 SSL 策略。

    供传输层注入（``use_transport_factory``）复用：需要「真实请求 + 顺带录制」
    的传输在此构造。SSL 验证策略仍是本模块一处集中管理。

    Args:
        **kwargs: 传递给 ``httpx.HTTPTransport`` 的额外参数。

    Returns:
        配置好的 ``httpx.HTTPTransport`` 实例。
    """
    if "verify" not in kwargs:
        kwargs["verify"] = _SSL_VERIFY
    return httpx.HTTPTransport(**kwargs)
