"""providers 各用例注入 ``make_http_client`` 的共享 HTTP 替身。

providers 测试此前每文件自带一份响应/客户端桩，接口随用随加导致同一概念多个拼写
（``FakeResponse`` / ``_Resp``）与语义分叉（有的按 URL 后缀分派、有的只回单个响应、
有的要 ``content`` 字节、有的要 ``raise_for_status``），本模块按各实现的并集收敛。

接口约定：
  - ``FakeResponse``：``text`` / ``status_code`` / ``encoding`` / ``content`` 四个属性，
    ``json()`` 返回 ``json_body``（``json_error=True`` 时抛 ``ValueError``，模拟非 JSON
    响应体），``raise_for_status()`` 在给了 ``raise_status`` 时抛该异常（模拟 429/404）。
  - ``FakeClient``：``response`` 为默认响应（``by_url`` 未命中时用它；都未给则回 404，
    与「源侧无此路径」的既有语义一致）；``by_url`` 按 URL **后缀或包含**匹配分派，
    顺序即字典插入顺序；``error`` 非空时每次请求先抛该异常（模拟传输级失败）。
  - 记录：``calls``（每次请求一条 ``{"url", "params", "headers"}``，``params``/``headers``
    归一为空字典）、``posts``（``(url, data)`` 二元组）、``gets``（URL 字符串列表）。
"""

from __future__ import annotations

from typing import Any


class FakeResponse:
    """``httpx.Response`` 的最小替身。"""

    def __init__(
        self,
        text: str = "",
        status_code: int = 200,
        *,
        json_body: Any = None,
        raise_status: BaseException | None = None,
        encoding: str = "",
        content: bytes | None = None,
        json_error: bool = False,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.encoding = encoding
        self.content = text.encode(encoding or "utf-8") if content is None else content
        self._json_body = json_body
        self._json_error = json_error
        self._raise_status = raise_status

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("not json")
        return self._json_body

    def raise_for_status(self) -> None:
        if self._raise_status is not None:
            raise self._raise_status


class FakeClient:
    """``make_http_client()`` 的最小替身：按 URL 分派响应并记录请求。"""

    def __init__(
        self,
        response: FakeResponse | None = None,
        *,
        by_url: dict[str, FakeResponse] | None = None,
        error: BaseException | None = None,
    ) -> None:
        self._response = response
        self._by_url = dict(by_url or {})
        self._error = error
        self.calls: list[dict[str, Any]] = []
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.gets: list[str] = []

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        return False

    def _dispatch(self, url: str) -> FakeResponse:
        for suffix, response in self._by_url.items():
            if url.endswith(suffix) or suffix in url:
                return response
        return self._response if self._response is not None else FakeResponse(status_code=404)

    def get(
        self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None, **_kwargs
    ) -> FakeResponse:
        self.gets.append(url)
        self.calls.append({"url": url, "params": params or {}, "headers": headers or {}})
        if self._error is not None:
            raise self._error
        return self._dispatch(url)

    def post(
        self, url: str, data: dict[str, Any] | None = None, headers: dict[str, str] | None = None, **_kwargs
    ) -> FakeResponse:
        self.posts.append((url, dict(data or {})))
        self.calls.append({"url": url, "params": dict(data or {}), "headers": headers or {}})
        if self._error is not None:
            raise self._error
        return self._dispatch(url)
