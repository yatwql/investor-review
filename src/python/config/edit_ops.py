"""配置编辑共享层 — TUI / Web / CLI 唯一编辑通道（白名单 + 校验 + 写入 + 备份）。

- ``config_edit_whitelist``：可编辑配置项白名单（点分键 → 类型/选项 → 目标文件 → 写入原语）。
  唯一事实来源；``set_config`` 不做值校验，任何渠道必须经本模块的白名单 + 值校验。
- ``apply_config_edit``：应用单次编辑（Web POST / TUI 菜单 / CLI ``config set`` 共用），按目标文件分派写入，
  写前对目标共享文件做单槽 .bak 备份。
- ``config_backup_file``：写共享配置文件前的单槽 .bak 备份（copy_file_atomic 原子复制）。

写入语义（渠道无关，单点实现）：
  config.json 顶层标量 → ``set_config``；嵌套 dict（comparison_indices）读合并后整块写；
  anonymization → ``set_anonymization_mode``；llm_settings.json → ``write_llm_settings``；
  features.json → ``save_feature_overrides``（清单由 ``features.feature_switch_registry``
  驱动，与 TUI 菜单 S / Web 开关面板 / CLI 同源）。

校验规则集中于此（holdings_filename 禁路径分隔符、对比指数代码长度/字符/重复、
类型/枚举/action 合法性），两渠道强度一致——禁止在渠道层另行实现同名规则。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from src.python.config._config_defaults import _DEFAULT_CONFIG
from src.python.config.features import (
    feature_switch_registry,
)
from src.python.config._scheduler import SCHEDULER_FIELDS as _SCHEDULER_FIELDS
from src.python.core.atomic_write import copy_file_atomic
from src.python.core.registry import get_llm_module_names

logger = logging.getLogger("invest")

# 匿名化枚举选项（对齐 config/anonymizer._ANONYMIZATION_MODES）
ANON_MODES = ("off", "code_display", "full_anonymous", "summary")

#: 动作型写入原语（无单一标量值：增删/重置/重排），CLI 直接赋值路径不接受
_ACTION_WRITERS = frozenset({"comparison_indices", "llm_providers"})


class ConfigEditError(ValueError):
    """配置编辑校验失败（未知键 / 类型不符 / 枚举不符 / action 非法）→ 调用方映射 400。"""


# ═══════════════════════════════════════════════════════════════
# 白名单（唯一事实来源：点分键 → 编辑规则 → 目标文件 → 写入原语）
# ═══════════════════════════════════════════════════════════════
# 设计约束：本数据字典为模块级小写名（check-semantic-index 反向校验
# 用大小写敏感子串匹配，UPPER_SNAKE 会匹配不过）。
# ── LLM 调优参数（llm_settings.json 顶层标量）─────────────────────
# 这些键是「用户可以合理调整」的运行参数：默认值有依据（见 _llm_settings_defaults），
# 但端点抖动/费用考量时需要能改。此前只能手改 JSON（无校验、无面板入口）。
# 范围（min/max）即校验边界——超出直接拒绝并说明，不静默裁剪。
LLM_TUNING_SPECS: dict[str, dict] = {
    "llm_max_thinking_concurrency": {
        "kind": "int",
        "min": 1,
        "max": 4,
        "label": "thinking 模块并发上限",
        "hint": "默认 2（两个 thinking 模块并行）；端点偶发空内容重试时改回 1（串行）",
    },
    "llm_max_concurrency": {
        "kind": "int",
        "min": 1,
        "max": 8,
        "label": "LLM 模块并发线程数",
        "hint": "默认 3；调高可提速但更易触发端点限速（429）",
    },
    "max_retries": {
        "kind": "int",
        "min": 0,
        "max": 5,
        "label": "单请求重试次数",
        "hint": "默认 2（503/超时/网络异常）；429/403 归配额不重试",
    },
    "llm_full_fail_retry_delay": {
        "kind": "int",
        "min": 0,
        "max": 600,
        "label": "整链失败后的重试等待（秒）",
        "hint": "默认 30；0 表示不等待",
    },
    "llm_total_time_budget_sec": {
        "kind": "int",
        "min": 0,
        "max": 7200,
        "label": "LLM 总时间预算（秒）",
        "hint": "默认 0（不启用）；超预算不再启动新模块，防单次报告拖成小时级",
    },
    "daily_cost_limit": {
        "kind": "float",
        "min": 0,
        "max": 10000,
        "label": "LLM 日费用上限",
        "hint": "默认 0（不启用）；超限时交互渠道询问「用已有结果继续 / 中止」",
    },
}


def _logging_specs() -> dict[str, dict]:
    """日志设置可编辑项（枚举/整数 + 范围 + 中文标签与提示）。

    与 TUI `[D]→[L]` 日志面板同一批键：写盘级别 / 控制台级别 / 单文件上限 / 备份份数 /
    查看器默认级别 / 查看器首屏行数。``path`` 与 ``console_color`` 不进编辑面（路径属部署项、
    颜色属终端能力探测，均留手动配置）。
    """
    from src.python.config._logging import DEFAULTS, LEVELS, RANGES, VIEWER_LEVELS

    def _mb(value: int) -> int:
        return int(value) // (1024 * 1024)

    return {
        "level": {
            "kind": "enum",
            "options": LEVELS,
            "default": DEFAULTS["level"],
            "label": "写盘级别",
            "hint": "默认 INFO；DEBUG 仅排障时启用（体积与信噪比代价高），改动下次启动生效",
        },
        "console_level": {
            "kind": "enum",
            "options": LEVELS,
            "default": DEFAULTS["console_level"],
            "label": "控制台级别",
            "hint": "默认 INFO；终端只看关键信息时可调到 WARNING，改动下次启动生效",
        },
        "max_bytes": {
            "kind": "int",
            "min": RANGES["max_bytes"][0],
            "max": RANGES["max_bytes"][1],
            "step": 1024 * 1024,
            "unit": "bytes",
            "default": DEFAULTS["max_bytes"],
            "label": "单文件上限（MB）",
            "hint": f"默认 {_mb(DEFAULTS['max_bytes'])} MB；超限轮转，改动下次启动生效",
        },
        "backup_count": {
            "kind": "int",
            "min": RANGES["backup_count"][0],
            "max": RANGES["backup_count"][1],
            "default": DEFAULTS["backup_count"],
            "label": "备份份数",
            "hint": "默认 5；0 表示不保留轮转文件，改动下次启动生效",
        },
        "viewer_level": {
            "kind": "enum",
            "options": VIEWER_LEVELS,
            "default": DEFAULTS["viewer_level"],
            "label": "查看器默认级别",
            "hint": "默认 INFO；ALL 表示不预筛，即时生效",
        },
        "tail_lines": {
            "kind": "int",
            "min": RANGES["tail_lines"][0],
            "max": RANGES["tail_lines"][1],
            "default": DEFAULTS["tail_lines"],
            "label": "查看器首屏行数",
            "hint": "默认 500；即时生效",
        },
    }


LOGGING_SPECS: dict[str, dict] = _logging_specs()


#: 调优项 → 编辑白名单条目（同一份 spec 派生，避免范围/说明两处维护）
def _tuning_default(key: str):
    """调优项默认值（唯一来源：`_llm_settings_defaults._DEFAULT_LLM_SETTINGS`）。"""
    from src.python.config._llm_settings_defaults import get_llm_setting_default

    return get_llm_setting_default(key)


_LLM_TUNING_WHITELIST = {
    key: {**spec, "default": _tuning_default(key), "target": "llm_settings", "writer": "llm_scalar"}
    for key, spec in LLM_TUNING_SPECS.items()
}

config_edit_whitelist = {
    # ── 1 自由文本路径（config.json 顶层标量）──
    "holdings_dir": {"kind": "str", "target": "config", "writer": "scalar"},
    "holdings_filename": {"kind": "str", "target": "config", "writer": "scalar"},
    "output_dir": {"kind": "str", "target": "config", "writer": "scalar"},
    # ── 2 报告章节开关（config.json 顶层标量）──
    "enable_fund_deep_analysis": {"kind": "bool", "target": "config", "writer": "scalar"},
    "enable_news": {"kind": "bool", "target": "config", "writer": "scalar"},
    "enable_history": {"kind": "bool", "target": "config", "writer": "scalar"},
    "enable_portfolio_evolution": {"kind": "bool", "target": "config", "writer": "scalar"},
    "enable_action": {"kind": "bool", "target": "config", "writer": "scalar"},
    # ── 4 持仓匿名化枚举（config.json 顶层 anonymization，set_anonymization_mode）──
    "anonymization.mode": {
        "kind": "enum",
        "options": ANON_MODES,
        "target": "config",
        "writer": "anonymization",
    },
    # ── 5 对比指数池（config.json 嵌套 dict，增/删/重置）──
    "comparison_indices": {
        "kind": "action",
        "actions": ("add", "remove", "reset"),
        "target": "config",
        "writer": "comparison_indices",
    },
    # ── 6 LLM 分析章节开关（llm_settings.json enabled_llm；清单 = 注册表可见标准模块）──
    **{
        f"enabled_llm.{sfx}": {"kind": "bool", "target": "llm_settings", "writer": "llm"}
        for sfx in get_llm_module_names()
    },
    # ── LLM 多链线路优先级（llm_providers.json）—— order 置换校验 + priority 归一化 ──
    "llm_providers.priority": {
        "kind": "action",
        "actions": ("reorder",),
        "target": "llm_providers",
        "writer": "llm_providers",
    },
    # ── 7 功能开关（features.json；清单取自 features.feature_switch_registry 全注册表，
    #      实验项与常规开关同表同写入路径，分组只影响前端分块渲染）──
    **{flag: {"kind": "bool", "target": "features", "writer": "features"} for flag in feature_switch_registry},
    # ── 8 LLM 调优参数（llm_settings.json 顶层标量；范围/说明见 LLM_TUNING_SPECS）──
    **_LLM_TUNING_WHITELIST,
    # ── 9 日志设置（logger.json；枚举/范围与 TUI 日志面板同源，清单见 _LOGGING_SPECS）──
    **{f"logging.{key}": {**spec, "target": "logging", "writer": "logging"} for key, spec in LOGGING_SPECS.items()},
}


def _target_path(target: str) -> str:
    """解析目标共享配置文件的绝对路径（写前备份用）。"""
    if target == "config":
        from src.python.config._config_defaults import get_config_path

        return get_config_path()
    if target == "llm_settings":
        from src.python.config._llm_settings import get_llm_settings_path

        return get_llm_settings_path()
    if target == "llm_providers":
        from src.python.config._llm_providers import _get_llm_providers_path

        return _get_llm_providers_path()
    if target == "features":
        from src.python.config.features import FEATURES_FILE

        return FEATURES_FILE
    if target == "logging":
        from src.python.config._logging import get_logger_config_path

        return get_logger_config_path()
    raise ConfigEditError(f"未知配置目标文件: {target}")


def config_backup_file(path: str) -> str | None:
    """写共享配置文件前的单槽 .bak 备份（原子复制）。

    - 文件不存在 → 返回 None（首次写入无需备份）。
    - 存在 → 复制为 ``{path}.bak``（单槽轮转：第二次写覆盖上一版 .bak）。

    Args:
        path: 共享配置文件绝对路径。

    Returns:
        .bak 绝对路径；原文件不存在时返回 None。

    Raises:
        OSError: 备份失败（目标目录不可写等），调用方中止配置写入。
    """
    if not os.path.isfile(path):
        return None
    bak_path = path + ".bak"
    copy_file_atomic(path, bak_path)
    logger.info("[config-edit] 已备份共享配置文件: %s", bak_path)
    return bak_path


def _dispatch_write(entry: dict, key: str, value) -> None:
    """按白名单写入原语分派（渠道无关的唯一写入路径）。"""
    writer = entry["writer"]
    if writer == "scalar":
        from src.python.config import set_config

        set_config(key, value)
    elif writer == "anonymization":
        from src.python.config.anonymizer import set_anonymization_mode

        set_anonymization_mode(value)
    elif writer == "llm":
        _write_llm_enabled(key, value)
    elif writer == "llm_scalar":
        _write_llm_scalar(key, value)
    elif writer == "logging":
        _write_logging(key, value)
    elif writer == "features":
        from src.python.config.features import save_feature_overrides

        save_feature_overrides({key: value})
    else:
        raise ConfigEditError(f"未知写入原语: {writer}")


def _write_logging(key: str, value) -> None:
    """写 logger.json 的单个扁平键（``logging.<键>`` → ``write_logger_config``）。

    校验与写回（文本 patch 保注释、非法值不落盘）全部委托 ``config._logging``，
    本函数只做键名映射——三渠道（TUI 日志面板 / Web 面板 / 手工）同一强度。
    """
    from src.python.config._logging import get_logger_config_path, write_logger_config

    flat_key = key.split(".", 1)[1]
    write_logger_config({flat_key: value}, get_logger_config_path())


def _write_llm_enabled(key: str, value: bool) -> None:
    """写 llm_settings.json 的 enabled_llm.<模块>（读扁平视图 → write_llm_settings）。"""
    from src.python.config._llm_settings import get_llm_settings_path, read_llm_settings_file, write_llm_settings

    snapshot = read_llm_settings_file()
    settings = dict(snapshot[0]) if snapshot else {}
    settings_path = snapshot[1] if snapshot else get_llm_settings_path()
    sub_key = key.split(".", 1)[1]
    enabled_map = dict(settings.get("enabled_llm") or {})
    enabled_map[sub_key] = value
    settings["enabled_llm"] = enabled_map
    write_llm_settings(settings, settings_path)


def _write_llm_scalar(key: str, value) -> None:
    """写 llm_settings.json 的顶层标量（读原始落盘 → 合并 → 保留注释写回）。"""
    from src.python.config._llm_settings import get_llm_settings_path, read_llm_settings_file, write_llm_settings

    snapshot = read_llm_settings_file()
    settings, path = snapshot if snapshot else ({}, get_llm_settings_path())
    settings[key] = value
    write_llm_settings(settings, path)


def _coerce_number(key: str, value, kind: str, entry: dict) -> int | float:
    """数值型编辑：接受数字或数字字符串，校验类型与范围（超范围明确报错，不静默裁剪）。"""
    if isinstance(value, bool):  # bool 是 int 子类，必须先拒
        raise ConfigEditError(f"配置项 {key} 应为{'整数' if kind == 'int' else '数值'}")
    try:
        number = int(value) if kind == "int" else float(value)
    except (TypeError, ValueError):
        raise ConfigEditError(f"配置项 {key} 应为{'整数' if kind == 'int' else '数值'}: {value!r}") from None
    if kind == "int" and isinstance(value, float) and value != int(value):
        raise ConfigEditError(f"配置项 {key} 应为整数: {value!r}")
    low, high = entry.get("min"), entry.get("max")
    if (low is not None and number < low) or (high is not None and number > high):
        raise ConfigEditError(f"配置项 {key} 取值 {number!r} 超出范围 [{low}, {high}]")
    return number


def _normalize_plain_value(key: str, value, entry: dict):
    """标量/布尔/枚举/数值编辑的纯校验与归一化（不写盘）。"""
    kind = entry["kind"]
    if kind == "str":
        if not isinstance(value, str) or not value.strip():
            raise ConfigEditError(f"配置项 {key} 应为非空字符串")
        value = value.strip()
        # holdings_filename 为纯文件名，拒绝含路径分隔符（防破坏文件定位）
        if key == "holdings_filename" and any(sep in value for sep in ("/", "\\")):
            raise ConfigEditError("holdings_filename 应为纯文件名，不能包含路径分隔符")
    elif kind == "bool":
        if not isinstance(value, bool):
            raise ConfigEditError(f"配置项 {key} 应为布尔值")
    elif kind == "enum":
        if value not in entry["options"]:
            raise ConfigEditError(f"配置项 {key} 取值不在允许范围内: {value}")
    elif kind in ("int", "float"):
        value = _coerce_number(key, value, kind, entry)
    else:
        raise ConfigEditError(f"配置项 {key} 不支持的值类型: {kind}")
    return value


def _apply_comparison_action(payload: dict, entry: dict) -> dict:
    """对比指数池增/删/重置（读合并 → set_config 整块写）。"""
    from src.python.config import get_config, set_config

    action = payload.get("action")
    if action not in entry["actions"]:
        raise ConfigEditError(f"对比指数池 action 不合法（add/remove/reset）: {action}")
    config = get_config()
    indices = dict(config.get("comparison_indices") or _DEFAULT_CONFIG.get("comparison_indices", {}))
    if action == "add":
        code = payload.get("code")
        name = payload.get("name")
        if not isinstance(code, str) or not code.strip():
            raise ConfigEditError("对比指数代码不能为空")
        code = code.strip()
        if len(code) < 3:
            raise ConfigEditError("对比指数代码长度至少为 3")
        if any(token in code for token in ("..", "/", "\\")):
            raise ConfigEditError("对比指数代码包含非法字符")
        if code in indices:
            raise ConfigEditError(f"指数 {code} 已在对比池中")
        if not isinstance(name, str) or not name.strip():
            raise ConfigEditError("对比指数名称不能为空")
        indices[code] = name.strip()
    elif action == "remove":
        code = payload.get("code")
        if not isinstance(code, str) or not code.strip():
            raise ConfigEditError("对比指数代码不能为空")
        code = code.strip()
        if code not in indices:
            raise ConfigEditError(f"指数 {code} 不在对比池中")
        del indices[code]
    else:  # reset → 默认预设
        indices = dict(_DEFAULT_CONFIG.get("comparison_indices", {}))
    set_config("comparison_indices", indices)
    return indices


def _apply_llm_provider_action(payload: dict, entry: dict) -> dict:
    """LLM 多链线路重排（reorder）：order 必须是当前线路名单的**置换**。

    语义唯一实现在此（CLI ``--llm-provider-order`` / TUI 面板 / Web 配置面均为薄适配）：
    priority 按新顺序归一化为 10, 20, 30…（数值小者链序靠前，与
    ``strategy.resolve_provider_chain`` 的 priority 排序口径一致）；其余字段
    （provider / credentials_ref / model / endpoint / weight / timeout…）原样保留。

    Args:
        payload: ``{"action": "reorder", "order": [线路名…]}``。
        entry: 白名单条目（校验 action 在允许集合内）。

    Returns:
        ``{"order": 生效顺序}``。

    Raises:
        ConfigEditError: 动作非法 / order 格式错 / 未恰好覆盖全部线路 / 配置无有效线路。
    """
    import copy

    from src.python.config._llm_providers import (
        _load_llm_providers,
        _parse_providers_list,
        write_llm_providers,
    )
    from src.python.config._llm_providers_defaults import _DEFAULT_LLM_PROVIDERS

    action = payload.get("action")
    if action not in entry["actions"]:
        raise ConfigEditError(f"llm_providers 动作不合法（reorder）: {action}")
    order = payload.get("order")
    if not isinstance(order, list) or not order or not all(isinstance(item, str) and item.strip() for item in order):
        raise ConfigEditError("order 必须为非空的线路名列表")
    names = [item.strip() for item in order]
    if len(set(names)) != len(names):
        raise ConfigEditError("order 中存在重复线路名")

    raw = _load_llm_providers()
    if raw is None:
        raw = copy.deepcopy(_DEFAULT_LLM_PROVIDERS)  # 文件缺失 → 内置模板上重排（写入即物化文件）
    providers = _parse_providers_list(raw)
    if not providers:
        raise ConfigEditError("llm_providers.json 无有效线路，先修复配置文件后重试")
    current = [str(p.get("name")) for p in providers]
    if len(names) != len(current) or set(names) != set(current):
        raise ConfigEditError(f"order 须恰好覆盖全部线路（当前: {'、'.join(current)}）")

    rank = {name: (idx + 1) * 10 for idx, name in enumerate(names)}
    new_list = []
    for item in raw.get("providers", []):
        item_name = str(item.get("name", ""))
        # 解析层已剔除的无效条目原样保留（不因重排丢失）；有效条目按新序归一化 priority
        new_list.append({**item, "priority": rank[item_name]} if item_name in rank else item)
    new_raw = {**raw, "providers": new_list}
    write_llm_providers(new_raw, _target_path("llm_providers"))
    return {"order": names}


def apply_config_edit(payload: dict) -> dict:
    """应用单次配置编辑（Web POST / TUI 菜单 / CLI ``config set`` 共用入口）。

    按白名单校验键与值，写前对目标共享文件做单槽 .bak 备份，随后按
    目标文件分派写入原语。

    Args:
        payload: ``{"key": 点分键, "value": 值}`` 或 ``{"key": "comparison_indices",
                 "action": add/remove/reset, "code": ..., "name": ...}``.

    Returns:
        ``{"key": 点分键, "value": 新值, "backup": .bak 路径或 None}``.

    Raises:
        ConfigEditError: 键/值/action 校验失败（Web 映射 400，TUI 映射提示行）。
        OSError / Exception: 写入失败（Web 映射 500，调用方记日志）。
    """
    key = payload.get("key")
    entry = config_edit_whitelist.get(key)
    if entry is None:
        raise ConfigEditError(f"配置键不在白名单: {key}")

    if entry["writer"] in _ACTION_WRITERS:
        backup_path = config_backup_file(_target_path(entry["target"]))
        if entry["writer"] == "comparison_indices":
            new_value = _apply_comparison_action(payload, entry)
        else:
            new_value = _apply_llm_provider_action(payload, entry)
        return {"key": key, "value": new_value, "backup": backup_path}

    # 先校验后备份：非法取值不产生 .bak（CLI --dry-run 复用同一校验路径）
    new_value = _normalize_plain_value(key, payload.get("value"), entry)
    backup_path = config_backup_file(_target_path(entry["target"]))
    _dispatch_write(entry, key, new_value)
    return {"key": key, "value": new_value, "backup": backup_path}


def preview_config_edit(payload: dict) -> dict:
    """校验单次标量编辑但不写盘（CLI ``config set --dry-run`` 复用）。

    Args:
        payload: ``{"key": 点分键, "value": 值}``。

    Returns:
        ``{"key": 点分键, "value": 归一化后的值}``。

    Raises:
        ConfigEditError: 未知键 / 动作型键 / 值校验失败。
    """
    key = payload.get("key")
    entry = config_edit_whitelist.get(key)
    if entry is None:
        raise ConfigEditError(f"配置键不在白名单: {key}")
    if entry["writer"] in _ACTION_WRITERS:
        raise ConfigEditError(f"{key} 是动作型键，不能直接赋值（请用 TUI/Web 或专用参数）")
    return {"key": key, "value": _normalize_plain_value(key, payload.get("value"), entry)}


def read_config_value(key: str):
    """读取白名单键的当前生效值（CLI ``config list/get`` 用，含运行时覆写）。

    Args:
        key: 白名单点分键。

    Returns:
        当前值（bool/int/str/枚举/嵌套 dict）。

    Raises:
        ConfigEditError: 未知键或动作型键（动作型无单一标量值）。
    """
    entry = config_edit_whitelist.get(key)
    if entry is None:
        raise ConfigEditError(f"配置键不在白名单: {key}")
    writer = entry["writer"]
    if writer in _ACTION_WRITERS:
        raise ConfigEditError(f"{key} 是动作型键，无单一取值")
    if writer == "scalar":
        from src.python.config import get_config

        return get_config().get(key)
    if writer == "anonymization":
        from src.python.config import get_config

        return (get_config().get("anonymization") or {}).get("mode", "off")
    if writer in ("llm", "llm_scalar"):
        from src.python.config import get_llm_config

        llm = get_llm_config() or {}
        if key.startswith("enabled_llm."):
            return (llm.get("enabled_llm") or {}).get(key.split(".", 1)[1])
        return llm.get(key)
    if writer == "features":
        from src.python.config.features import is_feature_enabled

        return is_feature_enabled(key)
    if writer == "logging":
        from src.python.config._logging import read_logger_config

        return read_logger_config().get(key.split(".", 1)[1])
    raise ConfigEditError(f"未知写入目标：{writer}")


def scheduler_field_names() -> tuple[str, ...]:
    """``scheduler.*`` 可编辑字段名（CLI 帮助/校验用，避免渠道层导入私有模块）。"""
    return _SCHEDULER_FIELDS


def validate_scheduler_value(field: str, value: Any) -> Any:
    """校验单个 ``scheduler.*`` 字段值（CLI ``--dry-run`` 用）。"""
    from src.python.config._scheduler import validate_field

    return validate_field(field, value)


def scheduler_values() -> dict[str, Any]:
    """``scheduler.*`` 四个字段的当前归一化取值（CLI ``config list/get`` 用）。"""
    from src.python.config import get_config
    from src.python.config._scheduler import normalize_block

    block = normalize_block(get_config().get("scheduler"))
    return {f"scheduler.{field}": block[field] for field in _SCHEDULER_FIELDS}


def set_scheduler_field(field: str, value: Any) -> dict:
    """写入单个 ``scheduler.*`` 字段（CLI ``config set`` 用）。

    按当前块补全其余字段后整块落盘；字段值走严格校验（非法直接报错）。

    Raises:
        ValueError: 未知字段或取值非法。
    """
    from src.python.config._scheduler import normalize_block, validate_field

    if field not in _SCHEDULER_FIELDS:
        raise ValueError(f"未知调度字段：{field}")
    from src.python.config import get_config

    block = normalize_block(get_config().get("scheduler"))
    block[field] = validate_field(field, value)
    result = apply_scheduler_block(block)
    result["key"] = f"scheduler.{field}"
    return result


def apply_scheduler_block(block: dict) -> dict:
    """保存内置定时生成的 ``scheduler`` 配置块（渠道共享的写入口）。

    与 ``apply_config_edit`` 同构：写前对 config.json 做单槽 .bak 备份。
    调度侧已完成格式校验（时刻/执行日/报告格式），此处只负责落盘，
    保证配置写原语不散落到渠道层。

    Args:
        block: 已校验归一化的 ``{enabled, time, weekdays, report_type}``。

    Returns:
        ``{"key": "scheduler", "value": 块, "backup": .bak 路径或 None}``。
    """
    from src.python.config import set_config

    backup_path = config_backup_file(_target_path("config"))
    set_config("scheduler", block)
    return {"key": "scheduler", "value": block, "backup": backup_path}
