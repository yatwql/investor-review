"""Web 配置编辑 — 可编辑面（GET）呈现 + 编辑应用（POST）委托。

编辑白名单、值校验、写入分派与写前备份的唯一实现在
``src/python/config/edit_ops.py``（Web / TUI 共用同一函数，校验强度一致）；
本模块保留 Web 面板特有的可编辑面组装（``get_config_edit_surface``），
并公开再导出共享层符号（既有引用保持可用）。
"""

from __future__ import annotations

import logging

from src.python.config import read_llm_settings_file, resolve_output_dir
from src.python.config.edit_ops import (  # noqa: F401  # 公开再导出
    ANON_MODES,
    ConfigEditError,
    apply_config_edit,
    config_backup_file,
    config_edit_whitelist,
)
from src.python.config.features import (
    GROUP_LABELS,
    GROUP_ORDER,
    experimental_flags,
    feature_switch_registry,
    switches_in_group,
)

logger = logging.getLogger("invest")

# LLM 分析章节可编辑开关 = 模块注册表全集（共享单源；辩论三段不在其内，缓存登记在缓存域）
from src.python.core.registry import get_llm_module_names  # noqa: E402


def _llm_tuning_surface() -> list[dict]:
    """LLM 调优项（并发/预算/重试）：清单、范围与说明全部取自共享白名单 ``edit_ops``。"""
    from src.python.config._llm_settings import get_llm_config
    from src.python.config.edit_ops import LLM_TUNING_SPECS

    settings = get_llm_config() or {}
    rows = []
    for key, spec in LLM_TUNING_SPECS.items():
        rows.append(
            {
                "key": key,
                "label": spec["label"],
                "value": settings.get(key, config_edit_whitelist[key].get("default")),
                "min": spec.get("min"),
                "max": spec.get("max"),
                "hint": spec.get("hint", ""),
                "step": 1 if spec["kind"] == "int" else 0.1,
            }
        )
    return rows


def _llm_providers_surface() -> dict:
    """LLM 多链线路面：策略 + 按 priority 升序的线路清单（与 TUI 面板同源展示）。

    Returns:
        ``{"strategy": ..., "providers": [{"name", "provider", "priority"}…]}``；
        providers 顺序 = priority 升序（数值小者链序靠前）。
    """
    from src.python.config import get_llm_providers

    cfg = get_llm_providers()
    providers = [p for p in (cfg.get("providers") or []) if isinstance(p, dict)]
    ordered = sorted(enumerate(providers), key=lambda t: (t[1].get("priority", 99), t[0]))
    return {
        "strategy": str(cfg.get("strategy") or "priority"),
        "providers": [
            {"name": p.get("name"), "provider": p.get("provider"), "priority": p.get("priority", 99)}
            for _idx, p in ordered
        ],
    }


#: 域 → 块（块顺序即渲染顺序）。域与块的划分见 `docs/plan/config-panel-design.md` §4.3；
#: `features.<组键>` 里只放六组「章内内容」开关——独立整章与关联产物走各自块（取自章节注册表）。
_DOMAIN_BLOCKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "report_content",
        ("sections", "llm", "standalone_chapters", "standalone_related"),
    ),
    ("presentation_mechanism", ("anonymization",)),
    ("data_and_routes", ("paths", "indices", "providers")),
    ("llm_run", ("tuning",)),
    ("ops_diagnostics", ("logging", "reference")),
)

#: 六组「章内内容」开关所在的面板（`[S]`）；独立整章/关联产物另立块
_CONTENT_PANEL = "[S]"


def _domain_tui_hint(domain_key: str) -> str:
    """域的 TUI 入口导引（只作阅读导引，不参与交互）。"""
    mapping = {
        "report_content": "TUI：[C] 报告章节显隐 + [S] 报告章节内容",
        "presentation_mechanism": "TUI：[G] 基准与脱敏（匿名化）+ [S] 呈现与交互 / 机制与质量",
        "data_and_routes": "TUI：[G] 目录与文件 / 基准与脱敏（基准）/ LLM 调优第 7 项",
        "llm_run": "TUI：[G]→[L] 运行参数 1-6",
        "ops_diagnostics": "TUI：[D]→[L] 日志设置",
    }
    return mapping.get(domain_key, "")


def _block_domains() -> list[dict]:
    """按 `_DOMAIN_BLOCKS` 派生 `domains`（`features.<组键>` 逐组展开，组键取自面板归属）。"""
    from src.python.config._feature_registry import (
        DOMAIN_HINTS,
        DOMAIN_LABELS,
        DOMAIN_ORDER,
        GROUP_DOMAIN,
        PANEL_GROUPS,
    )

    # `[S]` 的六组即「章内内容」开关；按域再分：四组内容域 + 两组呈现与机制域
    content_groups = [g for g in PANEL_GROUPS[_CONTENT_PANEL] if GROUP_DOMAIN[g] == "report_content"]
    mechanic_groups = [g for g in PANEL_GROUPS[_CONTENT_PANEL] if GROUP_DOMAIN[g] != "report_content"]
    domains: list[dict] = []
    for domain_key in DOMAIN_ORDER:
        blocks: list[str] = []
        for key, base_blocks in _DOMAIN_BLOCKS:
            if key != domain_key:
                continue
            blocks.extend(base_blocks)
            if key == "report_content":
                blocks.extend(f"features.{group}" for group in content_groups)
        if domain_key == "presentation_mechanism":
            blocks.extend(f"features.{group}" for group in mechanic_groups)
        domains.append(
            {
                "key": domain_key,
                "title": DOMAIN_LABELS[domain_key],
                "hint": DOMAIN_HINTS[domain_key],
                "tui": _domain_tui_hint(domain_key),
                "blocks": blocks,
            }
        )
    return domains


def _standalone_blocks() -> tuple[dict, dict]:
    """独立整章 / 关联产物两块的值（键集来自章节注册表，值来自运行时开关）。"""
    from src.python.config.chapter_registry import BLOCK_ARTIFACT, BLOCK_STANDALONE, chapters_in_block
    from src.python.config.features import is_feature_enabled

    def _values(block: str) -> dict:
        return {entry.key: is_feature_enabled(entry.key) for entry in chapters_in_block(block)}

    return _values(BLOCK_STANDALONE), _values(BLOCK_ARTIFACT)


def _logging_surface() -> dict:
    """日志设置面：六项可编辑值 + 枚举/范围 + 「下次启动生效」清单。"""
    from src.python.config._logging import read_logger_config
    from src.python.config.edit_ops import LOGGING_SPECS

    try:
        values = read_logger_config()
    except Exception:  # 版本不符等：面板照常渲染默认值，写入侧仍会给出具体拒绝原因
        logger.warning("读取 logger.json 失败，日志设置按默认展示", exc_info=True)
        values = {}

    items = []
    for key, spec in LOGGING_SPECS.items():
        items.append(
            {
                "key": f"logging.{key}",
                "label": spec["label"],
                "value": values.get(key, spec.get("default")),
                "kind": spec["kind"],
                "options": list(spec.get("options") or ()),
                "min": spec.get("min"),
                "max": spec.get("max"),
                "step": spec.get("step", 1),
                "hint": spec.get("hint", ""),
            }
        )
    return {
        "items": items,
        "restart_keys": ["logging.level", "logging.console_level", "logging.max_bytes", "logging.backup_count"],
    }


def _reference_surface() -> dict:
    """只读参考面：计价参考文件位置与说明（不进编辑面）。"""
    from src.python.config._llm_pricing import get_llm_pricing_path

    return {
        "pricing_path": get_llm_pricing_path(),
        "note": "计价参考按「内置价为基础、文件只覆盖出现的模型与字段」合并；改动后下次读取即生效，不在此面板编辑。",
    }


def _panel_metadata() -> dict:
    """可编辑面的文案与默认值元数据（`labels` / `descriptions` / `defaults` / `needs_hint`）。

    全部由注册表与共享白名单派生——前端不持有任何中文表，也不自算「已改」基准。
    """
    from src.python.config._llm_settings import default_enabled_llm
    from src.python.config._llm_settings_defaults import get_llm_setting_default
    from src.python.config.chapter_registry import chapter_label, chapter_registry
    from src.python.config.edit_ops import LLM_TUNING_SPECS, LOGGING_SPECS
    from src.python.core.registry import get_llm_module_names

    labels: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    defaults: dict[str, object] = {}

    path_labels = {
        "holdings_dir": "持仓信息目录",
        "holdings_filename": "持仓信息文件名",
        "output_dir": "报告输出目录",
    }
    path_descs = {
        "holdings_dir": "持仓 .xlsx 所在目录（绝对路径或相对项目根）",
        "holdings_filename": "读取的持仓文件名（与目录配合定位）",
        "output_dir": "报告输出目录（最新版 + 按日期归档）",
    }
    for key, label in path_labels.items():
        labels[key] = label
        descriptions[key] = path_descs[key]

    for entry in chapter_registry:
        if entry.source != "config":
            continue
        labels[entry.key] = chapter_label(entry)
        descriptions[entry.key] = "顶层章节显隐：关闭后该章整章不出现" + (
            "（仅调仓模拟报告页签）" if entry.artifact_note else ""
        )
        defaults[entry.key] = True

    llm_names = get_llm_module_names()
    llm_defaults = default_enabled_llm()
    for key, name in llm_names.items():
        labels[f"enabled_llm.{key}"] = name
        descriptions[f"enabled_llm.{key}"] = f"标准 LLM 分析章节（llm_settings.json → enabled_llm.{key}）"
        defaults[f"enabled_llm.{key}"] = bool(llm_defaults.get(key, True))

    from src.python.config.features import feature_switch_registry

    for flag, definition in feature_switch_registry.items():
        labels[flag] = definition.label
        descriptions[flag] = definition.desc
        defaults[flag] = definition.default

    for key, spec in LLM_TUNING_SPECS.items():
        labels[key] = spec["label"]
        descriptions[key] = spec.get("hint", "")
        defaults[key] = get_llm_setting_default(key)

    for key, spec in LOGGING_SPECS.items():
        labels[f"logging.{key}"] = spec["label"]
        descriptions[f"logging.{key}"] = spec.get("hint", "")
        defaults[f"logging.{key}"] = spec.get("default")

    # 匿名化枚举：默认档位取自 anonymizer（四档中文描述另行随面下发）
    from src.python.config.anonymizer import ANONYMIZATION_MODE_DESCRIPTIONS  # noqa: F401  # 引用即校验存在

    labels["anonymization.mode"] = "持仓匿名化（代码 / 名称脱敏）"
    descriptions["anonymization.mode"] = "默认关闭（显示真实名称与代码）；仅影响报告生成阶段，不改原始持仓文件"
    defaults["anonymization.mode"] = "off"

    return {
        "labels": labels,
        "descriptions": descriptions,
        "defaults": defaults,
        "needs_hint": [flag for flag, definition in feature_switch_registry.items() if definition.needs_hint],
    }


def get_config_edit_surface() -> dict:
    """读取面板全量可编辑面（GET /api/config/edit）。

    数据来源：config.json（get_config + 章节/子模块访问器）、
    llm_settings.json（enabled_llm 直接读源文件，缺失键默认开，对齐 TUI）、
    features.json（实验性功能开关经运行时覆写读取）。
    """
    from src.python.config import (
        get_config,
        get_default,
        is_enable_action,
        is_enable_fund_deep_analysis,
        is_enable_history,
        is_enable_news,
        is_enable_portfolio_evolution,
    )

    from src.python.config.anonymizer import ANONYMIZATION_MODE_DESCRIPTIONS, get_anonymization_mode
    from src.python.config.features import is_feature_enabled

    config = get_config()
    paths = {
        "holdings_dir": config.get("holdings_dir") or "",
        "holdings_filename": config.get("holdings_filename") or "",
        "output_dir": resolve_output_dir(config),
    }
    sections = {
        "enable_fund_deep_analysis": is_enable_fund_deep_analysis(config),
        "enable_news": is_enable_news(config),
        "enable_history": is_enable_history(config),
        "enable_portfolio_evolution": is_enable_portfolio_evolution(config),
        "enable_action": is_enable_action(config),
    }
    anon_mode = get_anonymization_mode()
    indices = config.get("comparison_indices") or get_default("comparison_indices")

    # LLM enabled_llm：读 llm_settings.json 的**原始落盘值**（配置层唯一读取入口；
    # 未配置 LLM 时 get_llm_config 返回 None，但面板仍要能展示开关）；
    # 缺失键默认开，与 TUI 面板同口径
    snapshot = read_llm_settings_file()
    if snapshot is None:
        logger.warning("读取 llm_settings.json 失败，LLM 开关按默认展示")
        enabled_map: dict = {}
    else:
        enabled_map = snapshot[0].get("enabled_llm") or {}
    surface_enabled = {sfx: bool(enabled_map.get(sfx, True)) for sfx in get_llm_module_names()}
    # 功能开关：按 GROUP_ORDER 四组动态下发（组键/组标题/清单皆由注册表派生，
    # 不硬编码组名，下次分组调整零改动）；显示名、「影响报告」标记与实验项清单
    # 由服务端同源下发——前端不维护任何开关字典，避免与注册表漂移。
    features_surface = {
        "groups": [
            {
                "key": group,
                "title": GROUP_LABELS[group],
                "switches": {flag: is_feature_enabled(flag) for flag, _d in switches_in_group(group)},
            }
            for group in GROUP_ORDER
        ],
        "labels": {flag: d.label for flag, d in feature_switch_registry.items()},
        "experimental": [flag for flag, _d in experimental_flags()],
        "report_affecting": [flag for flag, d in feature_switch_registry.items() if d.affects_report],
    }

    standalone_chapters, standalone_related = _standalone_blocks()

    return {
        "domains": _block_domains(),
        **_panel_metadata(),
        "paths": paths,
        "sections": sections,
        "standalone_chapters": standalone_chapters,
        "standalone_related": standalone_related,
        "anonymization": {
            "mode": anon_mode,
            "options": list(ANON_MODES),
            "labels": {mode: ANONYMIZATION_MODE_DESCRIPTIONS.get(mode, mode) for mode in ANON_MODES},
        },
        "comparison_indices": dict(indices),
        "comparison_indices_defaults": dict(get_default("comparison_indices") or {}),
        "llm": {"enabled_llm": surface_enabled},
        "llm_tuning": _llm_tuning_surface(),
        "llm_providers": _llm_providers_surface(),
        "features": features_surface,
        "logging": _logging_surface(),
        "reference": _reference_surface(),
    }
