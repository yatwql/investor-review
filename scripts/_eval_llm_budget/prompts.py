"""提示词常量与特性开关的临时替换（测量期生效、退出还原）。

评测需要在**不改生产常量**的前提下模拟「预算已生效」：本模块用 context manager
临时替换提示词常量与特性开关的绑定，退出即还原。替换点按代码的真实消费位置选择：

  - 标准路径：``src/python/llm/generators_singletons.py`` 的 ``_SYSTEM_EXPERT_REVIEW``
    （该模块 import 时绑定了常量名，改 ``prompts_core`` 不会生效）；
  - 辩论路径：``src/python/llm/generators.py`` 的 PRO / CON 常量（同上），
    以及 ``src/python/llm/prompts_core.py`` 的合成提示（合成函数在调用时读模块全局）；
  - 特性开关：``src/python/config/features.py::is_feature_enabled``，并对已 import
    该函数的模块rebind，避免绑定副本绕过替换。
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

STANDARD_PROMPT_TARGET = ("src.python.llm.generators_singletons", "_SYSTEM_EXPERT_REVIEW")
DEBATE_PROMPT_TARGETS: tuple[tuple[str, str], ...] = (
    ("src.python.llm.generators", "_SYSTEM_DEBATE_PRO"),
    ("src.python.llm.generators", "_SYSTEM_DEBATE_CON"),
    ("src.python.llm.prompts_core", "_SYSTEM_DEBATE_SYNTHESIS"),
    ("src.python.llm.prompts_core", "_SYSTEM_DEBATE_SYNTHESIS_CONDITIONAL"),
)


def _resolve(module_name: str, attr: str) -> tuple[Any, str]:
    module = importlib.import_module(module_name)
    if not hasattr(module, attr):
        raise AttributeError(f"{module_name} 不存在 {attr}（提示词常量位置已变，需同步评测脚本）")
    return module, getattr(module, attr)


@contextmanager
def patched_prompts(standard_suffix: str, *, debate_suffixes: dict[str, str] | None = None) -> Iterator[None]:
    """临时给提示词常量追加预算段。

    Args:
        standard_suffix: 追加到标准提示尾部的预算段。
        debate_suffixes: 辩论路径各角色（pro/con/synthesis/synthesis_conditional）
            的预算段；None 表示不改辩论提示。
    """
    saved: list[tuple[Any, str, Any]] = []
    try:
        module, original = _resolve(*STANDARD_PROMPT_TARGET)
        saved.append((module, STANDARD_PROMPT_TARGET[1], original))
        setattr(module, STANDARD_PROMPT_TARGET[1], original + standard_suffix)

        if debate_suffixes:
            mapping = {
                "_SYSTEM_DEBATE_PRO": "pro",
                "_SYSTEM_DEBATE_CON": "con",
                "_SYSTEM_DEBATE_SYNTHESIS": "synthesis",
                "_SYSTEM_DEBATE_SYNTHESIS_CONDITIONAL": "synthesis_conditional",
            }
            for module_name, attr in DEBATE_PROMPT_TARGETS:
                suffix = debate_suffixes.get(mapping[attr], "")
                if not suffix:
                    continue
                mod, orig = _resolve(module_name, attr)
                saved.append((mod, attr, orig))
                setattr(mod, attr, orig + suffix)
        yield
    finally:
        for module, attr, original in reversed(saved):
            setattr(module, attr, original)


@contextmanager
def patched_features(flags: dict[str, bool]) -> Iterator[None]:
    """临时替换特性开关（未列出的开关沿用既有判定）。

    Args:
        flags: 开关名 → 取值，例如 ``{"llm_debate_procon": True}``。
    """
    from src.python.config import features

    original = features.is_feature_enabled

    def _fake(name: str) -> bool:
        if name in flags:
            return bool(flags[name])
        return bool(original(name))

    rebound: list[tuple[Any, Any]] = []
    features.is_feature_enabled = _fake  # type: ignore[assignment]
    try:
        for module in list(sys.modules.values()):
            if module is None or getattr(module, "is_feature_enabled", None) is not original:
                continue
            try:
                rebound.append((module, original))
                module.is_feature_enabled = _fake  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                continue
        yield
    finally:
        features.is_feature_enabled = original  # type: ignore[assignment]
        for module, _ in rebound:
            module.is_feature_enabled = original  # type: ignore[attr-defined]


def debate_flags(mode: str) -> dict[str, bool]:
    """把评测模式映射为两个辩论开关的取值。

    Args:
        mode: ``standard`` / ``standard-conditional`` / ``debate`` / ``debate-conditional``。

    Returns:
        供 :func:`patched_features` 使用的开关字典。
    """
    if mode == "standard":
        return {"llm_debate_procon": False, "llm_debate_conditional": False}
    if mode == "standard-conditional":
        return {"llm_debate_procon": False, "llm_debate_conditional": True}
    if mode == "debate":
        return {"llm_debate_procon": True, "llm_debate_conditional": False}
    if mode == "debate-conditional":
        return {"llm_debate_procon": True, "llm_debate_conditional": True}
    raise ValueError(f"未知评测模式：{mode}")
