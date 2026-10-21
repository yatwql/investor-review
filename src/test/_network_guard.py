"""测试网络隔离原语 — 阻断未 mock 的外部访问 + 显式离线外部数据桩。

两件事在这里集中定义，供 ``src/test/conftest.py`` 使用：

1. :data:`BLOCKED_NETWORK_MSG` / :class:`NetworkBlockedInTests` —— 全局网络守卫
   （``conftest._block_external_network``）抛出的错误。继承 ``BaseException``
   而非 ``Exception``：数据源 provider 与 fetcher 链路普遍用 ``except Exception``
   做降级，若用 ``RuntimeError`` 会被静默吞掉 → 用例退化成“验证网络被阻断后的降级”
   且触发链路瞬时重试退避白等。用 ``BaseException`` 后漏 mock 即瞬时硬失败。

2. :class:`OfflineHTTPClient` / :class:`OfflineAsyncHTTPClient` /
   :func:`apply_offline_stubs` —— ``offline_external_sources`` fixture 的实现：
   把仓内 HTTP 出口（``httpx.Client``）与若干非 httpx 外部入口换成“即时取不到”，
   链路口径仍为“源不可用 → 降级”，但零网络、零退避等待。
3. :class:`_NoWaitClock` —— 等待型 ``time.sleep`` 的接管家（间隔节流 / 多策略退避 /
   限速 429 重试窗口）：离线桩下这些等待等的是“注定取不到的源”，白等不产生任何
   覆盖增量；换成空 sleep 后分支照常走，只是不再占用墙钟。
"""

from __future__ import annotations

import time
from typing import Any

BLOCKED_NETWORK_MSG = (
    "[ERR] 外部网络访问被阻断：测试用例不得发起真实网络连接，"
    "请 mock 对应的数据源/LLM API 调用（或显式声明 offline_external_sources）。"
)


class NetworkBlockedInTests(BaseException):
    """未 mock 的外部网络访问。

    继承 ``BaseException`` 是**刻意**的：数据源 provider / fetcher 链路 / 报告层
    普遍 ``except Exception`` 降级，若继承 ``Exception`` 会被吞掉，使“漏 mock”表现为
    静默降级（还会白等 retry 退避）。继承 ``BaseException`` 后它会直接冒泡到 pytest，
    把漏 mock 变成**瞬时硬失败**并带上可执行提示。
    """


class OfflineHTTPClient:
    """``httpx.Client`` 的离线桩：任何请求在发出前即时失败（零 socket / 零 DNS）。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> OfflineHTTPClient:
        return self

    def __exit__(self, *exc_info: Any) -> bool:
        return False

    def close(self) -> None:
        pass

    def _fail(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(BLOCKED_NETWORK_MSG)

    get = _fail
    post = _fail
    put = _fail
    delete = _fail
    head = _fail
    options = _fail
    patch = _fail
    request = _fail
    send = _fail
    stream = _fail


class OfflineAsyncHTTPClient(OfflineHTTPClient):
    """``httpx.AsyncClient`` 的离线桩（异步上下文 + 异步动词）。"""

    async def __aenter__(self) -> OfflineAsyncHTTPClient:  # type: ignore[override]
        return self

    async def __aexit__(self, *exc_info: Any) -> bool:  # type: ignore[override]
        return False

    async def _afail(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(BLOCKED_NETWORK_MSG)

    get = _afail
    post = _afail
    put = _afail
    delete = _afail
    head = _afail
    patch = _afail
    request = _afail
    send = _afail
    stream = _afail


class _NoWaitClock:
    """``time`` 模块代理：``sleep`` 变空操作，其余属性原样透传。

    只接管 sleep 是刻意的：``monotonic`` / ``perf_counter`` 必须保持真实时钟——
    间隔节流的“距上次调用已过多久”与超时判据都依赖它，替换掉会改变语义
    （否则“本应等待”的分支会变成“不必等”，零等待会误伤判据）。

    作用域限于被替换的那个模块对象（``setattr(module, "time", proxy)``），因此
    测试自身的 ``time.sleep``、其它模块的等待、以及 ``test_throttle`` /
    ``test_phase_timeout`` 这类**验证等待语义**的用例都不受影响。
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)

    def sleep(self, seconds: float) -> None:  # noqa: ARG002 — 签名对齐 time.sleep
        """空操作（不等待、不抛错）。"""
        return None


class _OfflineAkshareModule:
    """akshare 的离线桩：任意函数调用返回 ``None``。

    各 provider 均把 ``None``/空 DataFrame 视为“取不到”并走降级，因此行为与
    “akshare 不可用”一致；但不像网络守卫那样抛错，不会打断用例。
    覆盖 akshare 直连路径（不经 httpx）：交易日历兜底、分红全量拉取、机构盈利预测、
    行业/概念补充、财新与 CCTV 新闻、国债收益率等。
    """

    def __getattr__(self, name: str):
        def _stub(*_args: Any, **_kwargs: Any) -> None:
            return None

        return _stub


def apply_offline_stubs(monkeypatch: Any) -> None:
    """把外部数据入口置为离线（供 ``offline_external_sources`` fixture 调用）。

    1. ``httpx.Client`` / ``httpx.AsyncClient``：仓内全部 HTTP 出口都经
       ``core.http_client`` 工厂构造 httpx 客户端，替换类即可单点覆盖（含未来新增 provider）。
    2. ``core.trading_calendar._get_trading_calendar``：直接返回空集 → 调用方回退
       “非周末即交易日”的简易判断（比让 akshare 桩走到空 DataFrame 更快、更确定）。
    3. ``fetcher.chain._TRANSIENT_RETRY_BACKOFF``：同源瞬时重试退避置 0
       （仓内既有测试惯例，见 ``chain.py`` 注释）——重试分支仍被覆盖，但不再等待。
    4. akshare 直连路径：换掉 ``sys.modules["akshare"]``（覆盖函数内惰性导入）
       并在 ``providers.akshare_extras`` 已模块级绑定 ``ak`` 时一并替换。
    """
    import sys

    import httpx

    from src.python.core import retry, throttle, trading_calendar
    from src.python.fetcher import chain
    from src.python.providers import akshare_extras, cninfo, datasink

    akshare_stub = _OfflineAkshareModule()

    monkeypatch.setattr(httpx, "Client", OfflineHTTPClient)
    monkeypatch.setattr(httpx, "AsyncClient", OfflineAsyncHTTPClient)
    monkeypatch.setattr(trading_calendar, "_get_trading_calendar", lambda: set())
    monkeypatch.setattr(chain, "_TRANSIENT_RETRY_BACKOFF", 0.0)
    # provider 级重试策略（K 线 / 财务指标多期）同样置零退避：离线桩即时失败时重试
    # 分支仍被覆盖，但不再白等退避（与 chain 同习语）。
    from src.python.core.retry import STRATEGY_FIXED, RetryPolicy
    from src.python.fetcher import financial_indicator
    from src.python.providers import eastmoney, tencent

    def _zero(attempts: int) -> RetryPolicy:
        return RetryPolicy(attempts=attempts, strategy=STRATEGY_FIXED, base_backoff=0.0)

    monkeypatch.setattr(tencent, "_KLINE_RETRY_POLICY", _zero(3))
    monkeypatch.setattr(eastmoney, "_INDEX_RETRY_POLICY", _zero(3))
    monkeypatch.setattr(financial_indicator, "_SERIES_RETRY_POLICY", _zero(2))
    monkeypatch.setitem(sys.modules, "akshare", akshare_stub)
    if getattr(akshare_extras, "ak", None) is not None:
        monkeypatch.setattr(akshare_extras, "ak", akshare_stub)

    # 5. 等待型 sleep 接管（与上面链路口径一致：即时失败后不再白等）——
    #    ``core.throttle`` 的间隔节流（LLM 端点 pacing / provider qps / 批量调度）、
    #    ``core.retry`` 的多策略退避（provider 连接重试、K 线/财务多期重试等，
    #    含函数内就地构造的策略，无需逐个登记）、``cninfo`` / ``datasink`` 的 429
    #    限速重试窗口（两处自用模块级 ``time.sleep``）。
    no_wait = _NoWaitClock()
    for module in (throttle, retry, cninfo, datasink):
        monkeypatch.setattr(module, "time", no_wait)
