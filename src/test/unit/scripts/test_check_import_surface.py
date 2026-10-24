"""导入面观察期检查（check-import-surface.py）的规则与自检。"""

from __future__ import annotations


import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(scope="module")
def surface():
    return load_script("check-import-surface.py", module_name="_check_import_surface_under_test")


def test_real_repo_has_no_import_surface_findings(surface):
    findings, stats = surface.collect()
    assert findings == []
    assert set(stats) == {"compat-comment", "private-all", "cross-private", "dynamic-target"}


def test_compat_marker_is_detected(surface, tmp_path):
    root = tmp_path / "py"
    root.mkdir()
    (root / "mod.py").write_text("# 兼容既有导入面：旧路径\n", encoding="utf-8")
    findings = surface.scan_compat(root)
    assert any("[compat-comment]" in finding and "mod.py" in finding for finding in findings)


def test_private_all_is_detected(surface, tmp_path):
    root = tmp_path / "py"
    root.mkdir()
    (root / "__init__.py").write_text('__all__ = ["_internal", "public"]\n', encoding="utf-8")
    findings = surface.scan_private_all(root)
    assert any("[private-all]" in finding and "_internal" in finding for finding in findings)


def test_cross_package_private_import_is_detected(surface, tmp_path):
    root = tmp_path / "py"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir(parents=True)
    (root / "a" / "__init__.py").write_text("", encoding="utf-8")
    (root / "a" / "_x.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    (root / "b" / "__init__.py").write_text("", encoding="utf-8")
    (root / "b" / "mod.py").write_text("from src.python.a._x import value\n", encoding="utf-8")
    findings = surface.scan_cross_private(root)
    assert any("[cross-private]" in finding and "src.python.a._x" in finding for finding in findings)


def test_dynamic_import_targets_exist():
    """两条 importlib 动态映射的每个目标都能解析（dynamic-target 的变量形态 smoke）。"""
    import importlib.util

    from src.python.fetcher.chain_incremental import _HISTORY_PROVIDER_MAP
    from src.python.fetcher.source_adapter import ADAPTER_MODULES

    targets = (*ADAPTER_MODULES, *_HISTORY_PROVIDER_MAP.values())
    missing = [target for target in targets if importlib.util.find_spec(target) is None]
    assert missing == []
