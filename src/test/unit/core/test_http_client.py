"""HTTP 客户端工厂单元测试。

测试目标：
  - _should_verify — SSL_VERIFY 环境变量解析
  - make_http_client — 客户端创建、verify 参数合并
  - post_with_deadline — 墙钟总超时（read 超时被服务端滴流骗过时的兜底放弃）

运行：
  pytest src/test/unit/core/test_http_client.py -v
"""

from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import httpx

from src.python.core.http_client import _should_verify, make_http_client, post_with_deadline
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestShouldVerify(unittest.TestCase):
    """_should_verify 环境变量解析测试。"""

    @patch("src.python.core.http_client.os.getenv")
    def test_default_true(self, mock_getenv):
        """默认值：SSL_VERIFY 未设置（走 getenv 的 default 分支）→ True。"""
        mock_getenv.side_effect = lambda _key, default=None: default
        self.assertTrue(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_explicit_true(self, mock_getenv):
        """显式设置 true → True。"""
        mock_getenv.return_value = "true"
        self.assertTrue(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_explicit_one(self, mock_getenv):
        """SSL_VERIFY=1 → True。"""
        mock_getenv.return_value = "1"
        self.assertTrue(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_explicit_yes(self, mock_getenv):
        """SSL_VERIFY=yes → True。"""
        mock_getenv.return_value = "yes"
        self.assertTrue(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_false(self, mock_getenv):
        """SSL_VERIFY=false → False。"""
        mock_getenv.return_value = "false"
        self.assertFalse(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_zero(self, mock_getenv):
        """SSL_VERIFY=0 → False。"""
        mock_getenv.return_value = "0"
        self.assertFalse(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_no(self, mock_getenv):
        """SSL_VERIFY=no → False。"""
        mock_getenv.return_value = "no"
        self.assertFalse(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_case_insensitive(self, mock_getenv):
        """大小写不敏感：True/TRUE/YES 均识别。"""
        for val in ("True", "TRUE", "YES", "Yes"):
            mock_getenv.return_value = val
            self.assertTrue(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_unknown_value_returns_false(self, mock_getenv):
        """未知值（不在 true/1/yes 中）→ False。"""
        mock_getenv.return_value = "maybe"
        self.assertFalse(_should_verify())

    @patch("src.python.core.http_client.os.getenv")
    def test_whitespace_stripped(self, mock_getenv):
        """前后空格自动去除。"""
        mock_getenv.return_value = "  true  "
        self.assertTrue(_should_verify())


class TestMakeHttpClient(unittest.TestCase):
    """make_http_client 集成测试。"""

    @patch("src.python.core.http_client.httpx.Client")
    @patch("src.python.core.http_client._SSL_VERIFY", True)
    def test_default_verify_true(self, mock_client_class):
        """未传 verify → 使用模块级 _SSL_VERIFY=True。"""
        make_http_client(timeout=30.0)
        _, kwargs = mock_client_class.call_args
        self.assertIs(kwargs["verify"], True)

    @patch("src.python.core.http_client.httpx.Client")
    @patch("src.python.core.http_client._SSL_VERIFY", False)
    def test_default_verify_false(self, mock_client_class):
        """未传 verify → 使用模块级 _SSL_VERIFY=False。"""
        make_http_client(timeout=30.0)
        _, kwargs = mock_client_class.call_args
        self.assertIs(kwargs["verify"], False)

    @patch("src.python.core.http_client.httpx.Client")
    @patch("src.python.core.http_client._SSL_VERIFY", True)
    def test_explicit_verify_overrides(self, mock_client_class):
        """显式传 verify=False 覆盖模块级 True。"""
        make_http_client(verify=False, timeout=30.0)
        _, kwargs = mock_client_class.call_args
        self.assertIs(kwargs["verify"], False)

    @patch("src.python.core.http_client.httpx.Client")
    def test_timeout_passed_through(self, mock_client_class):
        """timeout 参数透传给 httpx.Client。"""
        make_http_client(timeout=15.0)
        _, kwargs = mock_client_class.call_args
        self.assertEqual(kwargs["timeout"], 15.0)

    @patch("src.python.core.http_client.httpx.Client")
    def test_headers_passed_through(self, mock_client_class):
        """headers 参数透传。"""
        make_http_client(headers={"X-Test": "1"})
        _, kwargs = mock_client_class.call_args
        self.assertEqual(kwargs["headers"], {"X-Test": "1"})

    @patch("src.python.core.http_client.httpx.Client")
    def test_multiple_kwargs(self, mock_client_class):
        """多个参数同时传递。"""
        make_http_client(timeout=30.0, follow_redirects=True, headers={"X-T": "1"})
        _, kwargs = mock_client_class.call_args
        self.assertEqual(kwargs["timeout"], 30.0)
        self.assertTrue(kwargs["follow_redirects"])
        self.assertEqual(kwargs["headers"], {"X-T": "1"})

    def test_context_manager(self):
        """支持 with 语句（真实 httpx.Client）。"""
        with make_http_client(timeout=30.0) as client:
            self.assertFalse(client.is_closed)
        self.assertTrue(client.is_closed)


class TestPostWithDeadline(unittest.TestCase):
    """post_with_deadline — 墙钟总超时：read 超时被服务端滴流骗过时的兜底。

    回归场景（上游服务过载事故）：网关排队时配置的 read 超时未触发，
    单请求挂足服务端 900s 上限才返回，调用方故障切换迟滞十余分钟。
    """

    _URL = "https://api.example.com/v1/messages"

    def test_hung_post_abandoned_at_wall_clock(self) -> None:
        """服务端挂起 → 墙钟到点放弃并归一为 httpx.ReadTimeout。"""
        release = threading.Event()

        def _hung_post(*args: object, **kwargs: object) -> None:
            release.wait(10)  # 模拟服务端挂起：远超用例墙钟
            raise AssertionError("墙钟放弃后主线程不应再等待本 POST")

        mock_client = MagicMock()
        mock_client.post.side_effect = _hung_post
        start = time.monotonic()
        try:
            with self.assertRaises(httpx.ReadTimeout):
                post_with_deadline(mock_client, self._URL, {}, {}, 0.3)
        finally:
            release.set()
        self.assertLess(time.monotonic() - start, 5.0)

    def test_fast_post_result_passes_through(self) -> None:
        """快速完成的 POST 原样透传，墙钟不干扰正常路径。"""
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        self.assertIs(post_with_deadline(mock_client, self._URL, {}, {}, 5.0), mock_response)

    def test_post_exception_crosses_thread_unchanged(self) -> None:
        """线程内 httpx 异常原样上抛（包装不吞异常，分类层拿到原异常类型）。"""
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("connection refused")
        with self.assertRaises(httpx.ConnectError):
            post_with_deadline(mock_client, self._URL, {}, {}, 5.0)

    def test_nonpositive_timeout_skips_wall_clock(self) -> None:
        """timeout<=0 → 不设墙钟，保持纯 httpx 行为（直通调用）。"""
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        self.assertIs(post_with_deadline(mock_client, self._URL, {}, {}, 0), mock_response)
        mock_client.post.assert_called_once()


class TestTransportFactory:
    """传输层注入点（use_transport_factory）—— 数据源记录-回放的接入方式。"""

    def test_no_factory_means_no_transport_kwarg(self):
        """未安装工厂：不向 httpx.Client 传 transport，行为与无本机制时一致。"""
        from src.python.core import http_client as hc

        with patch("src.python.core.http_client.httpx.Client") as mock_client_class:
            hc.make_http_client(timeout=5.0)
            _, kwargs = mock_client_class.call_args
        assert "transport" not in kwargs

    def test_installed_factory_supplies_transport(self):
        """已安装工厂：其产物作为 transport 传入，其余参数不受影响。"""
        from src.python.core import http_client as hc

        marker = object()
        with patch("src.python.core.http_client.httpx.Client") as mock_client_class:
            with hc.use_transport_factory(lambda: marker):
                hc.make_http_client(timeout=7.0)
            _, kwargs = mock_client_class.call_args
        assert kwargs["transport"] is marker
        assert kwargs["timeout"] == 7.0

    def test_factory_returning_none_leaves_default_transport(self):
        """工厂返回 None：不传 transport（回落 httpx 默认传输）。"""
        from src.python.core import http_client as hc

        with patch("src.python.core.http_client.httpx.Client") as mock_client_class:
            with hc.use_transport_factory(lambda: None):
                hc.make_http_client()
            _, kwargs = mock_client_class.call_args
        assert "transport" not in kwargs

    def test_explicit_transport_beats_factory(self):
        """调用方显式传 transport 时以调用方为准（工厂不覆盖明确意图）。"""
        from src.python.core import http_client as hc

        explicit = object()
        with patch("src.python.core.http_client.httpx.Client") as mock_client_class:
            with hc.use_transport_factory(lambda: object()):
                hc.make_http_client(transport=explicit)
            _, kwargs = mock_client_class.call_args
        assert kwargs["transport"] is explicit

    def test_factory_restored_after_block(self):
        """退出 with 块后工厂还原（不污染后续客户端）。"""
        from src.python.core import http_client as hc

        assert hc._TRANSPORT_FACTORY is None
        with hc.use_transport_factory(lambda: None):
            assert hc._TRANSPORT_FACTORY is not None
        assert hc._TRANSPORT_FACTORY is None

    def test_nested_factories_restore_to_outer(self):
        """嵌套时内层退出还原到外层工厂，而非直接清空。"""
        from src.python.core import http_client as hc

        outer = lambda: None  # noqa: E731
        inner = lambda: None  # noqa: E731
        with hc.use_transport_factory(outer):
            with hc.use_transport_factory(inner):
                assert hc._TRANSPORT_FACTORY is inner
            assert hc._TRANSPORT_FACTORY is outer

    def test_factory_restored_after_exception(self):
        """块内抛异常也须还原工厂（否则测试间污染后续用例）。"""
        from src.python.core import http_client as hc

        with pytest.raises(RuntimeError):
            with hc.use_transport_factory(lambda: None):
                raise RuntimeError("boom")
        assert hc._TRANSPORT_FACTORY is None

    def test_make_transport_honors_module_ssl_policy(self):
        """make_transport 与 make_http_client 共用同一 SSL 策略。"""
        from src.python.core import http_client as hc

        with patch("src.python.core.http_client.httpx.HTTPTransport") as mock_transport:
            with patch("src.python.core.http_client._SSL_VERIFY", False):
                hc.make_transport()
            _, kwargs = mock_transport.call_args
        assert kwargs["verify"] is False

    def test_make_transport_explicit_verify_wins(self):
        """显式 verify 覆盖模块级策略。"""
        from src.python.core import http_client as hc

        with patch("src.python.core.http_client.httpx.HTTPTransport") as mock_transport:
            with patch("src.python.core.http_client._SSL_VERIFY", True):
                hc.make_transport(verify=False)
            _, kwargs = mock_transport.call_args
        assert kwargs["verify"] is False
