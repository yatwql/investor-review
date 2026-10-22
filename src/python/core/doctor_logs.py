"""系统自检「日志与缓存」组 — 日志级别/体积、去重锚点、运行台账四项只读探针。

主模块 ``core.doctor`` 只保留分组编排与渲染，本模块承载「日志与缓存」组的
判定实现与其路径常量。**探针只读、自身永不抛异常**（单项失败由主模块的
逐项兜底统一转成失败行）。

路径常量挂在本模块（模块级，便于测试 setattr 重定向）——测试若要重定向，
patch 必须指向本模块 `doctor_logs`，指向 `doctor` 不会生效（调用点在此）。
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any

from src.python.core.doctor import GROUP_LOG_CACHE, PROJECT_ROOT, _item

#: 与主模块 logs/ 目录同源（PROJECT_ROOT/logs）
_LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
_APP_LOG_PATH = os.path.join(_LOGS_DIR, "app.log")
# 与 providers/news_dedup._ANCHOR_PATH 同源（core 层不得反向 import providers，
# 由 test_doctor_health 的路径一致性用例防漂移；相对段单列，便于测试不受路径重定向影响）
_DEDUP_ANCHOR_REL = os.path.join("data", "calibration", "dedup_anchors.jsonl")
_DEDUP_ANCHOR_PATH = os.path.join(PROJECT_ROOT, _DEDUP_ANCHOR_REL)
_PERF_LEDGER_PATH = os.path.join(PROJECT_ROOT, "data", "state", "perf_history.jsonl")
#: 去重锚点自动压缩阈值（与 providers/news_dedup._ANCHOR_SIZE_WARN_BYTES 同值）
_ANCHOR_COMPACT_BYTES = 32 * 1024 * 1024
#: 日志审计的采样上限（避免在超大日志上把自检拖慢）
_LOG_SCAN_MAX_LINES = 200_000


# ── 日志与缓存健康（审计驱动的自检组，只读） ──────────────────


def _check_log_level() -> dict[str, Any]:
    """文件日志级别的生效值（默认 INFO；DEBUG 属排障模式）。"""
    level = os.environ.get("INVEST_LOG_FILE_LEVEL", "").strip().upper() or "INFO"
    debug_on = level == "DEBUG"
    return _item(
        GROUP_LOG_CACHE,
        "日志级别",
        True,
        f"文件 {level}（{'DEBUG 排障模式' if debug_on else '默认 INFO'}）",
        hint="" if not debug_on else "排障结束可 unset INVEST_LOG_FILE_LEVEL 回到默认 INFO（DEBUG 会显著放大日志体积）",
    )


def _check_log_volume() -> dict[str, Any]:
    """日志体积与 DEBUG 占比：DEBUG 过半说明级别没收敛（审计时实测 91%）。"""
    try:
        size = os.path.getsize(_APP_LOG_PATH) if os.path.exists(_APP_LOG_PATH) else 0
        rotated = glob.glob(_APP_LOG_PATH + ".*")
        rotated_bytes = sum(os.path.getsize(f) for f in rotated if os.path.isfile(f))
        lines = 0
        debug_lines = 0
        if size:
            with open(_APP_LOG_PATH, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= _LOG_SCAN_MAX_LINES:
                        break
                    lines += 1
                    if "[DEBUG]" in line:
                        debug_lines += 1
        ratio = debug_lines / lines if lines else 0.0
        total_mb = (size + rotated_bytes) / 1e6
        ok = ratio <= 0.5 and total_mb <= 300
        hint = ""
        if ratio > 0.5:
            hint = "DEBUG 占比过半：确认未设 INVEST_LOG_FILE_LEVEL=DEBUG；排障后可清理 logs/app.log*（旧日志可删）"
        elif total_mb > 300:
            hint = "日志总量偏大：可删除较旧的 logs/app.log.N（保留 app.log 即可）"
        return _item(
            GROUP_LOG_CACHE,
            "日志体积",
            ok,
            f"app.log {size / 1e6:.1f} MB + 轮转 {len(rotated)} 份；DEBUG 占比 {ratio:.0%}（采样 {lines} 行）",
            hint=hint,
        )
    except OSError as e:
        return _item(GROUP_LOG_CACHE, "日志体积", False, f"读取失败：{e}", hint="检查 logs/ 目录权限")


def _check_dedup_anchor() -> dict[str, Any]:
    """去重锚点文件体积（超阈值会在读侧自动压缩）。"""
    try:
        if not os.path.exists(_DEDUP_ANCHOR_PATH):
            return _item(GROUP_LOG_CACHE, "去重锚点", True, "未生成（尚无去重锚点，属正常）")
        size = os.path.getsize(_DEDUP_ANCHOR_PATH)
        with open(_DEDUP_ANCHOR_PATH, encoding="utf-8", errors="replace") as f:
            lines = sum(1 for _ in f)
        bak = "（已保留 .bak 备份）" if os.path.exists(_DEDUP_ANCHOR_PATH + ".bak") else ""
        ok = size <= _ANCHOR_COMPACT_BYTES
        return _item(
            GROUP_LOG_CACHE,
            "去重锚点",
            ok,
            f"{size / 1024 / 1024:.1f} MB / {lines} 行（自动压缩阈值 {_ANCHOR_COMPACT_BYTES / 1024 / 1024:.0f} MB）{bak}",
            hint=""
            if ok
            else "超过阈值：下次生成时自动压缩（保留每组最新 + .bak 备份）；也可手工 "
            "`python scripts/eval-dedup-threshold.py --compact`",
        )
    except OSError as e:
        return _item(GROUP_LOG_CACHE, "去重锚点", False, f"读取失败：{e}", hint="检查 data/cache/ 权限")


def _check_perf_ledger_health() -> dict[str, Any]:
    """近 10 次运行的告警/错误水平（日志治理是否生效的量化回看）。"""
    try:
        if not os.path.exists(_PERF_LEDGER_PATH):
            return _item(GROUP_LOG_CACHE, "运行台账", True, "无性能台账（尚未生成过报告）")
        with open(_PERF_LEDGER_PATH, encoding="utf-8", errors="replace") as f:
            tail = f.readlines()[-10:]
        records = []
        for line in tail:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if len(records) < 3:
            return _item(GROUP_LOG_CACHE, "运行台账", True, f"仅 {len(records)} 条记录（样本不足，不作判断）")
        counters = [r.get("counters") or {} for r in records]
        warnings = sorted(int(c.get("warnings") or 0) for c in counters)
        median = warnings[len(warnings) // 2]
        errors = sum(len(r.get("errors") or []) for r in records)
        interrupted = sum(1 for r in records if r.get("status") == "interrupted")
        # 事实校验自动修正数：模型对指标口径理解偏差的直接信号（非故障，但要看趋势）
        fixes = sorted(int(c.get("fact_fix_total") or 0) for c in counters)
        fix_median = fixes[len(fixes) // 2]
        ok = median <= 5 and errors == 0
        message = f"近 {len(records)} 次运行：告警中位 {median}、累计错误 {errors}、中断 {interrupted}"
        if fix_median:
            message += f"；事实校验自动修正中位 {fix_median} 处（口径偏差信号，见 perf_history counters.fact_fix_*）"
        return _item(
            GROUP_LOG_CACHE,
            "运行台账",
            ok,
            message,
            hint=""
            if ok
            else "告警/错误偏高：先看 logs/app.log 对应时段与「数据源」组；预期缺失已降为 INFO，WARNING 应只剩真实降级",
        )
    except OSError as e:
        return _item(GROUP_LOG_CACHE, "运行台账", False, f"读取失败：{e}", hint="检查 data/state/ 权限")


def _check_logs_and_cache() -> list[dict[str, Any]]:
    """日志与缓存健康组（每项独立兜底：单项读取失败不影响其它项与整轮自检）。"""
    results: list[dict[str, Any]] = []
    for fn in (_check_log_level, _check_log_volume, _check_dedup_anchor, _check_perf_ledger_health):
        try:
            results.append(fn())
        except Exception as e:  # noqa: BLE001 — 自检自身永不抛异常
            results.append(_item(GROUP_LOG_CACHE, fn.__name__, False, f"自检异常：{e}"))
    return results


__all__ = [
    "_APP_LOG_PATH",
    "_DEDUP_ANCHOR_REL",
    "_DEDUP_ANCHOR_PATH",
    "_PERF_LEDGER_PATH",
    "_ANCHOR_COMPACT_BYTES",
    "_LOG_SCAN_MAX_LINES",
    "_check_log_level",
    "_check_log_volume",
    "_check_dedup_anchor",
    "_check_perf_ledger_health",
    "_check_logs_and_cache",
]
