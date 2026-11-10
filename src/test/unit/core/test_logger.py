"""日志模块（core/logger）关闭竞态回归测试。

覆盖：进程退出阶段（模块级 atexit 注册的关闭日志）流已关闭时，
_ClosedStreamSilentHandler 静默降级，不产生 `--- Logging error ---` 噪声。

回归背景：全量测试（mode all）进程退出时，tui.py 模块级
`atexit.register(log_app_boundary, "关闭", "TUI模式")` 触发的关闭日志
在 pytest 关闭 sys.stderr 后执行，StreamHandler emit 抛
`ValueError: I/O operation on closed file`，logging 默认 handleError
打印 `--- Logging error ---` 噪声。修复：console handler 换用
_ClosedStreamSilentHandler，仅对 "closed file" 竞态静默。
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
from unittest import mock

import pytest

import src.python.core.logger as log_mod

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]


class TestClosedStreamSilentHandler:
    """流已关闭时的静默降级回归测试。"""

    @staticmethod
    def _make_record() -> logging.LogRecord:
        return logging.LogRecord(
            name="invest",
            level=logging.INFO,
            pathname="test_logger.py",
            lineno=1,
            msg="关闭日志",
            args=(),
            exc_info=None,
        )

    def test_emit_after_stream_closed_no_logging_error(self):
        """stream 关闭后 emit：不打印 logging error（静默降级、不抛异常）。"""
        buf = io.StringIO()
        handler = log_mod._ClosedStreamSilentHandler(buf)
        handler.setFormatter(logging.Formatter("%(message)s"))
        buf.close()  # 模拟进程退出阶段 stream 被关闭

        # StreamHandler.emit 内部 try/except → handleError，本类对
        # "closed file" 静默返回，不会打印 `--- Logging error ---`
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            handler.emit(self._make_record())
        # 真正要守的是「未委托父类打印 --- Logging error ---」（仅不抛异常兜不住该回归）
        assert "Logging error" not in err.getvalue()

    def test_handle_error_silent_for_closed_file(self):
        """handleError 对 "closed file" 异常静默（不委托父类打印路径）。"""
        handler = log_mod._ClosedStreamSilentHandler(io.StringIO())
        with mock.patch.object(logging.StreamHandler, "handleError") as mock_super:
            try:
                raise ValueError("I/O operation on closed file")
            except ValueError:
                handler.handleError(self._make_record())
            mock_super.assert_not_called()

    def test_handle_error_passthrough_for_other_errors(self):
        """handleError 对非 "closed file" 错误照常委托父类。"""
        handler = log_mod._ClosedStreamSilentHandler(io.StringIO())
        with mock.patch.object(logging.StreamHandler, "handleError") as mock_super:
            try:
                raise RuntimeError("boom")
            except RuntimeError:
                handler.handleError(self._make_record())
            mock_super.assert_called_once()

    def test_console_handler_is_silent_handler(self):
        """setup_logger 控制台 handler 为 _ClosedStreamSilentHandler。"""
        logger = log_mod.setup_logger("invest_test_console_type")
        console = next(h for h in logger.handlers if isinstance(h, logging.StreamHandler))
        assert isinstance(console, log_mod._ClosedStreamSilentHandler)
        # 清理，避免污染其他测试
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)


class TestLogLevelConfig:
    """日志级别可由环境变量配置：默认 INFO，DEBUG 按需放开；非法值回落默认。"""

    @staticmethod
    def _fresh(name: str, monkeypatch, tmp_path):
        monkeypatch.setattr(log_mod, "_LOG_FILE", str(tmp_path / f"{name}.log"))
        return log_mod.setup_logger(name)

    @staticmethod
    def _levels(logger):
        file_levels = [h.level for h in logger.handlers if hasattr(h, "baseFilename")]
        console_levels = [h.level for h in logger.handlers if not hasattr(h, "baseFilename")]
        return file_levels[0], console_levels[0]

    def test_default_levels_are_info(self, monkeypatch, tmp_path):
        monkeypatch.delenv(log_mod._LOG_FILE_LEVEL_ENV, raising=False)
        monkeypatch.delenv(log_mod._LOG_CONSOLE_LEVEL_ENV, raising=False)
        file_level, console_level = self._levels(self._fresh("invest_lvl_default", monkeypatch, tmp_path))
        assert (file_level, console_level) == (logging.INFO, logging.INFO)

    def test_file_level_env_enables_debug(self, monkeypatch, tmp_path):
        monkeypatch.setenv(log_mod._LOG_FILE_LEVEL_ENV, "debug")
        logger = self._fresh("invest_lvl_debug", monkeypatch, tmp_path)
        file_level, console_level = self._levels(logger)
        assert file_level == logging.DEBUG
        assert console_level == logging.INFO

    def test_invalid_level_falls_back(self, monkeypatch, tmp_path):
        monkeypatch.setenv(log_mod._LOG_FILE_LEVEL_ENV, "verbose-ish")
        with pytest.warns(RuntimeWarning, match="不是合法日志级别"):
            file_level, _ = self._levels(self._fresh("invest_lvl_bad", monkeypatch, tmp_path))
        assert file_level == logging.INFO


class TestLlmCallColor:
    """LLM 实际调用行的品红标注：前缀判据 + 级别色优先。"""

    @staticmethod
    def _format(level: int, msg: str, monkeypatch, *, use_color: bool = True) -> str:
        monkeypatch.setattr(log_mod, "MAGENTA", "\033[95m")
        monkeypatch.setattr(log_mod, "RESET", "\033[0m")
        monkeypatch.setattr(
            log_mod._ColoredFormatter,
            "_LEVEL_COLORS",
            {logging.WARNING: "\033[93m", logging.ERROR: "\033[91m", logging.CRITICAL: "\033[91m"},
        )
        formatter = log_mod._ColoredFormatter("%(message)s", use_color=use_color)
        record = logging.LogRecord("invest", level, __file__, 1, msg, (), None)
        return formatter.format(record)

    def test_prefix_judgement_excludes_precheck_lines(self):
        assert log_mod.is_llm_call_message("  [LLM] 全球政经局势: 输入 1,024 + 输出 512")
        assert log_mod.is_llm_call_message("[LLM] 正在调用 全球政经局势（2 批未缓存，每批最多 50 条）...")
        assert not log_mod.is_llm_call_message("[LLM 预检] 基础模块命中 4/4：全球政经局势")
        assert not log_mod.is_llm_call_message("LLM 缓存命中: abc123")
        assert not log_mod.is_llm_call_message("正在获取行情数据...")

    def test_llm_call_line_is_magenta(self, monkeypatch):
        out = self._format(logging.INFO, "  [LLM] 全球政经局势: 输入 1,024 + 输出 512", monkeypatch)
        assert out == "\033[95m  [LLM] 全球政经局势: 输入 1,024 + 输出 512\033[0m"

    def test_llm_call_warning_keeps_level_color(self, monkeypatch):
        out = self._format(logging.WARNING, "[LLM] 调用重试中", monkeypatch)
        assert out == "\033[93m[LLM] 调用重试中\033[0m"

    def test_plain_line_stays_uncolored(self, monkeypatch):
        assert self._format(logging.INFO, "正在获取行情数据...", monkeypatch) == "正在获取行情数据..."

    def test_no_color_mode_skips_llm_highlight(self, monkeypatch):
        out = self._format(logging.INFO, "[LLM] x", monkeypatch, use_color=False)
        assert out == "[LLM] x"


class TestRunContextIsolation:
    """演示/基准运行的日志隔离：改落盘路径 + 上下文标记行。"""

    def test_env_log_path_overrides_file(self, monkeypatch):
        """``INVEST_LOG_PATH`` 指定时日志不落真实 app.log。"""
        monkeypatch.setattr(log_mod, "_is_pytest", False)
        monkeypatch.setenv(log_mod._LOG_PATH_ENV, "docs/tmp/demo-app.log")
        assert log_mod._apply_env_log_path("logs/app.log") == os.path.join(
            log_mod.PROJECT_ROOT, "docs/tmp/demo-app.log"
        )

    def test_env_log_path_absolute_kept_verbatim(self, monkeypatch, tmp_path):
        monkeypatch.setattr(log_mod, "_is_pytest", False)
        monkeypatch.setenv(log_mod._LOG_PATH_ENV, str(tmp_path / "x.log"))
        assert log_mod._apply_env_log_path("logs/app.log") == str(tmp_path / "x.log")

    def test_no_env_keeps_default_path(self, monkeypatch):
        monkeypatch.setattr(log_mod, "_is_pytest", False)
        monkeypatch.delenv(log_mod._LOG_PATH_ENV, raising=False)
        assert log_mod._apply_env_log_path("logs/app.log") == "logs/app.log"

    def test_pytest_process_ignores_env_override(self, monkeypatch):
        """测试进程固定 test.log：隔离变量不得把测试日志写到别处。"""
        monkeypatch.setattr(log_mod, "_is_pytest", True)
        monkeypatch.setenv(log_mod._LOG_PATH_ENV, "docs/tmp/demo-app.log")
        assert log_mod._apply_env_log_path("logs/test.log") == "logs/test.log"

    def test_run_context_reads_env(self, monkeypatch):
        monkeypatch.setenv(log_mod._RUN_CONTEXT_ENV, "demo")
        assert log_mod.get_run_context() == "demo"
        monkeypatch.setenv(log_mod._RUN_CONTEXT_ENV, "  ")
        assert log_mod.get_run_context() == ""

    def test_context_marker_logged_once(self, monkeypatch, tmp_path):
        """启动时打一行上下文标记；重复 setup_logger 不重复打。"""
        monkeypatch.setenv(log_mod._RUN_CONTEXT_ENV, "demo")
        monkeypatch.setattr(log_mod, "_LOG_FILE", str(tmp_path / "demo.log"))
        logger = log_mod.setup_logger("invest_context_probe")
        try:
            logger.info("占位")
            text = (tmp_path / "demo.log").read_text(encoding="utf-8")
            marker = [line for line in text.splitlines() if "运行上下文" in line]
            assert len(marker) == 1, "上下文标记应恰好一行（每个进程一次）"
            assert "demo" in marker[0]
        finally:
            logger.handlers.clear()
