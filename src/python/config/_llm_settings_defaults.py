"""LLM 设置默认模板 — llm_settings.json 缺省模板生成。

职责：
  提供 _get_default_llm_settings_template() 函数，返回带中文分组注释的
  llm_settings.json 模板字符串。首次初始化时由 _core.py 的
  _ensure_llm_settings_file() 调用写入磁盘。
"""

from __future__ import annotations

import json
from typing import Any

from src.python.core.registry import get_llm_module_names

# LLM 默认设置（与模板一一对应，确保一致性）
_FLAT_DEFAULTS: dict[str, Any] = {
    "max_retries": 2,
    "llm_max_concurrency": 3,
    # thinking 模块并发上限：2 让 expert_review 与 health_check 并行（实测串行等待
    # 占单次报告墙钟 ~44%，提到 2 即省该时长）；端点出现空内容重试时改回 1
    "llm_max_thinking_concurrency": 2,
    # 全链路失败（网络/超时/接口异常）后整链重试 1 次的等待秒数（0 = 不等待）
    "llm_full_fail_retry_delay": 30,
    # LLM 日费用预算上限（货币数值，0 = 不启用）：与事前费用预估同页展示，
    # 超限时交互渠道询问「用已有结果继续 / 中止」，非交互渠道直接中止
    "daily_cost_limit": 0,
    # LLM 总时间预算（秒，0 = 不启用）：超预算后不再启动新模块（已在跑的模块不打断），
    # 报告按「已生成/因预算跳过」如实呈现。防「单模块卡住 + 重试叠加」把一次报告拖成小时级
    "llm_total_time_budget_sec": 0,
    "enabled_llm": {
        "global_macro": True,
        "expert_review": True,
        "health_check": True,
        "penetration_deep": True,
        "news_correlation": False,
        "self_review": False,
        # 持仓变动复盘归因：章本体由 feature holding_change_review 控制（默认关），
        # 此开关仅在章本体开启后决定是否额外调用一次 LLM 做归因（默认开）
        "holding_change": True,
    },
    "system_prompt_global_macro": None,
    "model_global_macro": None,
    "temperature_global_macro": 0.3,
    "max_tokens_global_macro": 3072,
    "timeout_global_macro": 60,
    "cache_enabled_global_macro": True,
    "output_brief_global_macro": False,
    "thinking_enabled_global_macro": False,
    "thinking_budget_global_macro": 6000,
    "reasoning_effort_global_macro": "high",
    "system_prompt_expert_review": None,
    "model_expert_review": None,
    "temperature_expert_review": 0.3,
    "max_tokens_expert_review": 36000,
    "timeout_expert_review": 120,
    "cache_enabled_expert_review": True,
    "output_brief_expert_review": False,
    "thinking_enabled_expert_review": True,
    "thinking_budget_expert_review": 24000,
    "reasoning_effort_expert_review": "low",
    "system_prompt_health_check": None,
    "model_health_check": None,
    "temperature_health_check": 0.1,
    "max_tokens_health_check": 24000,
    "timeout_health_check": 120,
    "cache_enabled_health_check": True,
    "output_brief_health_check": False,
    "thinking_enabled_health_check": True,
    "thinking_budget_health_check": 18000,
    "reasoning_effort_health_check": "medium",
    "system_prompt_penetration_deep": None,
    "model_penetration_deep": None,
    "temperature_penetration_deep": 0.1,
    "max_tokens_penetration_deep": 12288,
    "timeout_penetration_deep": 90,
    "cache_enabled_penetration_deep": True,
    "output_brief_penetration_deep": False,
    "thinking_enabled_penetration_deep": False,
    "thinking_budget_penetration_deep": 12000,
    "reasoning_effort_penetration_deep": "high",
    # ── 生成后自检（出厂默认关：开启后每次报告额外调用一次 LLM）──
    "system_prompt_self_review": None,
    "model_self_review": None,
    "temperature_self_review": 0.1,
    "max_tokens_self_review": 2048,
    "timeout_self_review": 90,
    "cache_enabled_self_review": True,
    "output_brief_self_review": False,
    "thinking_enabled_self_review": False,
    "thinking_budget_self_review": 6000,
    "reasoning_effort_self_review": "low",
    # ── 持仓变动复盘归因（章本体由 feature holding_change_review 控制，独立章节与回放组默认关）──
    "system_prompt_holding_change": None,
    "model_holding_change": None,
    "temperature_holding_change": 0.2,
    "max_tokens_holding_change": 2048,
    "timeout_holding_change": 90,
    "cache_enabled_holding_change": True,
    "output_brief_holding_change": False,
    "thinking_enabled_holding_change": False,
    "thinking_budget_holding_change": 6000,
    "reasoning_effort_holding_change": "low",
    "system_prompt_news_correlation": None,
    "model_news_correlation": None,
    "temperature_news_correlation": 0.1,
    "max_tokens_news_correlation": 3000,
    "timeout_news_correlation": 60,
    "cache_enabled_news_correlation": True,
    "thinking_enabled_news_correlation": False,
    "thinking_budget_news_correlation": 6000,
    "reasoning_effort_news_correlation": "high",
    "news_correlation_top_n": 30,
    "debate": {
        "procon": {"per_call_max_tokens": 18432, "synthesis_model": None, "synthesis_temperature": 0.5},
        "conditional": {
            "scenarios": [
                {"name": "上涨", "change": 0.20, "desc": "如果未来市场上涨 20%"},
                {"name": "下跌", "change": -0.20, "desc": "如果未来市场下跌 20%"},
                {"name": "震荡", "change": 0.05, "desc": "如果未来市场窄幅震荡±5%"},
            ]
        },
        "concentration_qa": {"threshold": 0.20},
        "max_total_tokens_per_report": 72000,
        "per_call_timeout_override": 90,
    },
    "fact_check": {
        "tolerance": 1.0,
        "tolerance_overrides": {
            "expert_review": 2.0,
            "health_check": 1.0,
            "global_macro": 1.0,
            "penetration_deep": 1.0,
        },
    },
    "pricing": {
        "currency": "CNY",
        # 峰谷定价（DeepSeek 官方方案，北京时间，2026-09-10 起）——模型价格仍以
        # constants.py MODEL_PRICING 为唯一默认源，此处仅配置峰谷时段/时区/周末/节假日规则：
        #   timezone             — 峰谷判定时区（IANA 名称，默认 Asia/Shanghai）
        #   peak_periods         — 高峰时段（"HH:MM-HH:MM" 列表，闭区间，仅高峰日生效）
        #   idle_periods         — 闲时时段（空列表 = 高峰之外的其余时间均按闲时价）
        #   weekend_always_idle  — 周末（周六/周日）全天按闲时价计费（默认 true，
        #                           DeepSeek 官方周末统一低谷价，不区分峰谷）
        #   holiday_always_idle  — 法定节假日（工作日但非 A 股交易日）全天按闲时价计费
        #                           （默认 true，复用交易日历判定，官方 2026-09-10 口径）
        # 含 "peak" 高峰价子段的模型（如 deepseek-flash / deepseek-v4-*）在高峰日（工作日
        # 且非法定节假日）高峰时段按 peak 价计费，其余时段（含周末与法定节假日全天）按
        # base 价计费；无 "peak" 的模型始终按 base 价。
        # 模型价格覆盖示例（含 peak 子段，2026-09-10 12:00 起 flash 系列降价后价格，
        # 正式模型名 deepseek-flash，单位元/百万 token）：
        # "deepseek-flash": {"input": 1.0, "output": 4.0, "input_cache_hit": 0.02,
        # "peak": {"input": 2.0, "output": 8.0, "input_cache_hit": 0.04}}
        "timezone": "Asia/Shanghai",
        "peak_periods": ["09:00-12:00", "14:00-18:00"],
        "idle_periods": [],
        "weekend_always_idle": True,
        "holiday_always_idle": True,
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "input_cache_hit": 0.3},
    },
}

# 模块显示名映射（键 = settings_suffix，与 _DEFAULT_LLM_SETTINGS["enabled_llm"] 对齐）。
# 唯一事实来源为中央注册表（core.registry），此处不再自留副本：模板注释里的模块名
# 曾是与注册表并存的第三份硬编码 —— 注册表改名或新增模块时它不会跟着动，生成的
# 模板注释就与实际模块名静默不一致（不报错，只误导用户）。
_MODULE_LABELS = get_llm_module_names()


_MODULE_DEFAULT_PARAMS: dict[str, Any] = {
    "model": None,
    "temperature": 0.3,
    "max_tokens": 3072,
    "timeout": 60,
    "cache": True,
    "output_brief": False,
    "system_prompt": None,
    "thinking": {"enabled": False, "budget": None, "effort": None},
}


def _build_defaults_v2(flat: dict[str, Any]) -> dict[str, Any]:
    """由扁平出厂值推导 v2 文档（值唯一来源仍是 ``_FLAT_DEFAULTS``）。"""
    from src.python.config._llm_schema import FLAT_MODULE_SUFFIXES, RUNTIME_FIELDS

    modules: dict[str, Any] = {}
    enabled = flat.get("enabled_llm") or {}
    for name in get_llm_module_names():
        module: dict[str, Any] = {"enabled": bool(enabled.get(name, False))}
        for suffix, field in FLAT_MODULE_SUFFIXES:
            value = flat.get(f"{suffix}_{name}")
            if value != _MODULE_DEFAULT_PARAMS.get(field):
                module[field] = value
        thinking: dict[str, Any] = {"enabled": bool(flat.get(f"thinking_enabled_{name}", False))}
        if flat.get(f"thinking_budget_{name}") is not None:
            thinking["budget"] = flat[f"thinking_budget_{name}"]
        if flat.get(f"reasoning_effort_{name}") is not None:
            thinking["effort"] = flat[f"reasoning_effort_{name}"]
        if thinking != _MODULE_DEFAULT_PARAMS["thinking"]:
            module["thinking"] = thinking
        modules[name] = module

    debate = flat.get("debate") or {}
    generated_options = {
        key: debate[key] for key in ("procon", "conditional", "concentration_qa") if isinstance(debate.get(key), dict)
    }
    if generated_options:
        modules.setdefault("expert_review", {})["debate"] = generated_options

    runtime = {field: flat[flat_key] for field, flat_key in RUNTIME_FIELDS if flat_key in flat}
    runtime["debate_limits"] = {
        "max_tokens_per_report": debate.get("max_total_tokens_per_report", 0),
        "call_timeout_override_sec": debate.get("per_call_timeout_override", 0),
    }

    advanced: dict[str, Any] = {}
    if isinstance(flat.get("fact_check"), dict):
        advanced["fact_check"] = flat["fact_check"]
    if "news_correlation_top_n" in flat:
        advanced["news_correlation"] = {"top_n": flat["news_correlation_top_n"]}
    if isinstance(flat.get("pricing"), dict):
        advanced["pricing"] = flat["pricing"]

    return {
        "schema_version": 2,
        "defaults": json.loads(json.dumps(_MODULE_DEFAULT_PARAMS, ensure_ascii=False)),
        "modules": modules,
        "runtime": runtime,
        "advanced": advanced,
    }


_DEFAULTS_NESTED: dict[str, Any] = _build_defaults_v2(_FLAT_DEFAULTS)

#: 扁平出厂值（对外契约；v2 展开后的投影，供编辑白名单/面板/测试取默认值）
from src.python.config._llm_schema import flatten as _flatten_v2  # noqa: E402

_DEFAULT_LLM_SETTINGS: dict[str, Any] = _flatten_v2(_DEFAULTS_NESTED)


def get_llm_setting_default(key: str):
    """读取 llm_settings 的出厂默认值（唯一来源 `_FLAT_DEFAULTS` → v2 投影）。"""
    return _DEFAULT_LLM_SETTINGS.get(key)


_KEY_COMMENTS: dict[str, str] = {
    "model": "模型名；null = 用线路默认模型",
    "temperature": "采样温度（越低越确定）",
    "max_tokens": "单次调用最大输出 token",
    "timeout": "单次调用超时（秒）",
    "cache": "是否启用磁盘缓存",
    "output_brief": "是否要求精简输出",
    "system_prompt": "自定义系统提示词；null = 用内置",
    "thinking.enabled": "是否启用思考模式",
    "thinking.budget": "思考预算 token；null = 用端点默认",
    "thinking.effort": "推理强度 low/medium/high；null = 不指定",
    "max_concurrency": "普通模块并发上限",
    "thinking_concurrency": "思考模块并发上限",
    "max_retries": "单模块重试次数",
    "full_fail_retry_delay_sec": "全链路失败后整链重试等待（秒，0=不等）",
    "time_budget_sec": "报告总时间预算（秒，0=不启用）",
    "daily_cost_limit": "LLM 日费用上限（0=不启用）",
    "max_tokens_per_report": "辩论单报告 token 预算",
    "call_timeout_override_sec": "辩论单次调用超时覆盖（秒，0=沿用模块）",
    "tolerance": "事实校验容差",
    "top_n": "新闻关联条数上限",
    "enabled": "是否启用（模块启停 / 思考模式）",
}


def _comment_for(key: str) -> str:
    return _KEY_COMMENTS.get(key, "")


def _dump_block(value: Any, indent: int) -> list[str]:
    """把值序列化为带缩进的 JSON 行（dict 按键逐行，标量单行）。"""
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return [pad + "{}"]
        lines = [pad + "{"]
        items = list(value.items())
        for i, (key, val) in enumerate(items):
            rendered = _dump_block(val, indent + 2)
            comment = _comment_for(key)
            suffix = "," if i < len(items) - 1 else ""
            if len(rendered) == 1:
                tail = f"  // {comment}" if comment else ""
                lines.append(f"{pad}  {json.dumps(key, ensure_ascii=False)}: {rendered[0].strip()}{suffix}{tail}")
            else:
                lines.append(f"{pad}  {json.dumps(key, ensure_ascii=False)}: {rendered[0].strip()}{suffix}")
                lines.extend(rendered[1:])
        lines.append(pad + "}")
        return lines
    return [pad + json.dumps(value, ensure_ascii=False)]


def _render_defaults_section(defaults: dict[str, Any]) -> list[str]:
    lines = ["  // ── 缺省：所有模块继承；模块内只写差异 ──", '  "defaults": {']
    plain = {k: v for k, v in defaults.items() if k != "thinking"}
    for key, value in plain.items():
        comment = _comment_for(key)
        tail = f"  // {comment}" if comment else ""
        lines.append(f'    "{key}": {json.dumps(value, ensure_ascii=False)},{tail}')
    thinking = defaults.get("thinking") or {}
    lines.append('    "thinking": {')
    items = list(thinking.items())
    for i, (key, value) in enumerate(items):
        suffix = "," if i < len(items) - 1 else ""
        comment = _comment_for(f"thinking.{key}")
        tail = f"  // {comment}" if comment else ""
        lines.append(f'      "{key}": {json.dumps(value, ensure_ascii=False)}{suffix}{tail}')
    lines.append("    }")
    lines.append("  },")
    return lines


def _render_modules_section(modules: dict[str, Any]) -> list[str]:
    labels = get_llm_module_names()
    lines = ["", "  // ── 模块：一个业务对象一段（启停与参数同段；未写项继承 defaults）──", '  "modules": {']
    names = list(modules)
    for index, name in enumerate(names):
        module = modules[name]
        label = labels.get(name, name)
        lines.append(f"    // {label}（{name}）")
        lines.append(f'    "{name}": {{')
        items = list(module.items())
        for i, (key, value) in enumerate(items):
            suffix = "," if i < len(items) - 1 else ""
            if key == "debate":
                rendered = json.dumps(value, ensure_ascii=False, indent=2).splitlines()
                lines.append(f'      "debate": {rendered[0].strip()}')
                lines.extend("      " + line for line in rendered[1:])
                lines[-1] += suffix
                continue
            if isinstance(value, dict):
                rendered = _dump_block(value, 6)
                lines.append(f'      "{key}": {rendered[0].strip()}')
                lines.extend(rendered[1:])
                lines[-1] += suffix
                continue
            comment = _comment_for(key)
            tail = f"  // {comment}" if comment else ""
            lines.append(f'      "{key}": {json.dumps(value, ensure_ascii=False)}{suffix}{tail}')
        lines.append("    }" + ("," if index < len(names) - 1 else ""))
    lines.append("  },")
    return lines


def _render_v2(doc: dict[str, Any]) -> str:
    """把任意 v2 文档渲染为带中文分类注释与逐项说明的 JSONC 文本。"""
    source = doc
    doc = {
        "schema_version": doc.get("schema_version", 2),
        "defaults": doc.get("defaults") or {},
        "modules": doc.get("modules") or {},
        "runtime": doc.get("runtime") or {},
        "advanced": doc.get("advanced") or {},
    }
    lines = [
        "{",
        '  "schema_version": 2,   // 结构版本；缺失或不为 2 时拒绝加载，需删除后重新生成',
        "",
    ]
    lines.extend(_render_defaults_section(doc["defaults"]))
    lines.extend(_render_modules_section(doc["modules"]))
    lines.extend(["", "  // ── 运行约束：并发 / 重试 / 预算（面板「LLM 运行」域）──", '  "runtime": {'])
    runtime = dict(doc["runtime"])
    limits = runtime.pop("debate_limits", {})
    items = list(runtime.items())
    for i, (key, value) in enumerate(items):
        suffix = "," if i < len(items) - 1 or limits else ""
        comment = _comment_for(key)
        tail = f"  // {comment}" if comment else ""
        lines.append(f'    "{key}": {json.dumps(value, ensure_ascii=False)}{suffix}{tail}')
    if limits:
        lines.append('    "debate_limits": {')
        limit_items = list(limits.items())
        for i, (key, value) in enumerate(limit_items):
            suffix = "," if i < len(limit_items) - 1 else ""
            comment = _comment_for(key)
            tail = f"  // {comment}" if comment else ""
            lines.append(f'      "{key}": {json.dumps(value, ensure_ascii=False)}{suffix}{tail}')
        lines.append("    }")
    lines.extend(["  },", "", "  // ── 高级选项：事实校验 / 新闻条数 / 计价覆盖 ──", '  "advanced": {'])
    advanced = doc["advanced"]
    adv_items = list(advanced.items())
    for i, (key, value) in enumerate(adv_items):
        suffix = "," if i < len(adv_items) - 1 else ""
        rendered = _dump_block(value, 4)
        lines.append(f'    "{key}": {rendered[0].strip()}')
        lines.extend(rendered[1:])
        lines[-1] += suffix
    lines.append("  }")
    extra = {
        key: value
        for key, value in source.items()
        if key not in {"schema_version", "defaults", "modules", "runtime", "advanced"}
    }
    if extra:
        lines[-1] = "  },"
        lines.append("")
        lines.append("  // ── 未识别的顶层键（原样保留，供扩展字段使用）──")
        extra_items = list(extra.items())
        for i, (key, value) in enumerate(extra_items):
            suffix = "," if i < len(extra_items) - 1 else ""
            rendered = _dump_block(value, 2)
            lines.append(f'  "{key}": {rendered[0].strip()}')
            lines.extend(rendered[1:])
            lines[-1] += suffix
    lines.extend(["}", ""]) if not extra else lines.extend(["}", ""])
    return "\n".join(lines)


def _get_default_llm_settings_template() -> str:
    """返回 schema v2 默认模板（中文分类注释 + 逐项说明）。

    从 ``_DEFAULTS_NESTED`` 自动生成，保证生成值与代码默认逐键一致（去掉版本后缀的语义名）。
    注释剥离后必须能被 ``json.loads`` 解析（一致性用例锁定）。
    """
    return _render_v2(_DEFAULTS_NESTED)
