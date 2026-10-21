"""网络隔离原语回归测试 — 全局守卫的“不可吞”语义与离线外部数据桩。

回归背景（两处真实缺陷）：

1. 守卫早期抛 ``RuntimeError``（``Exception`` 子类），被数据源 provider / fetcher
   链路的 ``except Exception`` 降级**静默吞掉** → 漏 mock 的用例退化成“验证网络被
   阻断后的降级”，并触发链路同源瞬时重试退避（0.6~1.2s/槽）白等：实测 unit 模式
   1072 次未 mock 尝试、300 次退避睡眠、累计 149.3s 空等。
2. 收紧为不可吞错误时又暴露出反向问题：若连 ``socket.socket()`` **构造**也阻断，
   会误伤第三方库的导入期探测（urllib3 导入期构造 socket 且仅被 ``except Exception``
   包住）→ 库导入直接失败。正确边界是**只阻建连（connect/getaddrinfo），不阻构造**。

本文件同时覆盖 ``offline_external_sources`` 桩的覆盖面（HTTP 出口 / 交易日历 /
链路退避 / akshare 直连路径），确保“声明离线”后确实零网络、零等待。
"""

from __future__ import annotations

import socket
import time

import pytest

from src.test._network_guard import (
    BLOCKED_NETWORK_MSG,
    NetworkBlockedInTests,
    OfflineHTTPClient,
)

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


@pytest.fixture(autouse=True)
def _requires_network_guard(request):
    """``--run-live`` 会放行真实网络（守卫关闭本文件的断言前提）→ 跳过。"""
    if request.config.getoption("--run-live"):
        pytest.skip("--run-live 下不启用网络守卫")
    if request.node.get_closest_marker("live") is not None:
        pytest.skip("live 套件放行真实网络")


class TestGlobalNetworkGuard:
    """未 mock 的外网访问必须**瞬时硬失败**（不可被宽泛降级吞掉）。"""

    def test_connect_is_blocked_instantly(self) -> None:
        """建连入口被阻断且不等待——没有重试退避的空等。"""
        start = time.perf_counter()
        with pytest.raises(NetworkBlockedInTests, match="外部网络访问被阻断"):
            socket.create_connection(("example.com", 80), timeout=5)
        assert time.perf_counter() - start < 1.0

    def test_dns_lookup_is_blocked(self) -> None:
        with pytest.raises(NetworkBlockedInTests):
            socket.getaddrinfo("example.com", 80)

    def test_guard_error_escapes_broad_except(self) -> None:
        """回归 1：provider 惯用的 ``except Exception`` 降级不得吞掉守卫错误。

        若守卫错误是 ``Exception`` 子类，下面的 ``_degrade_like_provider`` 会返回
        ``"degraded"`` → 用例静默依赖外网降级；正确行为是错误穿透出来（硬失败）。
        """

        def _degrade_like_provider() -> str:
            try:
                socket.getaddrinfo("example.com", 80)
            except Exception:  # noqa: BLE001 — 刻意模拟 provider 的宽泛降级写法
                return "degraded"
            return "no-network-attempt"

        with pytest.raises(NetworkBlockedInTests):
            _degrade_like_provider()

    def test_socket_construction_is_allowed(self) -> None:
        """回归 2：只阻建连、不阻构造——否则第三方库导入期构造 socket 会失败。"""
        sock = socket.socket()
        try:
            assert sock.fileno() >= 0
        finally:
            sock.close()

    def test_message_is_actionable(self) -> None:
        assert "mock" in BLOCKED_NETWORK_MSG


@pytest.mark.usefixtures("offline_external_sources")
class TestOfflineExternalSources:
    """``offline_external_sources``：显式声明“本文件不依赖任何外部数据源”。"""

    def test_httpx_client_is_offline(self) -> None:
        import httpx

        assert httpx.Client is OfflineHTTPClient
        with httpx.Client(timeout=1) as client:
            with pytest.raises(RuntimeError, match="外部网络访问被阻断"):
                client.get("https://example.com")

    def test_async_httpx_client_is_offline(self) -> None:
        import asyncio

        import httpx

        async def _call() -> None:
            async with httpx.AsyncClient() as client:
                await client.get("https://example.com")

        with pytest.raises(RuntimeError, match="外部网络访问被阻断"):
            asyncio.run(_call())

    def test_trading_calendar_returns_empty(self) -> None:
        """交易日历（akshare/同花顺，不经 httpx）→ 空集，调用方回退简易判断。"""
        from src.python.core import trading_calendar

        assert trading_calendar._get_trading_calendar() == set()

    def test_chain_transient_backoff_zeroed(self) -> None:
        """链路同源瞬时重试退避置 0：重试分支仍在，但不再等待。"""
        from src.python.fetcher import chain

        assert chain._TRANSIENT_RETRY_BACKOFF == 0.0

    def test_akshare_backed_entries_are_stubbed(self) -> None:
        """akshare 直连路径（不经 httpx）同样置空，避免漏网的真实请求。"""
        from src.python.providers import akshare_extras, akshare_news

        assert akshare_news.fetch_news() == []
        assert akshare_extras._fetch_all_dividends(["600900"]) == {}

    def test_interval_throttle_wait_is_zeroed(self) -> None:
        """间隔节流等待不再占用墙钟（分支照走：仍返回实际请求序列一个许可）。"""
        from src.python.core.throttle import RateLimiter

        limiter = RateLimiter()
        start = time.perf_counter()
        waited = limiter.acquire_interval("offline-endpoint", 1.5)
        limiter.acquire_interval("offline-endpoint", 1.5)  # 第二次本应等满 1.5s
        elapsed = time.perf_counter() - start

        assert waited >= 0.0  # 算式仍返回等待量（语义未变），只是没真的睡
        assert elapsed < 0.5, f"离线桩下间隔节流仍在等待：{elapsed:.2f}s"

    def test_retry_backoff_wait_is_zeroed(self) -> None:
        """多策略退避不再白等，但重试次数与最终结果不受影响。"""
        from src.python.core.retry import STRATEGY_LINEAR, RetryPolicy, retry_transient

        calls: list[int] = []

        def _always_fail() -> None:
            calls.append(1)
            raise ConnectionError("瞬时失败")

        start = time.perf_counter()
        with pytest.raises(ConnectionError):
            retry_transient(
                _always_fail,
                policy=RetryPolicy(attempts=3, strategy=STRATEGY_LINEAR, base_backoff=1.0),
                retry_on=lambda exc: isinstance(exc, ConnectionError),
            )
        elapsed = time.perf_counter() - start

        assert len(calls) == 3  # 重试分支照常覆盖（线性退避本应 1+2=3s）
        assert elapsed < 0.5, f"离线桩下退避仍在等待：{elapsed:.2f}s"

    def test_no_wait_clock_keeps_real_monotonic(self) -> None:
        """只接管 sleep：monotonic / perf_counter 必须仍是真实时钟。"""
        from src.python.core import throttle

        clock = throttle.time
        before = time.monotonic()
        slept = clock.sleep(2.0)
        after = time.monotonic()

        assert slept is None
        assert after - before < 0.5
        assert abs(clock.monotonic() - time.monotonic()) < 0.5
        assert clock.perf_counter() > 0.0


class TestOfflineFixtureIsOptIn:
    """桩是显式 opt-in：未声明时不得改变 httpx 行为（由全局守卫负责兜底）。"""

    def test_not_applied_by_default(self) -> None:
        import httpx

        assert httpx.Client is not OfflineHTTPClient

    def test_wait_clock_not_applied_by_default(self) -> None:
        """未声明离线时等待语义原样保留（否则会伤到验证退避/节流的用例）。"""
        from src.python.core import retry, throttle

        assert throttle.time is time
        assert retry.time is time


class TestOfflineStubTargets:
    """桩清单完整性：被 monkeypatch 的模块/属性必须仍然存在。

    桩以「模块路径字符串」写死（``httpx.Client`` / ``trading_calendar._get_trading_calendar`` /
    ``chain._TRANSIENT_RETRY_BACKOFF`` / ``akshare_extras.ak`` / 四个模块的 ``time``）；上游
    重命名或搬迁会让``monkeypatch.setattr`` 在用例运行时直接报 AttributeError（不会静默
    失效）。本用例把这一层提前为可独立发现的断言，避免"改一处名字、跑全套才炸"。
    """

    def test_stub_targets_exist(self) -> None:
        import httpx

        from src.python.core import retry, throttle, trading_calendar
        from src.python.fetcher import chain
        from src.python.providers import akshare_extras, cninfo, datasink

        assert callable(getattr(httpx, "Client", None))
        assert callable(getattr(httpx, "AsyncClient", None))
        assert callable(getattr(trading_calendar, "_get_trading_calendar", None))
        assert isinstance(getattr(chain, "_TRANSIENT_RETRY_BACKOFF", None), float)
        assert hasattr(akshare_extras, "ak")
        for module in (throttle, retry, cninfo, datasink):
            assert callable(getattr(module, "time", None).sleep), f"{module.__name__} 缺 time.sleep"
