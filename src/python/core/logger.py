from __future__ import annotations

import logging
import os
import socket
import sys
from logging.handlers import RotatingFileHandler

from src.python.core.constants import PROJECT_ROOT
from src.python.core.ansi_colors import MAGENTA, RED, RESET, YELLOW

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
_LOGGER_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data/config/logger.json")
_DEFAULT_ROTATION_BYTES = 10 * 1024 * 1024
_DEFAULT_BACKUP_COUNT = 5
_DEFAULT_CONSOLE_COLOR = True
_DEFAULT_VIEWER_LEVEL = "INFO"
_DEFAULT_TAIL_LINES = 500
_VALID_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def _read_logger_config_file() -> dict:
    """读取 data/config/logger.json（JSONC）；缺失/损坏/版本不符 → 全默认。

    本模块属 core 层，不得导入 config 包；这里内联读取 + 轻量校验，面板侧另有
    ``config/_logging.py`` 提供同一范围表的保存拒绝与路径绝对化。
    """
    config = {
        "path": os.path.join("logs", "app.log"),
        "level": "INFO",
        "max_bytes": _DEFAULT_ROTATION_BYTES,
        "backup_count": _DEFAULT_BACKUP_COUNT,
        "console_level": "INFO",
        "console_color": _DEFAULT_CONSOLE_COLOR,
        "viewer_level": _DEFAULT_VIEWER_LEVEL,
        "tail_lines": _DEFAULT_TAIL_LINES,
    }
    if not os.path.exists(_LOGGER_CONFIG_PATH):
        return config
    try:
        from src.python.core.json_comments import loads

        with open(_LOGGER_CONFIG_PATH, encoding="utf-8-sig") as f:
            doc = loads(f.read())
    except Exception:  # noqa: BLE001 — 日志配置损坏不得阻断主流程
        return config
    if not isinstance(doc, dict):
        return config
    if doc.get("version") != 1:
        # 版本不符：告警后全默认（面板侧会明确提示重新生成）
        import warnings

        warnings.warn(
            f"logger.json 的 version={doc.get('version')!r} 不受支持（需 1），已使用默认日志配置；"
            "请删除该文件后重新生成",
            RuntimeWarning,
            stacklevel=2,
        )
        return config

    file_section = doc.get("file") or {}
    console = doc.get("console") or {}
    viewer = doc.get("viewer") or {}
    if isinstance(file_section.get("path"), str) and file_section["path"].strip():
        config["path"] = file_section["path"].strip()
    for key, section_key in (("level", ("file", "level")), ("console_level", ("console", "level"))):
        value = (doc.get(section_key[0]) or {}).get(section_key[1])
        if isinstance(value, str) and value.upper() in _VALID_LEVELS:
            config[key] = value.upper()
    viewer_level = viewer.get("default_level")
    if isinstance(viewer_level, str) and viewer_level.upper() in (*_VALID_LEVELS, "ALL"):
        config["viewer_level"] = viewer_level.upper()
    for key, value in (
        ("max_bytes", file_section.get("max_bytes")),
        ("backup_count", file_section.get("backup_count")),
        ("tail_lines", viewer.get("tail_lines")),
    ):
        if isinstance(value, int) and not isinstance(value, bool):
            config[key] = value
    if isinstance(console.get("color"), bool):
        config["console_color"] = console["color"]
    return config


def _apply_logger_config(config: dict) -> None:
    """把配置写入模块级生效值（路径绝对化；测试进程固定 test.log）。"""
    global _LOG_FILE, _LOG_MAX_BYTES, _LOG_BACKUP_COUNT, _CONSOLE_COLOR
    global _CONFIG_FILE_LEVEL, _CONFIG_CONSOLE_LEVEL
    path = config["path"]
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_ROOT, path)
    _LOG_FILE = os.path.join(_LOG_BASE, "test.log") if _is_pytest else _apply_env_log_path(path)
    _LOG_MAX_BYTES = int(config["max_bytes"])
    _LOG_BACKUP_COUNT = int(config["backup_count"])
    _CONSOLE_COLOR = bool(config["console_color"])
    _CONFIG_FILE_LEVEL = str(config["level"])
    _CONFIG_CONSOLE_LEVEL = str(config["console_level"])


def reload_logger_config() -> dict:
    """重新读取 logger.json 并刷新生效值（面板保存后调用）。返回配置副本。"""
    config = _read_logger_config_file()
    _apply_logger_config(config)
    return dict(config)


_LOG_FILE_LEVEL_ENV = "INVEST_LOG_FILE_LEVEL"
_LOG_CONSOLE_LEVEL_ENV = "INVEST_LOG_CONSOLE_LEVEL"
_CONFIG_FILE_LEVEL = "INFO"
_CONFIG_CONSOLE_LEVEL = "INFO"


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


#: LLM 实际调用行的统一日志前缀——报告运行时滚屏日志里唯一“花钱的调用”信号。
#: 新增 LLM 调用日志须以此前缀开头，才享受控制台品红与日志查看器同款标注。
_LLM_CALL_TAG = "[LLM]"


def is_llm_call_message(message: str) -> bool:
    """消息是否为 LLM 实际调用行（前缀 ``[LLM]``；``[LLM 预检]`` 等判定行不算）。"""
    return str(message).lstrip().startswith(_LLM_CALL_TAG)


class _ColoredFormatter(logging.Formatter):
    """按日志级别着色消息内容的格式器（仅限控制台；``use_color=False`` 时纯文本）。

    两级优先：级别色（WARNING 黄 / ERROR 红）先取，状态语义不被覆盖；
    其余 INFO 行若命中 :func:`is_llm_call_message`，用品红标记——一次报告运行里
    这些行就是“真实 LLM API 调用发生了”，在进度行中间需一眼可辨。
    """

    _LEVEL_COLORS = {
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED,
    }

    def __init__(self, fmt: str | None = None, *, use_color: bool = True) -> None:
        super().__init__(fmt)
        self._use_color = use_color

    def _message_color(self, record: logging.LogRecord) -> str:
        """消息着色：级别色优先（含无色模式下的「空色」），其次 LLM 调用品红。"""
        if not self._use_color:
            return ""
        if record.levelno in self._LEVEL_COLORS:
            return self._LEVEL_COLORS[record.levelno]
        return MAGENTA if is_llm_call_message(record.getMessage()) else ""

    def format(self, record: logging.LogRecord) -> str:
        color = self._message_color(record)
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


#: 生效值（模块级；reload_logger_config 可刷新）
_LOG_MAX_BYTES = _DEFAULT_ROTATION_BYTES
_LOG_BACKUP_COUNT = _DEFAULT_BACKUP_COUNT
_CONSOLE_COLOR = _DEFAULT_CONSOLE_COLOR
_LOG_FILE = os.path.join(_LOG_BASE, "test.log") if _is_pytest else os.path.join(_LOG_BASE, "app.log")

# ── 非真实运行（演示截图 / 性能基准）的日志隔离 ──────────────
# 演示 run 与真实 run 写同一个 app.log 时，演示持仓的告警（无行情/缺凭据/陈旧锁）会
# 混进真实运行的日志分析，只能靠「读了哪个持仓文件」事后反推识别。故两条通道：
#   INVEST_LOG_PATH=<文件>     → 改落盘文件（演示落 demo/logs/app.log，不污染真实日志）
#   INVEST_RUN_CONTEXT=<标签>  → 启动时打一行上下文标记（万一某子进程漏传 env，
#                                标签行能把整段运行归属出来）
_LOG_PATH_ENV = "INVEST_LOG_PATH"
_RUN_CONTEXT_ENV = "INVEST_RUN_CONTEXT"


def get_run_context() -> str:
    """当前进程的运行上下文标签（真实运行为空串；演示/基准为 ``demo`` / ``perf``）。"""
    return os.environ.get(_RUN_CONTEXT_ENV, "").strip()


def _apply_env_log_path(path: str) -> str:
    """环境变量指定的日志文件（相对路径按项目根解析）；测试进程固定 test.log。"""
    if _is_pytest:
        return path
    override = os.environ.get(_LOG_PATH_ENV, "").strip()
    if not override:
        return path
    return override if os.path.isabs(override) else os.path.join(PROJECT_ROOT, override)


_apply_logger_config(_read_logger_config_file())


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

    file_level = _resolve_level(_LOG_FILE_LEVEL_ENV, _CONFIG_FILE_LEVEL)
    console_level = _resolve_level(_LOG_CONSOLE_LEVEL_ENV, _CONFIG_CONSOLE_LEVEL)
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
    console_handler.setFormatter(_ColoredFormatter(_LOG_FORMAT, use_color=_CONSOLE_COLOR and bool(RESET)))
    logger.addHandler(console_handler)

    # ---- 文件 Handler（自动轮转；目录不可写时降级为仅控制台） ----
    try:
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
    except OSError as e:
        logger.warning("日志文件不可写（%s），本次仅输出到控制台: %s", _LOG_FILE, e)

    # 上下文标记：一行钉住「本次运行属于演示/基准而非真实报告」，即使某子进程
    # 漏传 INVEST_LOG_PATH 落回了真实日志，也能靠这行把整段输出归属出去。
    _context = get_run_context()
    if _context:
        logger.info("[run] 运行上下文=%s | 日志文件: %s", _context, _LOG_FILE)

    return logger


def get_machine_ip() -> str:
    """获取本机 IP 地址，失败时返回 'unknown'。"""
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "unknown"


def log_app_boundary(event: str, mode: str) -> None:
    """记录应用启动/关闭事件到日志。

    Args:
        event: "启动" 或 "关闭"
        mode: "CLI模式" 或 "TUI模式"
    """
    from src.python.core.constants import APP_NAME, APP_VERSION

    ip = get_machine_ip()
    logging.getLogger("invest").info(
        "应用%s | %s v%s | %s | 主机 IP: %s",
        event,
        APP_NAME,
        APP_VERSION,
        mode,
        ip,
    )
