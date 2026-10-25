"""内置定时生成配置块（``config.json`` 的 ``scheduler``）的归一化与校验。

Web 调度面板与 CLI ``config set scheduler.*`` 共用本模块：面板回显走宽松归一化
（缺省/非法项回落在真值来源 ``_DEFAULT_CONFIG["scheduler"]``），接口与命令行写入
走严格校验（非法字段直接报错，不静默改正）。
"""

from __future__ import annotations

import re
from typing import Any

from src.python.config._config_defaults import _DEFAULT_CONFIG

#: 缺省块（真值来源：`_DEFAULT_CONFIG["scheduler"]`）
DEFAULT_BLOCK: dict[str, Any] = dict(_DEFAULT_CONFIG["scheduler"])

#: 允许的报告格式（与 CLI `report --type` 子集一致）
REPORT_TYPES: tuple[str, ...] = ("basic", "both", "full")

#: 单字段编辑面（CLI `config set scheduler.<字段>`）
SCHEDULER_FIELDS: tuple[str, ...] = ("enabled", "time", "weekdays", "report_type")

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def normalize_block(raw: Any) -> dict:
    """把任意 ``scheduler`` 原始块归一化为完整可用形状（缺省/非法项回默认）。

    Args:
        raw: 配置中读到的原始值（可能是 None/部分字段/类型不符）。

    Returns:
        完整块 ``{enabled, time, weekdays, report_type}``（供面板回显）。
    """
    raw = raw if isinstance(raw, dict) else {}
    block = dict(DEFAULT_BLOCK)
    if isinstance(raw.get("enabled"), bool):
        block["enabled"] = raw["enabled"]
    match = _TIME_RE.match(str(raw.get("time") or ""))
    if match:
        block["time"] = f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    days = raw.get("weekdays")
    if isinstance(days, list):
        try:
            cleaned = sorted({int(d) for d in days})
        except (TypeError, ValueError):
            cleaned = []
        if cleaned and 0 <= cleaned[0] and cleaned[-1] <= 6:
            block["weekdays"] = cleaned
    if raw.get("report_type") in REPORT_TYPES:
        block["report_type"] = raw["report_type"]
    return block


def validate_block(payload: Any) -> dict:
    """校验面板/接口提交的 ``scheduler`` 块，返回归一化配置。

    Raises:
        ValueError: 任一字段非法（错误文案直映 HTTP 400 的中文提示）。
    """
    if not isinstance(payload, dict):
        raise ValueError("调度配置格式不合法")
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise ValueError("启用开关须为布尔值")
    time_text = str(payload.get("time") or "")
    match = _TIME_RE.match(time_text)
    if match is None:
        raise ValueError("时刻格式须为 HH:MM（00:00-23:59）")
    days_raw = payload.get("weekdays")
    if not isinstance(days_raw, list) or not days_raw:
        raise ValueError("执行日不能为空（0=周一 … 6=周日）")
    try:
        days = sorted({int(d) for d in days_raw})
    except (TypeError, ValueError):
        raise ValueError("执行日须为 0-6 整数（0=周一 … 6=周日）") from None
    if days[0] < 0 or days[-1] > 6:
        raise ValueError("执行日须为 0-6 整数（0=周一 … 6=周日）")
    report_type = payload.get("report_type", _DEFAULT_CONFIG["scheduler"]["report_type"])
    if report_type not in REPORT_TYPES:
        raise ValueError("报告格式不合法（basic/both/full）")
    hour, minute = int(match.group(1)), int(match.group(2))
    return {"enabled": enabled, "time": f"{hour:02d}:{minute:02d}", "weekdays": days, "report_type": report_type}


def validate_field(field: str, value: Any) -> Any:
    """校验单字段（CLI ``config set scheduler.<字段>``），返回归一化值。

    Raises:
        ValueError: 未知字段或取值非法。
    """
    if field == "enabled":
        if not isinstance(value, bool):
            raise ValueError("scheduler.enabled 须为布尔值（on/off）")
        return value
    if field == "time":
        match = _TIME_RE.match(str(value or ""))
        if match is None:
            raise ValueError("scheduler.time 须为 HH:MM（00:00-23:59）")
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    if field == "weekdays":
        if not isinstance(value, list) or not value:
            raise ValueError("scheduler.weekdays 不能为空（0=周一 … 6=周日）")
        try:
            days = sorted({int(d) for d in value})
        except (TypeError, ValueError):
            raise ValueError("scheduler.weekdays 须为 0-6 整数") from None
        if days[0] < 0 or days[-1] > 6:
            raise ValueError("scheduler.weekdays 须为 0-6 整数")
        return days
    if field == "report_type":
        if value not in REPORT_TYPES:
            raise ValueError("scheduler.report_type 不合法（basic/both/full）")
        return value
    raise ValueError(f"未知调度字段：{field}")


__all__ = [
    "DEFAULT_BLOCK",
    "REPORT_TYPES",
    "SCHEDULER_FIELDS",
    "normalize_block",
    "validate_block",
    "validate_field",
]
