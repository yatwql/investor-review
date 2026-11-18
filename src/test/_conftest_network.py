"""conftest 夹具实现 — 外网阻断与离线桩。

本模块由入口 `src/test/conftest.py` 显式 import 回来注册（pytest 只认入口模块命名空间里的
夹具与钩子）；改动后跑 `pytest src/test -q` 验证收集与自动复位仍然生效。
"""

from __future__ import annotations

import pytest

from src.test._network_guard import BLOCKED_NETWORK_MSG, NetworkBlockedInTests, apply_offline_stubs


@pytest.fixture(autouse=True)
def _block_external_network(monkeypatch, request):
    """全局阻断测试运行时真实外部网络连接。

    任何未 mock 的 socket 建连（数据源 API / LLM API / akshare 交易日历 /
    后台数据源健康检查等）立即抛 :class:`NetworkBlockedInTests` 使测试
    **立即失败** —— 从机制上保证测试用例运行时无外部网络依赖。

    异常选择 ``BaseException`` 子类（而非 ``RuntimeError``）的原因：数据源
    provider 与 fetcher 链路普遍用 ``except Exception`` 做降级，用 ``Exception``
    子类会被静静吞掉 → 用例变成“验证网络被阻断后的降级路径”而非按 mock 数据
    验证业务，且触发链路瞬时重试退避（0.6~1.2s/槽）白等。改用 ``BaseException``
    后：漏 mock 即**瞬时硬失败**并提示补 mock，既不会被吞也不消耗退避等待。

    已 mock HTTP 层（httpx.Client / requests / provider 函数 / _fetch_* 等）
    的测试不创建真实 socket，不受影响。

    替代方案（本文件不依赖外部数据时的推荐写法）：
    ``pytestmark = pytest.mark.usefixtures("offline_external_sources")`` ——
    显式声明无需真实数据源，由 ``offline_external_sources`` 把仓内 HTTP 出口
    换成即时失败的离线桩（保留链路“源不可用→降级”口径，但零网络、零等待）。

    例外：带 @pytest.mark.live 的 opt-in 真实网络套件放行（仅当 `--run-live`
    或 `-m live` 显式运行时），允许其发起真实数据源/LLM 连通性探测。

    实现要点：**只阻建连，不阻构造**。
    - 只替换 ``socket.socket.connect`` / ``connect_ex``、``socket.create_connection`` 与
      ``socket.getaddrinfo``（建连 / DNS 入口）。若连 ``socket.socket()`` 构造也阻，
      会误伤第三方库的**导入期**探测（如 urllib3 导入期构造 socket，且仅被 ``except
      Exception`` 包住）→ 硬化成 ``BaseException`` 后会使库导入失败：那是库自身行为，
      不是未 mock 的外网请求。
    - ``socket.socket`` 在 ``socket.py`` 中是 Python 类（继承 ``_socket.socket``），
      其 ``connect`` / ``connect_ex`` 可被 monkeypatch。
    - **回环地址豁免**：``127.0.0.0/8``、``::1``、``localhost`` 的连接放行。回环
      只在进程内部通信，到不了外部服务，不违背守卫意图；而 Windows 上
      ``asyncio.ProactorEventLoop`` 启动即用 ``socket.socketpair()``（内部退化为
      回环 ``connect``）建事件循环自管道，若一并阻断，任何 ``asyncio.run()`` 都会
      在事件循环初始化阶段硬失败（与「未 mock 外网」无关）。
    """
    import socket as _socket

    # opt-in 真实网络套件放行（--run-live 或 -m live 显式运行时）
    if request.config.getoption("--run-live"):
        return
    if request.node.get_closest_marker("live") is not None:
        return

    # 子进程取数（core/v8_subprocess）不在本进程 socket 桩的覆盖范围内：
    # 显式告知子进程「离线」，否则测试会绕过守卫发起真实网络请求。
    monkeypatch.setenv("INVEST_SUBPROCESS_NETWORK_OFFLINE", "1")

    def _is_loopback(addr: object) -> bool:
        """目标地址是否回环（unix socket 路径、None 等非 IP 目标不算）。"""
        if not isinstance(addr, tuple) or len(addr) < 2:
            return False
        host = addr[0]
        if not isinstance(host, str):
            return False
        if host in ("localhost", "::1"):
            return True
        return host.startswith("127.")

    _real_connect = _socket.socket.connect
    _real_connect_ex = _socket.socket.connect_ex
    _real_create_connection = _socket.create_connection

    def _guard(real):
        """包装真实建连函数：回环放行，其余抛异常。"""

        def _wrapped(*args, **kwargs):
            if any(_is_loopback(arg) for arg in args):
                return real(*args, **kwargs)
            raise NetworkBlockedInTests(BLOCKED_NETWORK_MSG)

        return _wrapped

    monkeypatch.setattr(_socket.socket, "connect", _guard(_real_connect))
    monkeypatch.setattr(_socket.socket, "connect_ex", _guard(_real_connect_ex))
    monkeypatch.setattr(_socket, "create_connection", _guard(_real_create_connection))

    def _raise(*args, **kwargs):
        raise NetworkBlockedInTests(BLOCKED_NETWORK_MSG)

    monkeypatch.setattr(_socket, "getaddrinfo", _raise)


@pytest.fixture
def offline_external_sources(monkeypatch):
    """显式声明：本测试文件不依赖任何外部数据源（opt-in，非 autouse）。

    用法（文件级一行）：
        pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("offline_external_sources")]

    作用：把“附带依赖”的外部数据入口置为**离线**，不再依赖全局网络守卫兜底。
    报告/编排类用例通常已 mock 了自己关注的数据（持仓/新闻/LLM），而生产链路还会
    顺带查询交易日历、行业数据、行情、健康检查探针等；这些附带依赖经本 fixture
    变为“即时取不到”——降级/可用性口径不变，但零网络、零等待（仅靠守卫兜底时，
    每个 provider 槽会白等 0.6~1.2s 的链路退避）。

    桩清单与实现见 ``src/test/_network_guard.py::apply_offline_stubs``。
    本文件无需真实数据源时优先用它；需要验证某源真实行为时，请在用例内显式 mock。
    """
    apply_offline_stubs(monkeypatch)
