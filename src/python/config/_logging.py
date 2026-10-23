"""logger.json — 日志运行配置（写盘/控制台/查看器）的读取、校验与写入。

`core/logger.py` 在进程启动时自行读取本文件（不导入 config 包，避免循环依赖）；
本模块是面板/校验层的共享入口：同一张范围表既用于加载回落，也用于保存拒绝。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from src.python.config._comments import strip_json_comments
from src.python.core.atomic_write import write_text_atomic
from src.python.core.constants import PROJECT_ROOT

logger = logging.getLogger("invest")

LOGGER_SCHEMA_VERSION = 1
LOGGER_CONFIG_PATH = os.path.join(PROJECT_ROOT, "data/config/logger.json")

LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
VIEWER_LEVELS: tuple[str, ...] = (*LEVELS, "ALL")

DEFAULTS: dict[str, Any] = {
    "path": "logs/app.log",
    "level": "INFO",
    "max_bytes": 10 * 1024 * 1024,
    "backup_count": 5,
    "console_level": "INFO",
    "console_color": True,
    "viewer_level": "INFO",
    "tail_lines": 500,
}

RANGES: dict[str, tuple[int, int]] = {
    "max_bytes": (1024, 1024 * 1024 * 1024),
    "backup_count": (0, 50),
    "tail_lines": (50, 10000),
}

_ENUM_KEYS = {"level": LEVELS, "console_level": LEVELS, "viewer_level": VIEWER_LEVELS}


class LoggerConfigError(ValueError):
    """非法日志配置（消息含键名、当前值、合法范围/枚举）。"""


def get_logger_config_path() -> str:
    return LOGGER_CONFIG_PATH


def _flatten(doc: dict[str, Any]) -> dict[str, Any]:
    file_section = doc.get("file") or {}
    console = doc.get("console") or {}
    viewer = doc.get("viewer") or {}
    return {
        "path": file_section.get("path", DEFAULTS["path"]),
        "level": file_section.get("level", DEFAULTS["level"]),
        "max_bytes": file_section.get("max_bytes", DEFAULTS["max_bytes"]),
        "backup_count": file_section.get("backup_count", DEFAULTS["backup_count"]),
        "console_level": console.get("level", DEFAULTS["console_level"]),
        "console_color": console.get("color", DEFAULTS["console_color"]),
        "viewer_level": viewer.get("default_level", DEFAULTS["viewer_level"]),
        "tail_lines": viewer.get("tail_lines", DEFAULTS["tail_lines"]),
    }


def _unflatten(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "file": {
            "path": values["path"],
            "level": values["level"],
            "max_bytes": values["max_bytes"],
            "backup_count": values["backup_count"],
        },
        "console": {"level": values["console_level"], "color": values["console_color"]},
        "viewer": {"default_level": values["viewer_level"], "tail_lines": values["tail_lines"]},
    }


def validate_value(key: str, value: Any) -> None:
    """校验单个键；非法抛 :class:`LoggerConfigError`（含键名/当前值/范围）。"""
    if key in _ENUM_KEYS:
        options = _ENUM_KEYS[key]
        if not isinstance(value, str) or value.upper() not in options:
            raise LoggerConfigError(f"配置项 {key} 取值 {value!r} 不在允许范围（{' / '.join(options)}）")
        return
    if key == "path":
        if not isinstance(value, str) or not value.strip() or ".." in value:
            raise LoggerConfigError(f"配置项 path 取值 {value!r} 非法（须为非空且不含 '..' 的路径）")
        return
    if key == "console_color":
        if not isinstance(value, bool):
            raise LoggerConfigError(f"配置项 console_color 应为布尔值（当前 {value!r}）")
        return
    if key in RANGES:
        low, high = RANGES[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise LoggerConfigError(f"配置项 {key} 应为整数（当前 {value!r}，合法范围 [{low}, {high}]）")
        if not low <= value <= high:
            raise LoggerConfigError(f"配置项 {key} 取值 {value} 超出范围 [{low}, {high}]")
        return
    raise LoggerConfigError(f"未知日志配置键: {key}")


def read_logger_config(path: str | None = None) -> dict[str, Any]:
    """读取并校验 logger.json，返回扁平配置（路径已绝对化）。

    - 文件缺失 → 全默认（不告警，首次运行正常态）
    - version 缺失/≠1 → 抛 :class:`LoggerConfigError`（面板层提示重新生成）
    - 单键非法 → 告警并回落该键默认（加载不阻断）
    """
    target = path or get_logger_config_path()
    if not os.path.exists(target):
        values = dict(DEFAULTS)
        return {**values, "path": _absolute_path(values["path"])}
    try:
        with open(target, encoding="utf-8-sig") as f:
            doc = json.loads(strip_json_comments(f.read()))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("[logging] logger.json 读取失败（%s），使用默认日志配置", e)
        values = dict(DEFAULTS)
        return {**values, "path": _absolute_path(values["path"])}

    if not isinstance(doc, dict):
        logger.warning("[logging] logger.json 根元素不是 JSON 对象，使用默认日志配置")
        values = dict(DEFAULTS)
        return {**values, "path": _absolute_path(values["path"])}
    version = doc.get("version")
    if version != LOGGER_SCHEMA_VERSION:
        raise LoggerConfigError(
            f"logger.json 的 version={version!r}，本版本只接受 {LOGGER_SCHEMA_VERSION}；"
            "请删除该文件后重新生成（程序会按模板重建）"
        )

    values = _flatten(doc)
    for key in DEFAULTS:
        try:
            validate_value(key, values[key])
        except LoggerConfigError as e:
            logger.warning("[logging] %s；已回落默认 %r", e, DEFAULTS[key])
            values[key] = DEFAULTS[key]
    values["path"] = _absolute_path(values["path"])
    return values


def _absolute_path(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def _render(values: dict[str, Any]) -> str:
    body = _unflatten(values)
    return f"""// 日志运行配置（logger.json）
// 格式：文件 / 控制台 / 查看器三段；环境变量 INVEST_LOG_FILE_LEVEL /
// INVEST_LOG_CONSOLE_LEVEL 可临时覆盖级别（优先级高于本文件）。
{{
  "version": {LOGGER_SCHEMA_VERSION},

  // ── 写盘 ──
  "file": {{
    "path": {json.dumps(body["file"]["path"], ensure_ascii=False)},   // 相对项目根或绝对路径
    "level": "{body["file"]["level"]}",   // 写盘级别：DEBUG / INFO / WARNING / ERROR / CRITICAL
    "max_bytes": {body["file"]["max_bytes"]},   // 单文件上限（字节）
    "backup_count": {body["file"]["backup_count"]}   // 备份份数（0 = 不轮转）
  }},

  // ── 控制台 ──
  "console": {{
    "level": "{body["console"]["level"]}",   // 控制台级别
    "color": {str(body["console"]["color"]).lower()}   // 允许颜色（不支持/NO_COLOR 时自动降级）
  }},

  // ── 日志查看器（TUI [D]→[V] / Web「运行日志」）──
  "viewer": {{
    "default_level": "{body["viewer"]["default_level"]}",   // 默认筛选级别；ALL = 不过滤
    "tail_lines": {body["viewer"]["tail_lines"]}   // 首屏读取行数上限
  }}
}}
"""


def render_default_logger_config() -> str:
    return _render(dict(DEFAULTS))


def ensure_logger_file(path: str | None = None) -> bool:
    """缺失时写入默认模板（含中文注释）；已存在则不动。"""
    target = path or get_logger_config_path()
    if os.path.exists(target):
        return False
    os.makedirs(os.path.dirname(target), exist_ok=True)
    return write_text_atomic(
        target, render_default_logger_config(), prefix=".logger_", log_tag="logging", noun="日志配置"
    )


def write_logger_config(updates: dict[str, Any], path: str | None = None) -> dict[str, Any]:
    """校验并写入（文本 patch 保注释；路径不可定位时按模板重排）。

    Args:
        updates: 扁平键 → 新值（如 ``{"level": "DEBUG", "backup_count": 3}``）。
    Returns:
        写入后的完整扁平配置（路径绝对化）。
    Raises:
        LoggerConfigError: 任一键非法（此时文件保持原值）。
    """
    for key, value in updates.items():
        if key not in DEFAULTS:
            raise LoggerConfigError(f"未知日志配置键: {key}")
        validate_value(key, value)

    target = path or get_logger_config_path()
    current = read_logger_config(target) if os.path.exists(target) else dict(DEFAULTS)
    merged = {**current, **updates}
    if "path" in updates:
        merged["path"] = _absolute_path(merged["path"])

    raw = ""
    if os.path.exists(target):
        with open(target, encoding="utf-8-sig") as f:
            raw = f.read()
    patched = _patch_values(raw, updates) if raw.strip() else None
    if patched is None:
        patched = _render(merged)
    else:
        try:
            json.loads(strip_json_comments(patched))
        except (json.JSONDecodeError, ValueError) as e:
            raise LoggerConfigError(f"日志配置写回结果非法，已中止: {e}") from None
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if not write_text_atomic(target, patched, prefix=".logger_", log_tag="logging", noun="日志配置"):
        raise LoggerConfigError("日志配置写入失败（请检查目录权限）")
    return {**merged, "path": _absolute_path(merged["path"])}


_PATHS: dict[str, tuple[str, str]] = {
    "path": ("file", "path"),
    "level": ("file", "level"),
    "max_bytes": ("file", "max_bytes"),
    "backup_count": ("file", "backup_count"),
    "console_level": ("console", "level"),
    "console_color": ("console", "color"),
    "viewer_level": ("viewer", "default_level"),
    "tail_lines": ("viewer", "tail_lines"),
}


def _patch_values(raw: str, updates: dict[str, Any]) -> str | None:
    """按 ``section.key`` 定位并在原文本替换值（保注释）；不可定位返回 None。"""
    from src.python.config._llm_schema import _locate_path_span

    patched = raw
    for key, value in updates.items():
        section, field = _PATHS[key]
        span = _locate_path_span(patched, (section, field))
        if span is None:
            return None
        vs, ve = span
        text = json.dumps(_absolute_path(value) if key == "path" else value, ensure_ascii=False)
        patched = patched[:vs] + text + patched[ve:]
    return patched
