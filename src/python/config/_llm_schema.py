"""llm_settings.json v2 结构 — 版本校验、展平/反展平、缺省合并、文本 patch。

对外契约保持**扁平键**（``model_<m>`` / ``thinking_enabled_<m>`` / ``enabled_llm`` /
``llm_max_*`` / ``debate`` / ``fact_check`` / ``pricing`` …）：``llm/`` 包与既有消费方
不改；文件落盘为 v2 嵌套结构（``defaults`` / ``modules`` / ``runtime`` / ``advanced``）。

结构只按当前 ``schema_version`` 解析：缺失或不为 2 时拒绝加载并提示重新生成。
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from src.python.core.registry import get_llm_module_names

SCHEMA_VERSION = 2

#: 每个模块段可写的参数（除 ``enabled`` 与 ``debate`` 外）
MODULE_PARAMS: tuple[str, ...] = (
    "model",
    "temperature",
    "max_tokens",
    "timeout",
    "cache",
    "output_brief",
    "system_prompt",
)

#: 扁平键后缀 → v2 模块字段
FLAT_MODULE_SUFFIXES: tuple[tuple[str, str], ...] = (
    ("system_prompt", "system_prompt"),
    ("model", "model"),
    ("temperature", "temperature"),
    ("max_tokens", "max_tokens"),
    ("timeout", "timeout"),
    ("cache_enabled", "cache"),
    ("output_brief", "output_brief"),
)

#: runtime 段字段 ↔ 扁平键
RUNTIME_FIELDS: tuple[tuple[str, str], ...] = (
    ("max_concurrency", "llm_max_concurrency"),
    ("thinking_concurrency", "llm_max_thinking_concurrency"),
    ("max_retries", "max_retries"),
    ("full_fail_retry_delay_sec", "llm_full_fail_retry_delay"),
    ("time_budget_sec", "llm_total_time_budget_sec"),
    ("daily_cost_limit", "daily_cost_limit"),
)


class LLMSchemaError(ValueError):
    """llm_settings.json 结构/版本不可用（附文件名与重新生成指引）。"""


def _module_names(document: dict[str, Any]) -> list[str]:
    """注册表模块序 + 文档中多出的模块（保留未知模块，便于前向兼容）。"""
    ordered = list(get_llm_module_names())
    extra = [name for name in (document.get("modules") or {}) if name not in ordered]
    return ordered + extra


def merge_defaults(user: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """深合并缺省（只补缺、dict 递归；未知内容原样保留）。"""
    merged = copy.deepcopy(defaults)
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_defaults(value, merged[key])
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def flatten(document: dict[str, Any]) -> dict[str, Any]:
    """v2 文档 → 扁平视图（消费方契约；未知顶层键原样透传）。"""
    flat: dict[str, Any] = {}
    defaults = document.get("defaults") or {}
    modules = document.get("modules") or {}
    enabled: dict[str, bool] = {}

    for name in _module_names(document):
        module = modules.get(name) or {}
        if not isinstance(module, dict):
            continue
        enabled[name] = bool(module.get("enabled", False))
        effective = {**defaults, **{k: v for k, v in module.items() if k not in ("enabled", "thinking", "debate")}}
        for suffix, field in FLAT_MODULE_SUFFIXES:
            if field in effective:
                flat[f"{suffix}_{name}"] = effective[field]
        thinking = {**(defaults.get("thinking") or {}), **(module.get("thinking") or {})}
        if "enabled" in thinking:
            flat[f"thinking_enabled_{name}"] = bool(thinking["enabled"])
        if "budget" in thinking:
            flat[f"thinking_budget_{name}"] = thinking["budget"]
        if "effort" in thinking:
            flat[f"reasoning_effort_{name}"] = thinking["effort"]
        if isinstance(module.get("debate"), dict):
            flat["debate"] = copy.deepcopy(module["debate"])

    flat["enabled_llm"] = enabled

    runtime = document.get("runtime") or {}
    for field, flat_key in RUNTIME_FIELDS:
        if field in runtime:
            flat[flat_key] = runtime[field]
    limits = runtime.get("debate_limits") or {}
    debate = flat.setdefault("debate", {})
    if "max_tokens_per_report" in limits:
        debate["max_total_tokens_per_report"] = limits["max_tokens_per_report"]
    if "call_timeout_override_sec" in limits:
        debate["per_call_timeout_override"] = limits["call_timeout_override_sec"]

    advanced = document.get("advanced") or {}
    if isinstance(advanced.get("fact_check"), dict):
        flat["fact_check"] = copy.deepcopy(advanced["fact_check"])
    news = advanced.get("news_correlation") or {}
    if "top_n" in news:
        flat["news_correlation_top_n"] = news["top_n"]

    known = {"schema_version", "defaults", "modules", "runtime", "advanced"}
    for key, value in document.items():
        if key not in known and key not in flat:
            flat[key] = copy.deepcopy(value)
    return flat


def _set_module_value(modules: dict[str, Any], name: str, field: str, value: Any) -> None:
    module = modules.setdefault(name, {})
    if not isinstance(module, dict):
        module = {}
        modules[name] = module
    if field.startswith("thinking."):
        thinking = module.setdefault("thinking", {})
        thinking[field.split(".", 1)[1]] = value
    else:
        module[field] = value


def apply_flat_updates(document: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """把扁平更新写回 v2 文档（保留未知内容；返回新文档）。"""
    doc = copy.deepcopy(document)
    doc.setdefault("schema_version", SCHEMA_VERSION)
    doc.setdefault("defaults", {})
    modules = doc.setdefault("modules", {})
    runtime = doc.setdefault("runtime", {})
    advanced = doc.setdefault("advanced", {})
    module_names = set(get_llm_module_names())

    runtime_by_flat = dict(RUNTIME_FIELDS)
    handled: set[str] = set()

    for key, value in updates.items():
        if key == "enabled_llm" and isinstance(value, dict):
            for name, flag in value.items():
                module = modules.setdefault(name, {})
                module["enabled"] = bool(flag)
            handled.add(key)
            continue
        if key == "debate" and isinstance(value, dict):
            module = modules.setdefault("expert_review", {})
            module["debate"] = copy.deepcopy(value)
            limits = runtime.setdefault("debate_limits", {})
            if "max_total_tokens_per_report" in value:
                limits["max_tokens_per_report"] = value["max_total_tokens_per_report"]
            if "per_call_timeout_override" in value:
                limits["call_timeout_override_sec"] = value["per_call_timeout_override"]
            handled.add(key)
            continue
        if key == "fact_check" and isinstance(value, dict):
            advanced["fact_check"] = copy.deepcopy(value)
            handled.add(key)
            continue
        if key == "news_correlation_top_n":
            advanced.setdefault("news_correlation", {})["top_n"] = value
            handled.add(key)
            continue
        if key in runtime_by_flat:
            runtime[runtime_by_flat[key]] = value
            handled.add(key)
            continue

        for suffix, field in FLAT_MODULE_SUFFIXES:
            prefix = f"{suffix}_"
            if key.startswith(prefix):
                name = key[len(prefix) :]
                if name in module_names:
                    _set_module_value(modules, name, field, value)
                    handled.add(key)
                break
        if key in handled:
            continue
        for prefix, field in (
            ("thinking_enabled_", "thinking.enabled"),
            ("thinking_budget_", "thinking.budget"),
            ("reasoning_effort_", "thinking.effort"),
        ):
            if key.startswith(prefix):
                name = key[len(prefix) :]
                if name in module_names:
                    _set_module_value(modules, name, field, value)
                    handled.add(key)
                break
        if key in handled:
            continue
        # 未映射的键（如 api_key / provider / 自定义扩展）原样保留在顶层
        doc[key] = value

    return doc


def validate_document(document: Any, *, filename: str = "llm_settings.json") -> dict[str, Any]:
    """校验 v2 结构；失败抛 :class:`LLMSchemaError`（含文件名与重生成指引）。"""
    if not isinstance(document, dict):
        raise LLMSchemaError(
            f"{filename} 根元素不是 JSON 对象；请删除该文件后重新生成（程序会按 schema v{SCHEMA_VERSION} 模板重建）"
        )
    version = document.get("schema_version")
    if version != SCHEMA_VERSION:
        raise LLMSchemaError(
            f"{filename} 的 schema_version={version!r}，本版本只接受 {SCHEMA_VERSION}；"
            f"请删除该文件后重新生成（程序会按 schema v{SCHEMA_VERSION} 模板重建）"
        )
    for section in ("defaults", "modules", "runtime", "advanced"):
        if section in document and not isinstance(document[section], dict):
            raise LLMSchemaError(f"{filename} 的 {section} 段应为 JSON 对象（重新生成可恢复）")
    if not isinstance(document.get("modules"), dict) or not document["modules"]:
        raise LLMSchemaError(f"{filename} 缺少 modules 段（重新生成可恢复）")
    for name, module in document["modules"].items():
        if not isinstance(module, dict):
            raise LLMSchemaError(f"{filename} 的 modules.{name} 应为 JSON 对象（重新生成可恢复）")
        if "enabled" in module and not isinstance(module["enabled"], bool):
            raise LLMSchemaError(f"{filename} 的 modules.{name}.enabled 应为布尔")
    return document


# ── 文本级 patch（写回保注释）：目标叶子为标量时可精确替换 ──────────

_FLAT_TO_PATH: dict[str, tuple[str, ...]] = {
    "llm_max_concurrency": ("runtime", "max_concurrency"),
    "llm_max_thinking_concurrency": ("runtime", "thinking_concurrency"),
    "max_retries": ("runtime", "max_retries"),
    "llm_full_fail_retry_delay": ("runtime", "full_fail_retry_delay_sec"),
    "llm_total_time_budget_sec": ("runtime", "time_budget_sec"),
    "daily_cost_limit": ("runtime", "daily_cost_limit"),
    "news_correlation_top_n": ("advanced", "news_correlation", "top_n"),
    "fact_check": ("advanced", "fact_check"),
}


def flat_key_path(key: str) -> tuple[str, ...] | None:
    """扁平键 → v2 路径（仅确定位置；嵌套 dict 本身不在此转换）。"""
    if key.startswith("enabled_llm."):
        return ("modules", key.split(".", 1)[1], "enabled")
    if key in _FLAT_TO_PATH:
        return _FLAT_TO_PATH[key]
    if key == "debate":
        return ("modules", "expert_review", "debate")
    for suffix, field in FLAT_MODULE_SUFFIXES:
        prefix = f"{suffix}_"
        if key.startswith(prefix):
            return ("modules", key[len(prefix) :], field)
    for prefix, sub in (
        ("thinking_enabled_", "enabled"),
        ("thinking_budget_", "budget"),
        ("reasoning_effort_", "effort"),
    ):
        if key.startswith(prefix):
            return ("modules", key[len(prefix) :], "thinking", sub)
    return None


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def _find_matching_close(text: str, start: int) -> int | None:
    """返回对象/数组闭合括号后的索引（跳过字符串与注释）。"""
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    i = start
    in_string = False
    in_line_comment = False
    in_block_comment = False
    while i < len(text):
        ch = text[i]
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
        elif in_block_comment:
            if ch == "*" and i + 1 < len(text) and text[i + 1] == "/":
                in_block_comment = False
                i += 2
                continue
        elif in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "/" and i + 1 < len(text) and text[i + 1] == "/":
            in_line_comment = True
            i += 2
            continue
        elif ch == "/" and i + 1 < len(text) and text[i + 1] == "*":
            in_block_comment = True
            i += 2
            continue
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return None


def _find_child_value_span(text: str, start: int, end: int, key: str) -> tuple[int, int] | None:
    """在 ``[start, end)`` 容器内定位 ``"key": value`` 的 value 区间（标量或容器）。"""
    pattern = re.compile(r'"' + re.escape(key) + r'"\s*:')
    match = pattern.search(text, start, end)
    if match is None:
        return None
    value_start = _skip_ws(text, match.end())
    if value_start >= end:
        return None
    if text[value_start] in "{[":
        close = _find_matching_close(text, value_start)
        return None if close is None else (value_start, close)
    if text[value_start] == '"':
        i = value_start + 1
        while i < end:
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == '"':
                return value_start, i + 1
            i += 1
        return None
    i = value_start
    while i < end and text[i] not in ",}]\n":
        i += 1
    stop = i
    while stop > value_start and text[stop - 1] in " \t":
        stop -= 1
    return value_start, stop


def _locate_path_span(text: str, path: tuple[str, ...]) -> tuple[int, int] | None:
    """定位 v2 路径的叶子 value 区间（中间段必须为对象，叶子必须是标量）。"""
    from src.python.config._json_patch import _find_top_level_value_span

    if not path:
        return None
    span = _find_top_level_value_span(text, path[0])
    if span is None:
        return None
    current = span
    for key in path[1:]:
        if text[current[0]] != "{":
            return None
        child = _find_child_value_span(text, current[0] + 1, current[1] - 1, key)
        if child is None:
            return None
        current = child
    return None if text[current[0]] in "{[" else current


def patch_document_text(raw: str, updates: dict[str, Any]) -> str | None:
    """在原始 JSONC 文本上按键替换标量（保注释）；任一路径不可定位返回 None。

    嵌套 dict（``enabled_llm`` / ``debate`` / ``fact_check`` 等）由调用方拆成
    子键后再传入；未变更的键不产生文本改动。
    """
    from src.python.config._json_patch import _find_top_level_value_span

    patched = raw
    for key, value in updates.items():
        path = flat_key_path(key)
        if path is None or isinstance(value, (dict, list)):
            return None
        span = _locate_path_span(patched, path)
        if span is None:
            span = _find_top_level_value_span(patched, key)
            if span is None:
                return None
        vs, ve = span
        patched = patched[:vs] + json.dumps(value, ensure_ascii=False) + patched[ve:]
    return patched
