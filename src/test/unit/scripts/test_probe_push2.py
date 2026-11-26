"""`_probes/push2`（push2 连通性探测）单次探测多态与汇总判定单元测试。

该 target 的产物就是「程序缺陷 vs 网络拦截」的判读依据，因此各类结果
（成功 / data 空 / 非 JSON / HTTP 错误码 / 断连 / 超时 / 其他异常）必须各自可辨，
且汇总只在「三发全成」时才判网络正常。HTTP 客户端换成假对象，不触网。
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import httpx  # noqa: E402

from _probes import push2  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


class _FakeResponse:
    def __init__(self, status_code: int = 200, headers: dict | None = None, payload: object = None):
        self.status_code = status_code
        self.headers = headers if headers is not None else {"content-type": "application/json"}
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("响应不是 JSON")
        return self._payload


class _FakeClientFactory:
    """httpx.Client 替身工厂：记录构造参数与请求，按预设返回响应或抛异常。"""

    def __init__(self):
        self.response: _FakeResponse | None = None
        self.exc: Exception | None = None
        self.instances: list[SimpleNamespace] = []

    def configure(self, response: _FakeResponse | None = None, exc: Exception | None = None) -> None:
        self.response, self.exc = response, exc

    def client_class(self):
        factory = self

        class _FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.requests: list[dict] = []
                factory.instances.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *_exc_info):
                return False

            def get(self, url, params=None, headers=None):
                self.requests.append({"url": url, "params": params, "headers": headers})
                if factory.exc is not None:
                    raise factory.exc
                return factory.response

        return _FakeClient


@pytest.fixture
def fake_httpx(monkeypatch):
    """把 push2 模块内的 httpx 换成注入式替身（只影响本用例，不动全局 httpx）。"""
    factory = _FakeClientFactory()
    shim = SimpleNamespace(
        Client=factory.client_class(),
        RemoteProtocolError=httpx.RemoteProtocolError,
        TimeoutException=httpx.TimeoutException,
    )
    monkeypatch.setattr(push2, "httpx", shim)
    return factory


# ── 单次探测的各类结果 ──────────────────────────────────────


def test_probe_once_success_reports_latency_and_industry(fake_httpx):
    """成功：打印行业字段，请求带上探测参数与浏览器指纹头。"""
    fake_httpx.configure(response=_FakeResponse(payload={"data": {"f127": "制造业"}}))

    ok, desc = push2._probe_once(0)

    assert ok is True
    assert "[0] 成功" in desc
    assert "行业=制造业" in desc
    request = fake_httpx.instances[0].requests[0]
    assert request["url"] == push2._URL
    assert request["params"] == push2._PARAMS
    assert request["headers"] == push2._HEADERS
    assert fake_httpx.instances[0].kwargs["timeout"] == push2._TIMEOUT


def test_probe_once_json_without_data_is_not_success(fake_httpx):
    """HTTP 200 但 data 为空 → 判非预期（被重定向/拦截的典型形态）。"""
    fake_httpx.configure(response=_FakeResponse(payload={"data": None}))

    ok, desc = push2._probe_once(1)

    assert ok is False
    assert "HTTP 200" in desc
    assert "响应非预期" in desc


def test_probe_once_non_json_content_type_is_not_success(fake_httpx):
    """content-type 不是 JSON 时不去解析响应体（HTML 拦截页易触发解析异常）。"""
    fake_httpx.configure(response=_FakeResponse(headers={"content-type": "text/html"}, payload={"data": {"f127": "x"}}))

    ok, desc = push2._probe_once(2)

    assert ok is False
    assert "响应非预期" in desc


def test_probe_once_reports_http_error_status(fake_httpx):
    fake_httpx.configure(response=_FakeResponse(status_code=502, payload={"data": {}}))

    ok, desc = push2._probe_once(0)

    assert ok is False
    assert "HTTP 502" in desc


def test_probe_once_distinguishes_disconnect(fake_httpx):
    """断连单独成一类（正是本 target 要定位的 push2 断连现象）。"""
    fake_httpx.configure(exc=httpx.RemoteProtocolError("Server disconnected"))

    ok, desc = push2._probe_once(0)

    assert ok is False
    assert "断连" in desc
    assert "Server disconnected" in desc


def test_probe_once_distinguishes_timeout(fake_httpx):
    fake_httpx.configure(exc=httpx.ReadTimeout("timed out"))

    ok, desc = push2._probe_once(0)

    assert ok is False
    assert "超时" in desc
    assert "ReadTimeout" in desc


def test_probe_once_catches_unexpected_exception(fake_httpx):
    """其他异常也要落成一行判读（诊断脚本不能因未知异常崩掉整轮探测）。"""
    fake_httpx.configure(exc=RuntimeError("证书链异常"))

    ok, desc = push2._probe_once(0)

    assert ok is False
    assert "异常" in desc
    assert "证书链异常" in desc


# ── 汇总判定 ───────────────────────────────────────────────


def test_run_returns_zero_only_when_all_probes_succeed(monkeypatch, capsys):
    calls: list[int] = []
    monkeypatch.setattr(push2, "_probe_once", lambda i: (calls.append(i) is None, f"[{i}] 成功"))

    code = push2.run(SimpleNamespace())

    out = capsys.readouterr().out
    assert code == 0
    assert calls == list(range(push2._PROBES))
    assert f"成功 {push2._PROBES}/{push2._PROBES}" in out
    assert "curl" in out, "汇总须给出 curl 对照命令（区分 TLS 指纹拦截与环境问题）"


def test_run_returns_one_when_any_probe_fails(monkeypatch, capsys):
    results = iter([(True, "[0] 成功"), (False, "[1] 断连"), (True, "[2] 成功")])
    monkeypatch.setattr(push2, "_probe_once", lambda _i: next(results))

    code = push2.run(SimpleNamespace())

    out = capsys.readouterr().out
    assert code == 1
    assert f"成功 2/{push2._PROBES}" in out
    assert "[1] 断连" in out
