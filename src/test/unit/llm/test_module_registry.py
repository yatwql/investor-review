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

#: 四并行单例模块的契约清单（字面量快照，**顺序 = `llm_content` 四元组的位置顺序**）。
#: 字面量在此只做位置契约的锚点：断言写成「前缀 / 差集」这类结构关系，不把实现里的派生
#: 表达式（`tuple(m for m in ... if m != ...)`）抄进断言——那只是同一个表达式自我验算。
_PARALLEL_CONTRACT = ("global_macro", "expert_review", "health_check", "penetration_deep")

_REPO_ROOT = Path(__file__).resolve().parents[4]

#: 「本地声明」允许保留文件后缀（相对 src/python）：core 是最底层、config 在其上，
#: 二者都不得反向 import `llm/`（单向分层），故字面量留在原处，由下方相等断言锁定。
_LAYERING_LOCAL_DECLARATIONS = {
    "core/data_registry.py",
    "core/report_section_registry.py",
    "config/_llm_settings.py",
}


def test_order_and_suffixes_are_one_fact():
    """有序常量与集合常量同源：成员一致、无重复、四并行 = 全集去掉串行后置项（结构关系断言）。"""
    assert PARALLEL_MODULE_ORDER[: len(_PARALLEL_CONTRACT)] == _PARALLEL_CONTRACT, (
        "四并行的成员与顺序即结果元组位置契约（错位会让 zip 整体对不上）"
    )
    assert set(LLM_MODULE_SUFFIXES) == set(LLM_MODULE_ORDER)
    assert len(set(LLM_MODULE_ORDER)) == len(LLM_MODULE_ORDER), "顺序常量不得含重复后缀"
    assert set(LLM_MODULE_ORDER) - set(PARALLEL_MODULE_ORDER) == {NEWS_CORRELATION_MODULE}, (
        "全集与四并行的差集只能是串行后置的新闻关联"
    )
    assert LLM_MODULE_ORDER[: len(PARALLEL_MODULE_ORDER)] == PARALLEL_MODULE_ORDER, (
        "四并行须是全集的前缀：调度顺序一致，不得各自重排"
    )


def test_universe_is_registered_in_authoritative_module_registry():
    """新增后缀只改一处即红：单源全集的每个后缀都须在权威模块注册表登记。

    `core/data_registry._MODULE_REGISTRY` 的 ``settings_suffix`` 决定缓存前缀、
    模块中文名与章节可见性——新增后缀若只加在 `llm/module_registry.py`，
    单源侧看上去一致，运行时则查不到模块名/缓存域。
    """
    registered = {d.settings_suffix for d in data_registry._MODULE_REGISTRY if d.settings_suffix}
    missing = set(LLM_MODULE_SUFFIXES) - registered
    assert missing == set(), (
        f"以下后缀未在 core/data_registry._MODULE_REGISTRY 登记（缓存域/模块名/章节可见性会查不到）：{sorted(missing)}"
    )


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
