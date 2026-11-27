"""LLM 模块键单一事实位（`llm/module_registry`）与各调用点的口径一致性。

覆盖契约：报告侧模块后缀只在 `llm/module_registry.py` 定义一次，其余调用点引用它
派生的常量；「质量评级（四并行模块）」与「模块明细（全集）」两处口径的差集恒为
新闻关联模块——新增模块后缀时两处同步扩张，不会再退化成 4 元素/5 元素各持一份、
新增模块时只改一处而静默丢评级或丢明细行。

少数低层模块（`core/`、`config/`）因分层约束不得反向 import `llm/`，其本地声明
由本用例逐项锁定与单源一致（漂移即红），见 ``_LAYERING_LOCAL_DECLARATIONS``。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.python.config import _llm_settings
from src.python.core import data_registry, report_section_registry
from src.python.llm import _llm_post_pass, fallback, force_scope
from src.python.llm.module_registry import (
    LLM_MODULE_ORDER,
    LLM_MODULE_SUFFIXES,
    PARALLEL_MODULE_ORDER,
)
from src.python.report import llm_module_info, llm_quality

pytestmark = [pytest.mark.unit, pytest.mark.unit_llm]

#: 新闻关联模块：LLM 部分是二次增强，无独立正文可评级、无降级占位。
NEWS_CORRELATION_MODULE = "news_correlation"

_REPO_ROOT = Path(__file__).resolve().parents[4]

#: 「本地声明」允许保留文件后缀（相对 src/python）：core 是最底层、config 在其上，
#: 二者都不得反向 import `llm/`（单向分层），故字面量留在原处，由下方相等断言锁定。
_LAYERING_LOCAL_DECLARATIONS = {
    "core/data_registry.py",
    "core/report_section_registry.py",
    "config/_llm_settings.py",
}


def test_order_and_suffixes_are_one_fact():
    """有序常量与集合常量同源：成员一致、无重复、四并行 = 全集减去新闻关联。"""
    assert set(LLM_MODULE_ORDER) == set(LLM_MODULE_SUFFIXES)
    assert len(set(LLM_MODULE_ORDER)) == len(LLM_MODULE_ORDER), "顺序常量不得含重复后缀"
    assert PARALLEL_MODULE_ORDER == tuple(m for m in LLM_MODULE_ORDER if m != NEWS_CORRELATION_MODULE)


def test_parallel_call_sites_share_the_same_constant():
    """按四元组位置对齐的调用点：直接引用单源对象（新增后缀自动同步，无副本可漂移）。"""
    assert llm_quality._MODULE_KEYS is PARALLEL_MODULE_ORDER
    assert fallback._MODULE_KEYS is PARALLEL_MODULE_ORDER
    assert _llm_post_pass.BASE_MODULES is PARALLEL_MODULE_ORDER


def test_call_site_key_sets_are_subset_of_universe():
    """各调用点使用的模块集合都不得越出单源全集（越界 = 该处自持了别处的键名）。"""
    call_sites = {
        "llm_quality": llm_quality._MODULE_KEYS,
        "fallback": fallback._MODULE_KEYS,
        "_llm_post_pass": _llm_post_pass.BASE_MODULES,
        "llm_module_info": llm_module_info._MODULE_KEYS,
        "data_registry.LLM_MODULE_GATED_SECTIONS": data_registry.LLM_MODULE_GATED_SECTIONS,
        "report_section_registry._LLM_SHEET_NAME_KEYS": report_section_registry._LLM_SHEET_NAME_KEYS,
        "_llm_settings._REPORT_LLM_MODULES": _llm_settings._REPORT_LLM_MODULES,
    }
    for name, keys in call_sites.items():
        assert set(keys) <= set(LLM_MODULE_SUFFIXES), (
            f"{name} 含单源全集之外的模块键：{set(keys) - set(LLM_MODULE_SUFFIXES)}"
        )


def test_quality_and_module_info_calibers_agree():
    """质量评级与模块明细两处口径：明细 = 全集（有序），评级 = 四并行，差集只有新闻关联。"""
    info_keys = list(llm_module_info._MODULE_KEYS)
    quality_keys = tuple(llm_quality._MODULE_KEYS)

    assert info_keys == list(LLM_MODULE_ORDER), "明细行顺序/集合须与单源一致"
    assert set(quality_keys) == set(PARALLEL_MODULE_ORDER)
    assert set(quality_keys) < set(info_keys), "评级模块须是明细模块的真子集"
    assert set(info_keys) - set(quality_keys) == {NEWS_CORRELATION_MODULE}


def test_force_scope_extends_universe_with_post_analysis_modules_only():
    """强刷域 = 报告侧全集（保持调度顺序在前）+ 无章节的后置模块（不得混入全集）。"""
    forceable = force_scope.FORCEABLE_LLM_MODULES

    assert forceable[: len(LLM_MODULE_ORDER)] == LLM_MODULE_ORDER
    assert set(LLM_MODULE_SUFFIXES) <= set(forceable)


def test_layering_local_declarations_match_single_source():
    """分层受限的本地声明：逐项等于单源派生值（漂移即红，而不是静默两套口径）。"""
    assert set(data_registry.LLM_MODULE_GATED_SECTIONS) == set(PARALLEL_MODULE_ORDER)
    assert set(report_section_registry._LLM_SHEET_NAME_KEYS) == set(LLM_MODULE_SUFFIXES)
    assert set(_llm_settings._REPORT_LLM_MODULES) == set(PARALLEL_MODULE_ORDER)


def test_no_module_universe_literal_outside_declared_sites():
    """全仓 `src/python` 扫描：不得再出现「含全部四并行模块」的字面量集合副本。

    只认 ``ast.Tuple/List/Set`` 的纯字符串元素（dict 键、单键集合与真子集另有语义，
    不属副本），故 `PRICE_INDEPENDENT_MODULES` / 提示词范围子集等不会误报。
    """
    parallel = set(PARALLEL_MODULE_ORDER)
    offenders: list[str] = []
    for path in sorted((_REPO_ROOT / "src" / "python").rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT / "src" / "python").as_posix()
        if rel == "llm/module_registry.py" or rel in _LAYERING_LOCAL_DECLARATIONS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                continue
            if not node.elts or not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
                continue
            if parallel <= {e.value for e in node.elts}:
                offenders.append(f"{rel}:{node.lineno}")

    assert offenders == [], f"以下位置复制了 LLM 模块全集字面量，须改用 module_registry 单源：{offenders}"
