"""Web 只读观测类路由 — 数据源健康 / 系统自检 / 运行日志 / 健康历史。

本模块只承载「读现状」的四条 GET 路由与其短缓存；写侧与报告生成路由在
``web.handlers``。响应信封原语在 ``handlers._ok`` / ``handlers._err``，此处按
函数内延迟导入取用——本模块不反向依赖路由注册，两模块不成环。

缓存口径（与拆分前逐字节一致）：
  - 健康探测 60s 缓存，``?fresh=1`` 强制重测（用户主动动作不计入缓存污染）；
  - 健康历史每次读文件（``summarize_health_history`` 自身廉价），不设缓存。
"""

from __future__ import annotations

import logging
import threading
import time

from flask import request

logger = logging.getLogger("invest")

# 健康探测短缓存——防频繁轮询重复真实探测。
# 并发边界：server 为 threaded=True，读写由同一把锁保护——锁只保护「读缓存/
# 写缓存」两段，真实计算在锁外；两请求同时 miss 时可能重复计算一次（本地
# 单人 Web 的低风险余量，不引入检查时间内串行化代价）。
_health_cache: dict = {"ts": 0.0, "data": None}
_render_cache_lock = threading.Lock()


def _handle_health():
    """GET /api/health — 数据源实时探测（60s 缓存，``?fresh=1`` 强制重测）。"""
    from src.python.core.check_sources import run_health_checks
    from src.python.web.handlers import _ok

    fresh = request.args.get("fresh") == "1"
    now = time.time()
    if not fresh:
        with _render_cache_lock:
            if _health_cache["data"] is not None and now - _health_cache["ts"] < 60:
                return _ok(_health_cache["data"])
    # 预算取 core.doctor 的 Web 档（低于前端 /api/health 的 15s abort 留余量；
    # 未完成项由 run_health_checks 标记"超时"返回，避免整接口超时被前端判失败）
    from src.python.core.doctor import NETWORK_TIMEOUT_WEB

    results = run_health_checks(max_timeout=NETWORK_TIMEOUT_WEB)
    with _render_cache_lock:
        _health_cache["ts"] = now
        _health_cache["data"] = results
    return _ok(results)


def _handle_doctor():
    """GET /api/doctor — 系统自检（恒上屏，无开关）。

    查询参数：
      network — ``0`` 跳过数据源联网检查（默认 1，含网络检查）
      timeout — 网络检查预算秒数（缺省/下限/上限口径全部取自 ``core.doctor``）

    与 /api/health 的分工：health 只探测数据源；doctor 还覆盖环境/配置/目录，
    故不与其共享缓存（doctor 的本地项廉价，而与 health 的预算不同）。

    Returns:
        {results: [...], ok_count: int, bad_count: int}
        每项含 group / label / ok / message / hint。
    """
    from src.python.core.doctor import NETWORK_TIMEOUT_CEILING, NETWORK_TIMEOUT_WEB, normalize_network_timeout
    from src.python.core.doctor import run_doctor_checks, summarize_doctor_results
    from src.python.web.handlers import _ok

    include_network = request.args.get("network", "1") != "0"
    # 预算默认/下限/上限口径全部来自 core.doctor（渠道不另立数字）
    timeout = normalize_network_timeout(
        request.args.get("timeout"), default=NETWORK_TIMEOUT_WEB, ceiling=NETWORK_TIMEOUT_CEILING
    )
    # 整体预算低于前端 abort 阈值（留余量），未完成项由 run_health_checks 标"超时"
    results = run_doctor_checks(include_network=include_network, max_timeout=timeout)
    ok_count, bad_count = summarize_doctor_results(results)
    return _ok({"results": results, "ok_count": ok_count, "bad_count": bad_count})


def _handle_logs():
    """GET /api/logs — 结构化日志查看（日志可视化）。

    查询参数：
      level  — 最小级别阈值（DEBUG/INFO/WARNING/ERROR/CRITICAL，非法值 → 400）
      lines  — 尾部读取物理行数（默认 5000，clamp [1,5000]，防大日志卡顿）
      since/until — 时间前缀过滤（透传核心层）
    所有解析/过滤/尾部读取逻辑委托核心层 read_log()，本 handler 仅做
    参数校验与 JSON 渲染。
    """
    from src.python.core.log_reader import LOG_LEVELS, read_log
    from src.python.web.handlers import _err, _ok

    level = request.args.get("level")
    if level is not None and level not in LOG_LEVELS:
        return _err("BAD_PARAM", f"无效日志级别: {level}"), 400

    raw_lines = request.args.get("lines", "5000")
    try:
        lines = int(raw_lines)
    except (TypeError, ValueError):
        return _err("BAD_PARAM", f"无效 lines 参数: {raw_lines}"), 400
    lines = max(1, min(lines, 5000))

    since = request.args.get("since")
    until = request.args.get("until")

    try:
        entries = read_log(limit=lines, level=level, since=since, until=until)
    except (ValueError, OSError):
        logger.exception("[logs] 读取运行日志失败")
        return _err("LOG_READ_FAILED", "读取运行日志失败（详情请查看日志）"), 500

    return _ok([e.to_dict() for e in entries])


def _handle_health_history():
    """GET /api/health/history — 数据源健康历史摘要（最近 10 次）。

    与 /api/health（实时探测）解耦：本接口只读历史快照文件（零网络探测），
    聚合逻辑委托核心层 summarize_health_history()。
    """
    from src.python.core.perf import summarize_health_history
    from src.python.web.handlers import _err, _ok

    try:
        summaries = summarize_health_history(limit=10)
    except OSError:
        logger.exception("[health] 读取健康历史失败")
        return _err("HEALTH_HISTORY_READ_FAILED", "读取健康历史失败（详情请查看日志）"), 500

    return _ok(summaries)


__all__ = ["_health_cache", "_handle_health", "_handle_doctor", "_handle_logs", "_handle_health_history"]
