"""LLM 模块级强刷范围解析 —— force 从全局布尔升级为按模块粒度。

`--force-llm`（全局）只能全量绕缓存重跑，只想重生成某个不满意的模块（如
智囊团复盘）时只能全量烧钱或手改缓存文件。本模块把「哪些模块要强刷」
归一为模块键集合，供三端（CLI `--llm-module` / TUI 交互多选 / Web 勾选）
与共享层（编排器/分发层/串行后置模块）共用同一套键名与校验。

设计要点：
- **沿用既有模块指纹缓存键**：强刷不改任何缓存键构造，仅按模块把
  ``can_cache`` 置 False / 传 ``force=True`` 跳过缓存读，写侧键不变。
- **键名单一来源**：可强刷模块键 = 中央注册表 ``settings_suffix`` 的子集，
  中文标签经 ``core.registry.get_llm_module_names()`` 派生，渠道不自持副本。
- **全局 force 与现状兼容**：``resolve_force_scope(True, None)`` 返回全集，
  与旧 ``force=True`` 全量强刷行为一致（新闻关联 LLM 增强此前不受 force
  控制，本模块将其纳入强刷域——「强制重新生成 LLM 内容」理应含新闻增强）。
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = [
    "FORCEABLE_LLM_MODULES",
    "resolve_force_scope",
    "is_module_forced",
]

# 可强刷模块键（有序，与四并行 + 新闻关联 + 串行后置的调度顺序一致）。
# 新增 LLM 强刷粒度在此登记；键必须与 core/registry.py 的 settings_suffix 一致。
FORCEABLE_LLM_MODULES: tuple[str, ...] = (
    "global_macro",
    "expert_review",
    "health_check",
    "penetration_deep",
    "news_correlation",
    "self_review",
    "holding_change",
)


def resolve_force_scope(force_all: bool, modules: Iterable[str] | None = None) -> frozenset[str]:
    """归一化强刷请求为模块键集合。

    显式模块列表优先于全局开关（粒度优先）：``--llm-module expert_review
    --force-llm`` 只强刷 expert_review。

    Args:
        force_all: 全局强刷开关（``--force-llm``），True 且未显式指定模块时返回全集。
        modules: 显式指定的模块键列表（``--llm-module`` / TUI 多选 / Web 勾选），
            可为 None 或空（均视为未指定）。

    Returns:
        需强刷的模块键 frozenset；两者都未给时为空集（全部照常命中缓存）。

    Raises:
        ValueError: ``modules`` 含不可强刷的键名（报错并列出全部合法键）。
    """
    if modules:
        requested = {str(m).strip() for m in modules if str(m).strip()}
        unknown = requested - set(FORCEABLE_LLM_MODULES)
        if unknown:
            raise ValueError(
                f"不可强刷的 LLM 模块: {', '.join(sorted(unknown))}（可选: {', '.join(FORCEABLE_LLM_MODULES)}）"
            )
        return frozenset(requested)
    if force_all:
        return frozenset(FORCEABLE_LLM_MODULES)
    return frozenset()


def is_module_forced(scope: frozenset[str], module_key: str) -> bool:
    """判定单个模块是否在强刷范围内。"""
    return module_key in scope
