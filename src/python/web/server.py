#!/usr/bin/env python3
"""Web 服务主入口 — sys.path 注入 + main() + 端口检测 + app.run。

启动方式：
  python -m src.python.web             # 模块入口（对齐 cli/tui）
  python src/python/web/server.py      # 直接执行（launch.sh web）

参数：
  --host 默认本机回环    监听地址（默认仅本机；局域网访问显式传全零监听地址）
  --port 8000        监听端口
  --config PATH      备用配置文件路径（默认 data/config/config.json）

启动防护：
  端口占用检测——占用则报错并提示换端口，避免服务静默失败/多实例混用产物。
  output_dir 写锁检测——被其他入口占用则警告，防止多进程共享输出目录互相覆盖产物。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import time

# 确保项目根目录在 sys.path 中（支持直接执行 python src/python/web/server.py）
_src_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(_src_dir)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.python.config import resolve_output_dir
from src.python.core.constants import APP_NAME

logger = logging.getLogger("invest")

# output_dir 写锁文件名（点文件：不参与 YYYYMMDD 归档扫描与历史枚举）
OUTPUT_DIR_LOCK_FILE = ".investor_output.lock"

#: 锁文件无 pid 信息时的陈旧阀值（秒）：旧格式/半写的锁超过这个年龄按残留处理
_LOCK_STALE_SECONDS = 12 * 3600


def _output_dir_lock_path(output_dir: str) -> str:
    """返回 output_dir 写锁文件路径。"""
    return os.path.join(output_dir, OUTPUT_DIR_LOCK_FILE)


def _read_lock_payload(lock_path: str) -> dict:
    """读锁文件载荷；不可读/非对象一律当空载荷（陈旧判据自行降级到文件年龄）。"""
    try:
        with open(lock_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _pid_alive(pid: int) -> bool | None:
    """pid 是否存活；无法可靠判定时返回 ``None``（调用方退化为文件年龄判据）。

    **Windows 上绝不能用 ``os.kill(pid, 0)`` 探测**：该 API 在 Windows 对非控制台
    信号直接走 ``TerminateProcess``（sig 被当作退出码）——探测即等于系死持有锁的进程。
    改用 ``OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)`` 只看句柄能否打开。

    Args:
        pid: 目标进程号。

    Returns:
        True（存活）/ False（已退出）/ None（无法判定）。
    """
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:  # noqa: BLE001 — 探测失败不得让启动防护报错
            return None
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True  # 进程存在、属其它用户 —— 视为仍占用
    except OSError:
        return False
    return True


def _lock_staleness(lock_path: str) -> str:
    """锁文件陈旧判据（返回空串 = 仍然有效）。

    只判「存在」会把崩溃残留锁（kill -9 / 容器重启 / 演示工作区旧锁）当成持续占用：
    实测一个 4 天前的残留锁让每次启动都刷一条「可能正被其他入口占用」的告警，
    既误报又让人对真实抢占型告警脱敏。两条判据：

    1. 锁内 pid 已不存在 → 持有者已退出；
    2. pid 无法判定，或锁内无 pid（旧格式/半写）→ 文件超过 ``_LOCK_STALE_SECONDS``
       未更新才判残留（存活持有者年龄再大也不接管）。

    Args:
        lock_path: 锁文件路径。

    Returns:
        陈旧原因（用于日志）；仍有效时为空串。
    """
    payload = _read_lock_payload(lock_path)
    pid = payload.get("pid")
    if isinstance(pid, int) and pid > 0:
        alive = _pid_alive(pid)
        if alive is False:
            return f"持有进程 {pid} 已不存在"
        if alive is True:
            return ""
    try:
        age = os.path.getmtime(lock_path)
    except OSError:
        return ""
    idle = time.time() - age
    if idle > _LOCK_STALE_SECONDS:
        return f"锁文件 {idle / 3600:.1f} 小时未更新（pid 无法确认）"
    return ""


def _is_output_dir_locked(output_dir: str) -> bool:
    """output_dir 是否已被其他入口**有效**占用（残留锁不算）。"""
    lock_path = _output_dir_lock_path(output_dir)
    if not os.path.exists(lock_path):
        return False
    return not _lock_staleness(lock_path)


def _acquire_output_dir_lock(output_dir: str) -> str | None:
    """原子创建 output_dir 写锁文件（O_CREAT|O_EXCL，避免多进程抢占竞态）。

    Args:
        output_dir: 报告输出根目录（不存在则尝试创建）。

    Returns:
        获取成功返回锁文件路径；锁已存在、目录不可写或创建失败返回 None。
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError:
        return None
    lock_path = _output_dir_lock_path(output_dir)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError:
        # 扣锁失败：先判陈旧残留——残留锁不应永久占据输出目录
        stale = _lock_staleness(lock_path)
        if not stale:
            return None
        logger.info("清理陈旧输出目录锁（%s）: %s", stale, lock_path)
        try:
            os.remove(lock_path)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError:
            return None
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"entry": "web", "pid": os.getpid()}, f, ensure_ascii=False)
    return lock_path


def _release_output_dir_lock(lock_path: str) -> None:
    """释放 output_dir 写锁（删除锁文件，删除失败静默忽略）。"""
    try:
        os.remove(lock_path)
    except OSError:
        pass


def ensure_output_dir_lock(output_dir: str) -> str | None:
    """检测并获取 output_dir 写锁。

    多进程（多开 web、或 web 与 TUI/CLI 并行）共享同一 output_dir 会互相覆盖
    最新版产物——启动时原子抢占写锁：抢占成功返回锁路径（调用方退出时须释放）；
    锁已被其他入口持有则记录警告并返回 None（不阻塞启动，产物竞态交由用户决策）。

    Args:
        output_dir: 报告输出根目录（config 已绝对化）。

    Returns:
        成功抢占返回锁文件路径；被占用或创建失败返回 None。
    """
    lock_path = _acquire_output_dir_lock(output_dir)
    if lock_path is not None:
        return lock_path
    if _is_output_dir_locked(output_dir):
        logger.warning(
            "输出目录 %s 存在锁文件 %s —— 该输出目录可能正被其他入口占用，产物可能互相覆盖",
            output_dir,
            OUTPUT_DIR_LOCK_FILE,
        )
    else:
        logger.warning("输出目录 %s 写锁创建失败，跳过锁检测（产物竞态风险不再提示）", output_dir)
    return None


def _port_in_use(host: str, port: int) -> bool:
    """检测端口是否已被占用（bind 探测，立即释放）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return False
        except OSError:
            return True


def main() -> int:
    """Web 服务主入口。"""
    from src.python.core.logger import log_app_boundary, setup_logger

    parser = argparse.ArgumentParser(
        prog="investor-review-web",
        description=f"{APP_NAME} — 轻量 Web 模式",
        epilog="示例: python -m src.python.web --host 127.0.0.1 --port 8000",
    )
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1；局域网访问显式用 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    parser.add_argument("--config", metavar="PATH", help="备用配置文件路径（默认: data/config/config.json）")
    args = parser.parse_args()

    setup_logger()
    log_app_boundary("启动", "Web模式")

    from src.python.config import init_config

    init_config(config_path=args.config)

    # 端口占用检测：占用则报错并提示换端口，避免多实例混用产物
    if _port_in_use(args.host, args.port):
        logger.error("端口 %s:%d 已被占用，请换端口（--port）后重试", args.host, args.port)
        return 2

    # output_dir 写锁：被其他入口占用则警告（防止多进程共享输出目录互相覆盖产物）

    output_dir = resolve_output_dir()
    output_lock = ensure_output_dir_lock(output_dir)

    try:
        from src.python.web.app import create_app
        from src.python.web.runs import get_run_manager
        from src.python.web.upload import cleanup_all

        run_manager = get_run_manager()
        app = create_app(run_manager)

        # 启动时清理全部残留上传文件（§6.1：残留由启动清理兜底）
        cleanup_all()

        # 内置定时生成调度（缺省关闭；线程每间隔重读配置，面板改配置即生效）
        from src.python.web.scheduler import SchedulerService

        SchedulerService(run_manager).start()

        if args.host in ("0.0.0.0", "::"):
            logger.warning("Web 服务监听 %s —— 局域网可访问，请仅限可信网络（无内建认证）", args.host)
        logger.info("Web 服务已启动: http://127.0.0.1:%d （Ctrl+C 退出）", args.port)
        # 生成线程 daemon=True：Ctrl+C 时进程可正常退出（进行中任务丢弃）
        app.run(host=args.host, port=args.port, threaded=True)
        return 0
    finally:
        if output_lock is not None:
            _release_output_dir_lock(output_lock)


if __name__ == "__main__":
    from src.python.core.logger import log_app_boundary

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log_app_boundary("关闭", "Web模式")
        sys.exit(130)
    except Exception:
        logger.exception("Web 未处理异常")
        log_app_boundary("关闭", "Web模式")
        sys.exit(2)
