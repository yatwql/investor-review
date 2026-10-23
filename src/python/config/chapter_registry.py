"""报告章节注册表（配置面板视点）——``[C]`` 面板的唯一事实来源。

与 :mod:`core.report_section_registry` 的分工：后者描述**报告产物**（章节顺序 /
导航分组 / 页签名称），本模块描述**章节开关在配置面板中如何呈现**（分块 / 来源
文件 / 稳定键名 / 子项）。两者以键名对齐、互不派生：报告章节的增删由产物侧
注册表决定，而配置面板只呈现已登记、可开关的章节。

四个分块按来源划分（``BLOCK_ORDER``）：

  - 顶层章节：``config.json`` 的 ``enable_*`` 布尔键（5 项）
  - LLM 章节：``llm_settings.json`` 的 ``enabled_llm.<模块>``（7 项）
  - 默认关闭的整章：``features.json`` 的独立章节开关（3 项）
  - 关联产物：``features.json`` 的产物页签开关（1 项，仅调仓模拟报告）

编号由本表顺序派生（:func:`chapter_numbers`）；智囊团的生成选项作为子项挂在
其章节下（:func:`sub_item_numbers` 派生 ``7.1`` 这类编号）——面板与测试都不得
写死编号，稳定入口是键名（``?键名``）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

BLOCK_TOP = "top"
BLOCK_LLM = "llm"
BLOCK_STANDALONE = "standalone"
BLOCK_ARTIFACT = "artifact"

BLOCK_ORDER: tuple[str, ...] = (BLOCK_TOP, BLOCK_LLM, BLOCK_STANDALONE, BLOCK_ARTIFACT)

BLOCK_LABELS: dict[str, str] = {
    BLOCK_TOP: "顶层章节",
    BLOCK_LLM: "LLM 章节",
    BLOCK_STANDALONE: "默认关闭的整章",
    BLOCK_ARTIFACT: "关联产物",
}

SOURCE_CONFIG = "config"
SOURCE_LLM = "llm_settings"
SOURCE_FEATURES = "features"

SOURCE_FILES: dict[str, str] = {
    SOURCE_CONFIG: "config.json",
    SOURCE_LLM: "llm_settings.json",
    SOURCE_FEATURES: "features.json",
}


@dataclass(frozen=True)
class ChapterEntry:
    """单条章节声明。

    Attributes:
        key: 稳定键名（``config.json`` 键 / LLM 模块键 / 功能开关键）——面板
            ``?键名`` 查询与写路径都以它为锚，编号漂移不影响定位
        block: 所属分块（``BLOCK_*``，决定 ``[C]`` 面板的四块排版）
        source: 取值来源（``SOURCE_*``，决定读写落到哪份配置文件）
        label: 显示名；空串表示由来源注册表派生（LLM 模块名 / 功能开关显示名）
        sub_items: 章节下的生成选项（功能开关键，按显示顺序；只影响章内内容）
        artifact_note: 关联产物的归属说明（仅 ``BLOCK_ARTIFACT`` 非空）
    """

    key: str
    block: str
    source: str
    label: str = ""
    sub_items: tuple[str, ...] = ()
    artifact_note: str = ""


#: 章节清单（顺序即 ``[C]`` 编号序，四块按 ``BLOCK_ORDER`` 连续排列）
chapter_registry: tuple[ChapterEntry, ...] = (
    ChapterEntry("enable_fund_deep_analysis", BLOCK_TOP, SOURCE_CONFIG, "基金深度分析"),
    ChapterEntry("enable_news", BLOCK_TOP, SOURCE_CONFIG, "市场新闻"),
    ChapterEntry("enable_history", BLOCK_TOP, SOURCE_CONFIG, "组合历史走势+回撤"),
    ChapterEntry("enable_portfolio_evolution", BLOCK_TOP, SOURCE_CONFIG, "组合演进"),
    ChapterEntry("enable_action", BLOCK_TOP, SOURCE_CONFIG, "行动建议"),
    ChapterEntry("global_macro", BLOCK_LLM, SOURCE_LLM),
    ChapterEntry(
        "expert_review",
        BLOCK_LLM,
        SOURCE_LLM,
        sub_items=("llm_debate_procon", "llm_debate_conditional"),
    ),
    ChapterEntry("news_correlation", BLOCK_LLM, SOURCE_LLM),
    ChapterEntry("health_check", BLOCK_LLM, SOURCE_LLM),
    ChapterEntry("penetration_deep", BLOCK_LLM, SOURCE_LLM),
    ChapterEntry("self_review", BLOCK_LLM, SOURCE_LLM),
    ChapterEntry("holding_change", BLOCK_LLM, SOURCE_LLM),
    ChapterEntry("rebalance_schedule_replay", BLOCK_STANDALONE, SOURCE_FEATURES),
    ChapterEntry("holding_change_review", BLOCK_STANDALONE, SOURCE_FEATURES),
    ChapterEntry("stock_fundamentals", BLOCK_STANDALONE, SOURCE_FEATURES),
    ChapterEntry("whatif_trade_cost", BLOCK_ARTIFACT, SOURCE_FEATURES, artifact_note="仅调仓模拟报告"),
)


def chapters_in_block(block: str) -> tuple[ChapterEntry, ...]:
    """取某分块的全部章节（保持注册表顺序）。"""
    return tuple(entry for entry in chapter_registry if entry.block == block)


def chapter_numbers() -> tuple[tuple[int, ChapterEntry], ...]:
    """章节目录序：``((1, entry), (2, entry), ...)``，编号从 1 连续派生。"""
    return tuple(enumerate(chapter_registry, 1))


def chapter_number(key: str) -> int:
    """章节键名 → 面板编号；未登记抛 :class:`KeyError`（防静默错位）。"""
    for number, entry in chapter_numbers():
        if entry.key == key:
            return number
    raise KeyError(f"报告章节注册表未登记：{key}")


def sub_item_numbers() -> dict[str, str]:
    """子项编号 → 功能开关键（``{"7.1": "llm_debate_procon", ...}``，由父项编号派生）。"""
    numbered: dict[str, str] = {}
    for number, entry in chapter_numbers():
        for offset, flag in enumerate(entry.sub_items, 1):
            numbered[f"{number}.{offset}"] = flag
    return numbered


def chapter_by_key(key: str) -> ChapterEntry | None:
    """按稳定键名取章节（子项键名亦返回其父章节，供 ``?键名`` 定位）。"""
    for entry in chapter_registry:
        if entry.key == key or key in entry.sub_items:
            return entry
    return None


def chapter_edit_key(entry: ChapterEntry) -> str:
    """写入编辑层的键名：LLM 章节目录落在 ``enabled_llm.<模块>``，其余即原键。"""
    return f"enabled_llm.{entry.key}" if entry.source == SOURCE_LLM else entry.key


def chapter_storage(entry: ChapterEntry) -> str:
    """章节的存储位置说明（面板 ``?`` 详情与文档同源）。"""
    return f"{SOURCE_FILES[entry.source]} → {chapter_edit_key(entry)}"


def chapter_label(entry: ChapterEntry, llm_names: Mapping[str, str] | None = None) -> str:
    """章节显示名：配置项取注册表名，LLM / 功能开关取各自注册表（单一来源）。"""
    if entry.label:
        return entry.label
    if entry.source == SOURCE_LLM:
        if llm_names is None:
            from src.python.core.registry import get_llm_module_names

            llm_names = get_llm_module_names()
        return llm_names.get(entry.key, entry.key)
    from src.python.config._feature_registry import feature_switch_registry

    definition = feature_switch_registry.get(entry.key)
    return definition.label if definition is not None else entry.key


def chapter_default(entry: ChapterEntry) -> bool:
    """章节出厂默认值：顶层章节默认开；LLM / 功能开关取各自注册表默认值。"""
    if entry.source == SOURCE_CONFIG:
        return True
    if entry.source == SOURCE_LLM:
        from src.python.config._llm_settings import default_enabled_llm

        return bool(default_enabled_llm().get(entry.key, True))
    from src.python.config._feature_registry import feature_switch_registry

    definition = feature_switch_registry.get(entry.key)
    return bool(definition.default) if definition is not None else True


__all__ = [
    "BLOCK_ARTIFACT",
    "BLOCK_LABELS",
    "BLOCK_LLM",
    "BLOCK_ORDER",
    "BLOCK_STANDALONE",
    "BLOCK_TOP",
    "SOURCE_CONFIG",
    "SOURCE_FEATURES",
    "SOURCE_FILES",
    "SOURCE_LLM",
    "ChapterEntry",
    "chapter_by_key",
    "chapter_default",
    "chapter_edit_key",
    "chapter_label",
    "chapter_number",
    "chapter_numbers",
    "chapter_registry",
    "chapter_storage",
    "chapters_in_block",
    "sub_item_numbers",
]
