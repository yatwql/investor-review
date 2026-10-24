"""LLM 相关配置校验（开关、报告深度、模块/线路、缓存 TTL 之外的 LLM 语义）。"""

from __future__ import annotations

import logging

from src.python.core.registry import get_known_enabled_llm_keys

logger = logging.getLogger("invest")


def _validate_llm_report_depth(config: dict, issues: int) -> int:
    """校验报告深度档位取值（非法时运行时按 standard 档回落并告警，此处仅登记问题）。"""
    raw = config.get("llm_report_depth")
    if raw is None:
        return issues
    from src.python.llm.depth_profile import REPORT_DEPTH_DEFAULT, REPORT_DEPTH_LEVELS

    valid = isinstance(raw, str) and raw.strip().lower() in REPORT_DEPTH_LEVELS
    if not valid:
        logger.warning(
            "config.json llm_report_depth = %r 不是合法档位（可选 %s），将按 %s 档处理",
            raw,
            " / ".join(REPORT_DEPTH_LEVELS),
            REPORT_DEPTH_DEFAULT,
        )
        issues += 1
    return issues


def _validate_enable_boards(config: dict, issues: int) -> int:
    """验证章节可见性配置（enable_fund_deep_analysis / enable_news / enable_history /
    enable_portfolio_evolution / enable_action）。

    enable_action（行动建议独立章）默认开，缺失视为 True（沿用默认值），
    类型校验逻辑与其余 enable_xxx 一致。
    """
    for key in (
        "enable_fund_deep_analysis",
        "enable_news",
        "enable_history",
        "enable_portfolio_evolution",
        "enable_action",
    ):
        val = config.get(key)
        if val is None:
            continue  # 缺失视为默认值（各章节可见性开关默认 True）
        if not isinstance(val, bool):
            logger.warning("config.json %s = %r 不是布尔值，将使用默认值", key, val)
            issues += 1
    return issues


def _validate_enable_llm(issues: int) -> int:
    """验证 llm_settings.json 中 enabled_llm 字典的子键。

    仅检查格式/拼写错误，不判断业务语义（全关正常——可能是用户主动关闭
    所有 LLM 报告模块但仍需 news_correlation）。缺失视为正常（默认启用）。
    """
    from src.python.config._llm_settings import get_llm_config

    llm_config = get_llm_config()
    if not llm_config:
        return issues
    enabled_map = llm_config.get("enabled_llm")
    if enabled_map is None:
        return issues  # 缺失正常
    if not isinstance(enabled_map, dict):
        logger.warning("llm_settings.json enabled_llm = %r 不是字典", enabled_map)
        return issues + 1

    known_keys = get_known_enabled_llm_keys()
    unknown = [k for k in enabled_map if k not in known_keys]
    if unknown:
        logger.warning("llm_settings.json enabled_llm 中存在未知模块 %s，请检查拼写", unknown)
        issues += 1
    return issues


# ── llm_settings 模块参数范围（加载回落默认 / 面板写入拒绝，共用同一张表） ──

#: 参数路径（相对模块段或 runtime/advanced 段）→ 合法范围/枚举
LLM_PARAM_RANGES: dict[str, tuple[float | int, float | int] | tuple[str, ...]] = {
    "temperature": (0.0, 2.0),
    "max_tokens": (1, 200000),
    "timeout": (5, 600),
    "thinking.budget": (1024, 100000),
    "thinking.effort": ("low", "medium", "high"),
    "debate.procon.synthesis_temperature": (0.0, 2.0),
    "runtime.debate_limits.max_tokens_per_report": (1024, 500000),
    "runtime.debate_limits.call_timeout_override_sec": (5, 600),
}


def _range_text(bounds: tuple[float | int, float | int] | tuple[str, ...]) -> str:
    if bounds and isinstance(bounds[0], str):
        return " / ".join(str(item) for item in bounds)
    return f"[{bounds[0]}, {bounds[1]}]"


def param_violation(param: str, value: object) -> str | None:
    """校验单个参数；返回错误文案（含键名/当前值/合法范围），合法返回 None。"""
    if value is None:
        return None
    bounds = LLM_PARAM_RANGES.get(param)
    if bounds is None:
        return None
    if bounds and isinstance(bounds[0], str):
        if value not in bounds:
            return f"配置项 {param} 取值 {value!r} 不在允许范围（{_range_text(bounds)}）"
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"配置项 {param} 应为数值（当前 {value!r}，合法范围 {_range_text(bounds)}）"
    low, high = bounds
    if not low <= value <= high:
        return f"配置项 {param} 取值 {value!r} 超出范围 {_range_text(bounds)}"
    return None


def _module_default(defaults: dict, module: str, param: str) -> object:
    """取模块参数的出厂默认（模块段优先，其次 defaults 段）。"""
    module_doc = (defaults.get("modules") or {}).get(module) or {}
    section = "thinking" if param.startswith("thinking.") else "debate" if param.startswith("debate.") else None
    if section is None:
        if param in module_doc:
            return module_doc[param]
        return (defaults.get("defaults") or {}).get(param)
    current: object = module_doc
    for part in param.split("."):
        if not isinstance(current, dict) or part not in current:
            current = None
            break
        current = current[part]
    if current is not None:
        return current
    current = defaults.get("defaults") or {}
    for part in param.split(".")[1:]:
        current = current.get(part) if isinstance(current, dict) else None
    return current


def sanitize_document(document: dict, defaults: dict) -> tuple[dict, list[str]]:
    """加载路径：越界/类型错误的模块参数回落到出厂默认并登记告警文案。

    只处理 ``LLM_PARAM_RANGES`` 中列出的参数；枚举与数值共用 ``param_violation``。
    返回 (修正后的文档, 问题列表)；问题列表供调用方逐条写日志。
    """
    import copy

    doc = copy.deepcopy(document)
    issues: list[str] = []
    modules = doc.get("modules") or {}
    for name, module in modules.items():
        if not isinstance(module, dict):
            continue
        checks = [(param, module.get(param)) for param in ("temperature", "max_tokens", "timeout")]
        thinking = module.get("thinking") if isinstance(module.get("thinking"), dict) else {}
        checks += [
            ("thinking.budget", thinking.get("budget")),
            ("thinking.effort", thinking.get("effort")),
        ]
        debate_procon = (
            ((module.get("debate") or {}).get("procon") or {}) if isinstance(module.get("debate"), dict) else {}
        )
        checks.append(("debate.procon.synthesis_temperature", debate_procon.get("synthesis_temperature")))

        for param, value in checks:
            message = param_violation(param, value)
            if message is None:
                continue
            issues.append(f"modules.{name}.{param}: {message}；已回落出厂默认")
            fallback = _module_default(defaults, name, param)
            if param.startswith("thinking."):
                thinking[param.split(".", 1)[1]] = fallback
                module["thinking"] = thinking
            elif param.startswith("debate."):
                procon = module.setdefault("debate", {}).setdefault("procon", {})
                procon["synthesis_temperature"] = fallback
            elif fallback is None:
                module.pop(param, None)
            else:
                module[param] = fallback

    runtime_limits = (
        ((doc.get("runtime") or {}).get("debate_limits") or {}) if isinstance(doc.get("runtime"), dict) else {}
    )
    for param in ("max_tokens_per_report", "call_timeout_override_sec"):
        value = runtime_limits.get(param)
        message = param_violation(f"runtime.debate_limits.{param}", value)
        if message is None:
            continue
        issues.append(f"runtime.debate_limits.{param}: {message}；已回落出厂默认")
        runtime_limits[param] = ((defaults.get("runtime") or {}).get("debate_limits") or {}).get(param)
    return doc, issues
