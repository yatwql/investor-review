from __future__ import annotations

import logging
import os
import socket
import sys
from logging.handlers import RotatingFileHandler

from src.python.core.constants import PROJECT_ROOT
from src.python.core.ansi_colors import RED, RESET, YELLOW

# 日志文件路径（始终以项目根目录为基准，不受 CWD 影响）
_LOG_BASE = os.path.join(PROJECT_ROOT, "logs")
# 检测方式（按可靠性降序）：
#   1. INVEST_RUNNING_TESTS 环境变量（test-runner.py 显式设置，xdist worker 继承）
#   2. PYTEST_CURRENT_TEST 环境变量（pytest 自身设置）
#   3. sys.modules 中已加载 pytest（xdist worker 进程，pytest 先于用户代码导入）
#   4. sys.argv[:3] 包含 "pytest"（直接 python -m pytest）
_is_pytest = (
    os.environ.get("INVEST_RUNNING_TESTS") == "1"
    or bool(os.environ.get("PYTEST_CURRENT_TEST"))
    or "pytest" in sys.modules
    or any("pytest" in arg.lower() for arg in sys.argv[:3])
)
_LOG_FILE = os.path.join(_LOG_BASE, "test.log") if _is_pytest else os.path.join(_LOG_BASE, "app.log")

# 日志格式
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

# 日志轮转配置
_LOG_MAX_BYTES = 10 * 1024 * 1024  # 单文件最大 10 MB
_LOG_BACKUP_COUNT = 5  # 保留 5 个备份

# ── 级别可配（默认 INFO；排障时按需开 DEBUG） ──────────────
# 背景：文件 handler 长期固定 DEBUG，逐次取数的追踪行（市场时段/缓存命中）占日志
# 九成以上，10MB 轮转只能留约 6 天，真正告警被埋。默认收敛到 INFO，需要追踪时
# 用环境变量单独放开，不改代码、不改配置：
#   INVEST_LOG_FILE_LEVEL=DEBUG      （文件）
#   INVEST_LOG_CONSOLE_LEVEL=DEBUG   （控制台）
_LOG_FILE_LEVEL_ENV = "INVEST_LOG_FILE_LEVEL"
_LOG_CONSOLE_LEVEL_ENV = "INVEST_LOG_CONSOLE_LEVEL"
_DEFAULT_FILE_LEVEL = "INFO"
_DEFAULT_CONSOLE_LEVEL = "INFO"


def _resolve_level(env_name: str, default_name: str) -> int:
    """环境变量指定的级别；缺省/非法一律回落默认档（非法值只提示一次）。"""
    raw = os.environ.get(env_name, "").strip().upper()
    default = getattr(logging, default_name)
    if not raw:
        return default
    level = getattr(logging, raw, None)
    if isinstance(level, int):
        return level
    import warnings

    warnings.warn(
        f"{env_name}={raw!r} 不是合法日志级别（DEBUG/INFO/WARNING/ERROR），按 {default_name} 处理",
        RuntimeWarning,
        stacklevel=2,
    )
    return default


# ── 控制台彩色日志格式器 ────────────────────────────────────
# 仅控制台 handler 应用颜色，文件 handler 保持纯文本


class _ColoredFormatter(logging.Formatter):
    """按日志级别着色消息内容的格式器（仅限控制台）。"""

    _LEVEL_COLORS = {
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self._LEVEL_COLORS.get(record.levelno, "")
        if color:
            original = record.msg
            record.msg = f"{color}{record.msg}{RESET}"
            result = super().format(record)
            record.msg = original
            return result
        return super().format(record)


class _ClosedStreamSilentHandler(logging.StreamHandler):
    """控制台 Handler — 对「流已关闭」写失败静默降级。

    进程退出阶段（模块级 atexit 注册的关闭日志）可能发生在宿主/测试
    框架关闭 sys.stderr 之后，此时 emit 抛 ``ValueError: I/O operation
    on closed file``，logging 默认经 handleError 打印 ``--- Logging error ---``
    噪声。本类仅对该退出竞态静默，其余日志错误照常由父类报告。
    """

    def handleError(self, record: logging.LogRecord) -> None:
        exc_value = sys.exc_info()[1]
        if isinstance(exc_value, (ValueError, OSError)) and "closed file" in str(exc_value):
            return  # 流已关闭属退出竞态，静默降级
        super().handleError(record)


def setup_logger(name: str = "invest") -> logging.Logger:
    """
    初始化并返回 logger。

    配置控制台输出和自动轮转文件输出两种 handler，避免重复添加。
    自动创建 logs/ 目录（如果不存在）。
    使用 RotatingFileHandler，单文件超过 10 MB 自动切割，保留 5 份备份。

    Args:
        name: logger 名称，默认 "invest"

    Returns:
        配置好的 logging.Logger 实例
    """
    logger = logging.getLogger(name)

    # 如果已经配置过 handler，直接返回
    if logger.handlers:
        return logger

    file_level = _resolve_level(_LOG_FILE_LEVEL_ENV, _DEFAULT_FILE_LEVEL)
    console_level = _resolve_level(_LOG_CONSOLE_LEVEL_ENV, _DEFAULT_CONSOLE_LEVEL)
    # 根 logger 保持 DEBUG，由两个 handler 各自过滤：这样显式设置 handler/根级别的
    # 调试工具（caplog、临时 handler）仍能拿到 DEBUG 记录，默认落盘范围不受影响
    logger.setLevel(logging.DEBUG)

    # 创建日志格式器
    formatter = logging.Formatter(_LOG_FORMAT)

    # ---- 控制台 Handler（彩色输出） ----
    # 用 _ClosedStreamSilentHandler：进程退出阶段（atexit）流可能已关闭，
    # 对 "closed file" 静默降级，避免 `--- Logging error ---` 噪声。
    console_handler = _ClosedStreamSilentHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(_ColoredFormatter(_LOG_FORMAT))
    logger.addHandler(console_handler)

    # ---- 文件 Handler（自动轮转） ----
    log_dir = os.path.dirname(_LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)

    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def _get_machine_ip() -> str:
    """获取本机 IP 地址，失败时返回 'unknown'。"""
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "unknown"


# 公开 API：渠道层/展示层统一使用此名（私有名保留供既有内部引用）
def get_machine_ip() -> str:
    """公开 API（转发包装：内部实现 ``_get_machine_ip`` 可被测试 patch，实时生效）。"""
    return _get_machine_ip()


def log_app_boundary(event: str, mode: str) -> None:
    """记录应用启动/关闭事件到日志。

    Args:
        event: "启动" 或 "关闭"
        mode: "CLI模式" 或 "TUI模式"
    """
    from src.python.core.constants import APP_NAME, APP_VERSION

    ip = _get_machine_ip()
    logging.getLogger("invest").info(
        "应用%s | %s v%s | %s | 主机 IP: %s",
        event,
        APP_NAME,
        APP_VERSION,
        mode,
        ip,
    )
