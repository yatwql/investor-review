"""Web 入口与统一 JSON 错误处理的分支覆盖。

覆盖点：
  - ``python -m src.python.web`` 把 server.main() 的返回值交给 shell（退出码可观测）
  - server.py 的 ``__main__`` 块：退出码传递 / Ctrl+C 退 130 / 未处理异常退 2
  - ``create_app()`` 未注入 run_manager 时取全局单例，并绑定默认生成执行体
  - 413 / 500 错误处理器的中文 JSON 响应（上传超限、服务器内部错误）
"""

from __future__ import annotations

import runpy
from types import SimpleNamespace

import pytest

from src.python.web import server
from src.python.web.app import create_app

pytestmark = [pytest.mark.unit, pytest.mark.unit_web]


class TestWebModuleEntryPoint:
    """``__main__.py`` 必须把退出码传给 shell。"""

    def test_module_entry_propagates_exit_code(self, monkeypatch):
        monkeypatch.setattr(server, "main", lambda: 5)

        with pytest.raises(SystemExit) as exc:
            runpy.run_module("src.python.web", run_name="__main__")

        assert exc.value.code == 5


class TestServerMainBlock:
    """server.py 的 ``__main__`` 块：三条退出路径互不混淆。"""

    def _run_main_block(self, monkeypatch, preflight) -> SystemExit:
        monkeypatch.setattr("sys.argv", ["prog"])
        monkeypatch.setattr("src.python.core.logger.setup_logger", lambda: None)
        monkeypatch.setattr("src.python.core.logger.log_app_boundary", lambda *a, **k: None)
        monkeypatch.setattr("src.python.core.doctor.interpreter_preflight_error", preflight)
        with pytest.raises(SystemExit) as exc:
            runpy.run_path(server.__file__, run_name="__main__")
        return exc.value

    def test_main_return_code_becomes_exit_status(self, monkeypatch):
        """解释器预检失败让 main() 返回 1，进程退出码必须是 1（不是恒 0）。"""
        exc = self._run_main_block(monkeypatch, lambda: "缺 pandas")

        assert exc.code == 1

    def test_keyboard_interrupt_exits_130(self, monkeypatch):
        def _interrupt():
            raise KeyboardInterrupt

        exc = self._run_main_block(monkeypatch, _interrupt)

        assert exc.code == 130

    def test_unhandled_exception_exits_2(self, monkeypatch):
        def _boom():
            raise RuntimeError("启动失败")

        exc = self._run_main_block(monkeypatch, _boom)

        assert exc.code == 2


class TestCreateAppDefaults:
    """未注入 run_manager：取全局单例并补上默认生成执行体。"""

    def test_default_run_manager_gets_executor(self, monkeypatch):
        from src.python.web.run_generation import _run_generation

        manager = SimpleNamespace(executor=None)
        monkeypatch.setattr("src.python.web.runs.get_run_manager", lambda: manager)

        app = create_app()

        assert manager.executor is _run_generation
        assert app.config["MAX_CONTENT_LENGTH"] > 0


class TestErrorHandlers:
    """413 / 500 统一 JSON 错误响应。"""

    def _app(self):
        app = create_app(SimpleNamespace(executor=lambda *a, **k: None))
        app.config["PROPAGATE_EXCEPTIONS"] = False
        return app

    def test_upload_too_large_returns_413_json(self):
        from src.python.web.upload import _MAX_BYTES

        client = self._app().test_client()
        resp = client.post(
            "/api/upload",
            data=b"0" * (_MAX_BYTES + 1),
            content_type="multipart/form-data",
        )

        assert resp.status_code == 413
        assert resp.get_json()["error_code"] == "UPLOAD_TOO_LARGE"

    def test_unhandled_route_error_returns_500_json(self):
        app = self._app()

        @app.route("/__boom__")
        def _boom():
            raise RuntimeError("内部错误")

        resp = app.test_client().get("/__boom__")

        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "SERVER_ERROR"
