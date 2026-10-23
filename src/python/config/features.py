"""功能开关注册表 — Feature Flag 体系。

提供集中管理功能开关的能力，替代分散在各模块中的条件判断。
所有开关在注册表中统一声明默认值，支持运行时启用/禁用。

用法：
  >>> from src.python.config.features import is_feature_enabled, FEATURE_FLAGS
  >>> if is_feature_enabled("metrics_enabled"):
  ...     render_metric_cards()

配置持久化：功能开关可通过 features.json 覆写默认值。
全部开关在 :data:`feature_switch_registry` 一处登记（显示名/说明/作用域分组/
默认值/产物影响/实验身份），TUI 面板、Web 配置面板、CLI 取值域与文档清单一律
由它派生——渠道层不得另写开关清单。分组（呈现与体验 / 分析增强 / 独立章节与
回放 / 机制与诊断）表达**作用域**——「开了长出什么」，是面板主分类轴；
**生命周期**是独立字段 ``experimental``：``--experiment`` 取值域与页脚实验自述
只看该字段，不看分组。「转正」= 把 ``experimental`` 置 False 摘除实验身份；
若作用域同时变化则再改 ``group``。
模块级 LLM 分析章节、新闻源、报告章节等**不在此登记**——它们各有归属文件，
见 ``feature_switch_registry`` 上方说明。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Iterable

from src.python.core.atomic_write import write_json_atomic
from src.python.core.constants import PROJECT_ROOT

from ._feature_registry import (  # noqa: F401 — 兼容既有导入面
    DOMAIN_DATA_AND_ROUTES,
    DOMAIN_HINTS,
    DOMAIN_LABELS,
    DOMAIN_LLM_RUN,
    DOMAIN_OPS_DIAGNOSTICS,
    DOMAIN_ORDER,
    DOMAIN_PRESENTATION_MECHANISM,
    DOMAIN_REPORT_CONTENT,
    EXPERIMENT_ALL,
    GROUP_ANALYSIS,
    GROUP_CHAPTER_OPTIONS,
    GROUP_DOMAIN,
    GROUP_EVENT_SUMMARY,
    GROUP_FUND_STYLE,
    GROUP_LABELS,
    GROUP_MARKET,
    GROUP_MECHANISM,
    GROUP_ORDER,
    GROUP_PORTFOLIO,
    GROUP_PRESENTATION,
    GROUP_STANDALONE,
    PANEL_GROUPS,
    FeatureSwitchDef,
    experimental_flags,
    feature_switch_registry,
    is_experimental_switch,
    switches_in_group,
)

from ._feature_registry import _FEATURE_FLAGS_DEFAULT  # noqa: F401 — 私有派生表，仅本模块使用

logger = logging.getLogger("invest")

# ── 路径常量 ────────────────────────────────────────────────


FEATURES_FILE = os.path.join(PROJECT_ROOT, "data/config/features.json")

# ── 分组常量（作用域轴）───────────────────────────────────────
# 分组表达**作用域**——用户决策心智是「开了长出什么」：
#   GROUP_PORTFOLIO      —— 持仓与交易：成本 / 申赎状态 / 成本收益 / 风险调整
#   GROUP_MARKET         —— 市场与估值：温度 / 估值分位 / 景气度 / 危机回放
#   GROUP_FUND_STYLE     —— 基金与风格：候选比较 / 行业 Beta / 因子目录
#   GROUP_EVENT_SUMMARY  —— 事件与摘要：事件窗 / 情绪热点 / 数据质量 / 本期要点
#   GROUP_PRESENTATION   —— 呈现与交互：图表轴值 / 报告页追问
#   GROUP_MECHANISM      —— 机制与质量：提示词注入 / 输出评级
#   GROUP_STANDALONE     —— 独立章节与回放：新增整页签或多期回放
#   GROUP_CHAPTER_OPTIONS—— 章节内选项：由 [P] 作为章节子项渲染（辩论两项）
# **生命周期是另一根轴**：``FeatureSwitchDef.experimental``（末位默认 False 字段）。
# 此前「默认值」「是否实验项」「分组」三者纠缠在一个 group 字段上：转正会连带
# 摘掉面板入口、
# 组内默认态混合时标签写不准。解耦后：作用域由 group 定、生命周期由
# experimental 定、取值由 default 定——``--experiment`` 取值域与页脚实验自述
# 只看 experimental，「转正」= experimental 置 False（作用域也变时再改 group）。


# 分组标题（TUI 菜单 [S] 与 Web 配置面板共用同一措辞，渠道层不另写文字）
# 面板分块顺序（顺序即渲染顺序；默认开在前、默认关在后、机制收尾）


# ── 功能开关注册表（唯一登记点） ────────────────────────────
# 渠道层（TUI 面板、Web 配置面板、CLI 取值域与提示）与各文档清单一律由此派生，
# **不得另写清单**——一处登记即三面上屏，改一处即三面同步。声明顺序即面板顺序。
#
# 本注册表只登记**有消费者的开关**（全仓必有一处 is_feature_enabled 读取其取值）。
# 其余开关各有归属文件，不在此登记、也不要再往这里搬：
#   - LLM 模块启停 / 基金深度分析模块 → llm_settings.json 的 enabled_llm（TUI 菜单 S
#     标准模块区、Web 配置面板「LLM 分析章节」组）
#   - 新闻源启停 → config.json 的 news_sources
#   - 历史走势与回撤 → config.json 的 enable_history
#   - 基础报告章节（基金深度分析/市场新闻/组合演进/行动建议）→ config.json 的 enable_*
#   - 匿名化模式 → config.json 的 anonymization.mode
# 注：报告增强子模块（数据质量/行业Beta/候选比较/成本流水/估值分位/市场温度/财报摘要/
# 财务指标）登记于本注册表 GROUP_ANALYSIS / GROUP_STANDALONE 分组，取值落 features.json。
# 声明了却无人读取的开关会让用户照文档配置后毫无效果（本注册表曾含 16 项此类
# 陈旧开关，已全部移除）。新增开关必须同时接线到消费点，回归测试见
# test_features.py::TestRegistryLiveness。
#
# ``affects_report`` 是**产物自述的准入口径**：开启该开关后报告产物的内容是否可能
# 不同。``experimental`` 与 ``affects_report`` 双真者进入报告自述（HTML 页脚 /
# Excel 落点）与控制台横幅，读者据此判断手上这份产物是否非默认开关下的结果；
# ``affects_report`` 为 True 的非实验项在 Web 配置面板的项标签上带「（影响报告）」。
# 只改入口可见性的开关答 False，不得凭惯性落进自述——
# 列出一个不改报告任何字节的开关，读者会推断内容受其影响。

# ── 出厂默认值投影 ──────────────────────────────────────────
# 出厂默认值投影：``get_feature_defaults()`` 与兼容既有引用的取值表

# ── 注册表查询 ──────────────────────────────────────────────


# ── 开关名解析（``--experiment`` / ``--feature``） ──────────


# ``--feature NAME=VALUE`` 的取值词表（大小写不敏感）
# 开关取值词表（公开：CLI --feature 与 TUI [S] 面板共用同一词表，避免两处各写一份）
SWITCH_TRUE_TOKENS = frozenset({"on", "true", "1", "yes", "enable", "enabled"})
SWITCH_FALSE_TOKENS = frozenset({"off", "false", "0", "no", "disable", "disabled"})


def _match_experiment(token: str) -> str | None:
    """按开关名（大小写不敏感）或显示名（精确）匹配单个实验功能。

    Returns:
        命中的开关名，未匹配到返回 None
    """
    lowered = token.lower()
    for flag, d in experimental_flags():
        if flag.lower() == lowered or d.label == token:
            return flag
    return None


def resolve_experiment_flags(names: list[str]) -> tuple[set[str], list[str]]:
    """将用户输入的实验功能名解析为开关名集合（注册表驱动）。

    接受三种写法（忽略首尾空白；开关名大小写不敏感）：
      - 开关名：``decision_reflection``
      - 显示名：``决策跨期反思闭环``
      - ``all``：全部实验功能

    Args:
        names: 用户输入的名称列表（空白项自动跳过）

    Returns:
        ``(命中的开关名集合, 未识别的原始名称列表)``；调用方据此决定
        是全部启用还是报错提示可用清单。
    """
    resolved: set[str] = set()
    unknown: list[str] = []
    for raw in names:
        token = (raw or "").strip()
        if not token:
            continue
        if token.lower() == EXPERIMENT_ALL:
            resolved.update(flag for flag, _d in experimental_flags())
            continue
        hit = _match_experiment(token)
        if hit is None:
            unknown.append(raw)
        else:
            resolved.add(hit)
    return resolved, unknown


def describe_experiment_flags() -> str:
    """返回实验功能清单的人类可读串（供 CLI 帮助与报错提示复用）。"""
    return "、".join(f"{flag}（{d.label}）" for flag, d in experimental_flags())


def describe_switches() -> str:
    """返回全部功能开关清单的人类可读串（``--feature`` 报错提示复用）。"""
    return "、".join(f"{flag}（{d.label}）" for flag, d in feature_switch_registry.items())


def resolve_switch_values(pairs: list[tuple[str, bool]] | None) -> list[tuple[str, bool]]:
    """把 ``--feature NAME=VALUE`` 解析结果收敛为待应用的覆写列表。

    Args:
        pairs: argparse 收集的 ``(开关名, 取值)`` 列表（可为 None）

    Returns:
        去重后的 ``(开关名, 取值)`` 列表，后者覆盖前者（同名重复时以最后一次为准）；
        输入为空时返回空列表。
    """
    merged: dict[str, bool] = {}
    for flag, value in pairs or []:
        merged[flag] = value
    return list(merged.items())


def parse_switch_override(token: str) -> tuple[str, bool]:
    """解析 ``--feature`` 的单个取值 ``NAME=VALUE``。

    取值在 argparse ``type`` 回调中即时校验——错误的开关名或取值当场报错并列出
    可选项，而不是等到运行中途静默无效。

    Args:
        token: 形如 ``module_quality_gate=on`` / ``report_qa=off`` 的字符串

    Returns:
        ``(开关名, 取值)``

    Raises:
        ValueError: 缺少 ``=``、开关名未知、或取值不在词表内
    """
    name, sep, raw_value = token.partition("=")
    name = name.strip()
    if not sep or not name:
        raise ValueError("应为 NAME=VALUE 形式（如 module_quality_gate=on）")
    if name not in feature_switch_registry:
        raise ValueError(f"未知功能开关 '{name}'；可选: {describe_switches()}")

    value = raw_value.strip().lower()
    if value in SWITCH_TRUE_TOKENS:
        return name, True
    if value in SWITCH_FALSE_TOKENS:
        return name, False
    raise ValueError(f"开关 '{name}' 的取值 '{raw_value}' 不可识别；可选: on / off")


def parse_switch_value(text: str) -> bool | None:
    """把单个取值文本按开关词表解析为布尔（``None`` = 词表外）。

    与 :func:`parse_switch_override` 共用同一词表：CLI ``--feature NAME=VALUE``
    与 TUI ``[S]`` 面板的 ``键名=值`` 通道因此不会出现「一处认 on、一处只认 true」。

    Args:
        text: 取值文本（大小写不敏感，允许首尾空白），如 ``on`` / ``off`` / ``1``。

    Returns:
        True / False；不在词表内返回 None（调用方自行给出提示）。
    """
    value = text.strip().lower()
    if value in SWITCH_TRUE_TOKENS:
        return True
    if value in SWITCH_FALSE_TOKENS:
        return False
    return None


def enabled_experimental_features() -> list[tuple[str, str]]:
    """返回当前已启用、且**可能改变报告产物**的实验功能 ``[(开关名, 显示名), ...]``。

    报告层用它在**产物自身上**标注生成条件（HTML 页脚 / Excel 落点）——报告是
    可脱离本机流转的文件，读者须能判断内容是否为非默认开关下的产物。

    只列注册表中 ``affects_report`` 为真者：只改交互入口可见性的开关不改报告
    任何字节，列进自述会让读者推断内容受其影响。清单取自 :func:`experimental_flags`
    （生命周期看 ``experimental`` 字段），注册表仍是唯一来源；TUI 菜单 [S] 与
    Web 配置面板渲染的是**全部开关**（含不影响产物者与非实验项），两者用途不同。

    Returns:
        已启用项的 ``(开关名, 显示名)`` 列表，按注册表顺序；无启用项时返回空列表。
    """
    return [(flag, d.label) for flag, d in experimental_flags() if d.affects_report and is_feature_enabled(flag)]


def log_experimental_features() -> None:
    """如果已启用实验性功能，在日志中输出醒目标记，说明具体开启了什么功能。

    唯一调用点为报告入口 ``report/orchestrator.generate_report``（在配置初始化
    之后），故 TUI / CLI / Web 三条入口在生成报告时均会提示——「本次报告受哪些
    实验功能影响」正是需要看到这条信息的时刻。
    级别取 ``INFO``：横幅是生成条件提示而非错误，用 ``ERROR`` 会污染错误统计
    （实测一次运行 68 条 ERROR 中 65 条为本横幅，真错误被淹没）；醒目由
    ``log_reader`` 的装饰横幅标记与报告产物自身的实验标注承担。
    """
    enabled = enabled_experimental_features()
    if not enabled:
        return

    import logging

    logger = logging.getLogger("invest")
    sep = "=" * 48

    logger.info(sep)
    logger.info("  ⚗ 实验性功能已开启！")
    logger.info(sep)
    for flag, name in enabled:
        logger.info("  ⚗ %s — %s", name, feature_switch_registry[flag].desc)
    logger.info(sep)

    # 使用统计（尽力而为，绝不影响报告主链路）：每次生成报告时记录各实验开关
    # 的累计启用次数与最近启用日期，供「转正 / 撤销」决策用客观数据支撑。
    try:
        from src.python.core.experiment_stats import record_experiment_usage

        record_experiment_usage([flag for flag, _name in enabled])
    except Exception:  # noqa: BLE001
        logger.warning("[features] 实验功能使用统计记录失败（不影响报告生成）", exc_info=True)


__all__ = [
    "DOMAIN_DATA_AND_ROUTES",
    "DOMAIN_HINTS",
    "DOMAIN_LABELS",
    "DOMAIN_LLM_RUN",
    "DOMAIN_OPS_DIAGNOSTICS",
    "DOMAIN_ORDER",
    "DOMAIN_PRESENTATION_MECHANISM",
    "DOMAIN_REPORT_CONTENT",
    "EXPERIMENT_ALL",
    "GROUP_CHAPTER_OPTIONS",
    "GROUP_DOMAIN",
    "GROUP_EVENT_SUMMARY",
    "GROUP_FUND_STYLE",
    "GROUP_MARKET",
    "GROUP_PORTFOLIO",
    "PANEL_GROUPS",
    "FEATURE_FLAGS",
    "GROUP_ANALYSIS",
    "GROUP_LABELS",
    "GROUP_MECHANISM",
    "GROUP_ORDER",
    "GROUP_PRESENTATION",
    "GROUP_STANDALONE",
    "FeatureSwitchDef",
    "describe_experiment_flags",
    "describe_switches",
    "enabled_experimental_features",
    "experimental_flags",
    "feature_switch_registry",
    "get_feature_defaults",
    "is_experimental_switch",
    "is_feature_enabled",
    "log_experimental_features",
    "parse_switch_override",
    "resolve_experiment_flags",
    "resolve_switch_values",
    "set_feature_enabled",
    "switches_in_group",
    "load_feature_overrides",
    "save_feature_overrides",
    "reset_feature_flags",
]

# ── 运行时状态 ──────────────────────────────────────────────
# 合并默认值 + 外部覆写后的最终生效值

FEATURE_FLAGS: dict[str, bool] = dict(_FEATURE_FLAGS_DEFAULT)
_FEATURES_LOCK = threading.Lock()


def get_feature_defaults() -> dict[str, bool]:
    """返回功能开关的出厂默认值（不受运行时覆写影响）。"""
    return dict(_FEATURE_FLAGS_DEFAULT)


def is_feature_enabled(flag_name: str) -> bool:
    """检查指定功能开关是否启用。

    Args:
        flag_name: 功能开关名称（如 "llm_global_macro"）

    Returns:
        True 表示功能启用，False 表示功能禁用
    """
    if flag_name not in FEATURE_FLAGS:
        logger.debug("[features] 未知功能开关 '%s'，视为关闭", flag_name)
        return False
    return FEATURE_FLAGS[flag_name]


def set_feature_enabled(flag_name: str, enabled: bool) -> None:
    """运行时切换功能开关状态（不持久化）。

    持久化覆写请调用 save_feature_overrides()。

    Args:
        flag_name: 功能开关名称
        enabled: True 启用 / False 禁用
    """
    if flag_name not in FEATURE_FLAGS:
        logger.warning("[features] 试图设置未知功能开关 '%s'，忽略", flag_name)
        return
    old = FEATURE_FLAGS[flag_name]
    FEATURE_FLAGS[flag_name] = enabled
    if old != enabled:
        logger.info("[features] 功能开关 '%s': %s → %s", flag_name, old, enabled)


def load_feature_overrides() -> None:
    """从 features.json 加载覆写配置，合并到 FEATURE_FLAGS。

    文件中仅需列出需要覆写的开关键值对，未列出的保持默认值。

    JSON 格式：
      {
        "metrics_enabled": true,
        "data_quality": false
      }
    """
    if not os.path.exists(FEATURES_FILE):
        return
    try:
        with open(FEATURES_FILE, encoding="utf-8") as f:
            overrides = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[features] 加载覆写文件失败: %s", e)
        return

    if not isinstance(overrides, dict):
        logger.warning("[features] 覆写文件格式异常（应为 JSON object），忽略")
        return

    valid_count = 0
    changed = 0
    unknown: list[str] = []
    with _FEATURES_LOCK:
        for flag_name, value in overrides.items():
            if isinstance(value, bool) and flag_name in FEATURE_FLAGS:
                changed += FEATURE_FLAGS[flag_name] != value
                FEATURE_FLAGS[flag_name] = value
                valid_count += 1
            elif isinstance(value, bool):
                unknown.append(flag_name)
                FEATURE_FLAGS[flag_name] = value
                valid_count += 1
                changed += 1
            else:
                logger.warning("[features] 覆写 '%s' 值应为 bool，忽略", flag_name)

    # 无消费者开关一次告警（多为陈旧开关或拼写错误）：这类键在本版本不驱动任何
    # 行为，用户照文档配置后会毫无效果，必须让其可见。收集后合并成一条——逐键
    # 打印会在每次启动刷屏，而 features.json 在模块导入时就会加载一次。
    if unknown:
        logger.warning(
            "[features] features.json 含 %d 项无消费者的开关，配置后不产生任何效果"
            "（请核对拼写，或查阅 how-to-config 的功能开关键表）: %s",
            len(unknown),
            "、".join(sorted(unknown)),
        )

    if not valid_count:
        return
    # 只有确实改变了取值才报 INFO：本模块在导入时自动加载一次，调用方（如 CLI
    # 早返回命令的应用开关入口）可能再显式加载一次，重复打印同一条日志是噪声。
    if changed:
        logger.info("[features] 已加载 %d 项功能开关覆写", valid_count)
    else:
        logger.debug("[features] 覆写已生效（%d 项，取值无变化）", valid_count)


def save_feature_overrides(overrides: dict[str, bool], merge: bool = True) -> None:
    """保存功能开关覆写到 features.json。

    Args:
        overrides: {flag_name: enabled} 字典
        merge: True = 合并到现有覆写（覆盖同名键），False = 完全替换
    """
    existing: dict[str, Any] = {}
    if merge and os.path.exists(FEATURES_FILE):
        try:
            with open(FEATURES_FILE, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing.update(overrides)

    # 只保留值为 bool 的条目
    cleaned = {k: v for k, v in existing.items() if isinstance(v, bool)}

    # 落盘委托 core/atomic_write（唯一原语，mkstemp + os.replace）。失败由原语记日志
    # 并返回 False——开关覆写属尽力持久化：写不进盘不影响本次运行（内存态随后同步），
    # 也不应因此中断调用链。
    if write_json_atomic(
        FEATURES_FILE,
        cleaned,
        prefix=".features_",
        log_tag="features",
        noun="功能开关覆写",
    ):
        logger.info("[features] 已保存 %d 项功能开关覆写", len(cleaned))

    # 同步运行时状态
    for flag_name, enabled in cleaned.items():
        FEATURE_FLAGS[flag_name] = enabled


def clear_feature_overrides(flags: Iterable[str] | None = None) -> int:
    """移除功能开关覆写，使开关回到出厂默认（「恢复默认」= 删键而非写入同值）。

    features.json 只存与代码默认的差异，恢复默认在语义上应删除键：批量原子写一份
    剔除目标键后的覆写文件，并把运行时状态同步回 ``_FEATURE_FLAGS_DEFAULT``。
    单键不存在于文件时自然忽略（但运行时仍回默认——会话内 set_feature_enabled
    的临时切换同样被恢复）。

    Args:
        flags: 要恢复的开关键集合；None 表示清空全部覆写（恢复全部默认）。

    Returns:
        从覆写文件中实际移除的键数（文件不存在或无匹配键时为 0）。
    """
    file_keys: dict[str, Any] = {}
    if os.path.exists(FEATURES_FILE):
        try:
            with open(FEATURES_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                file_keys = {k: v for k, v in loaded.items() if isinstance(v, bool)}
        except (json.JSONDecodeError, OSError):
            file_keys = {}

    if flags is None:
        remaining: dict[str, Any] = {}
    else:
        targets = set(flags)
        remaining = {k: v for k, v in file_keys.items() if k not in targets}
    removed = len(file_keys) - len(remaining)

    if len(remaining) != len(file_keys):
        # 与 save_feature_overrides 同一原子写原语；只落 bool 条目（与保存路径口径一致）
        write_json_atomic(
            FEATURES_FILE,
            remaining,
            prefix=".features_",
            log_tag="features",
            noun="功能开关覆写",
        )

    with _FEATURES_LOCK:
        if flags is None:
            for key in list(FEATURE_FLAGS):
                if key in _FEATURE_FLAGS_DEFAULT:
                    FEATURE_FLAGS[key] = _FEATURE_FLAGS_DEFAULT[key]
                else:
                    # 覆写文件已清空，无消费者的运行时残留键一并移除
                    FEATURE_FLAGS.pop(key, None)
        else:
            for key in flags:
                if key in FEATURE_FLAGS and key in _FEATURE_FLAGS_DEFAULT:
                    FEATURE_FLAGS[key] = _FEATURE_FLAGS_DEFAULT[key]

    if removed:
        logger.info("[features] 已恢复 %d 项功能开关覆写至出厂默认", removed)
    return removed


def reset_feature_flags() -> None:
    """重置所有功能开关为默认值（运行时状态，不影响持久化文件）。"""
    with _FEATURES_LOCK:
        FEATURE_FLAGS.clear()
        FEATURE_FLAGS.update(_FEATURE_FLAGS_DEFAULT)
    logger.debug("[features] 功能开关已重置为默认值")


# 模块导入时自动加载覆写
load_feature_overrides()
