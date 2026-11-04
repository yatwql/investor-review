"""导入面观察期检查（check-import-surface.py）的规则与自检。"""

from __future__ import annotations

import json

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(scope="module")
def surface():
    return load_script("check-import-surface.py", module_name="_check_import_surface_under_test")


def test_real_repo_has_no_import_surface_findings(surface):
    findings, stats = surface.collect()
    assert findings == []
    # 规则集合与其扫描结果逐项对应（新增规则必须同时产出统计键，否则 -v 少报一路）
    assert set(stats) == {
        "compat-comment",
        "private-all",
        "cross-private",
        "dynamic-target",
        "exception-table",
    }
    assert all(count == 0 for count in stats.values())


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


_EXCEPTION_ENTRY = {
    "path": "src/python/nowhere.py",
    "name": "ghost",
    "owner": "core",
    "reason": "历史导入面待迁",
    "expiry": "2099-12-31",
    "replacement": "src.python.core.x",
}


def _use_exception_table(surface, monkeypatch, tmp_path, table) -> None:
    path = tmp_path / "_import_surface_exceptions.json"
    path.write_text(json.dumps(table, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(surface, "EXCEPTIONS_FILE", path)


def test_exception_missing_field_is_metadata_finding(surface, monkeypatch, tmp_path):
    entry = {key: value for key, value in _EXCEPTION_ENTRY.items() if key != "reason"}
    _use_exception_table(surface, monkeypatch, tmp_path, {"compat-comment": [entry]})
    findings = surface.audit_exceptions(surface._load_exceptions())
    assert any("[exception-metadata]" in finding and "reason" in finding for finding in findings)


def test_exception_expiry_must_be_iso_date(surface, monkeypatch, tmp_path):
    entry = {**_EXCEPTION_ENTRY, "expiry": "2099/12/31"}
    _use_exception_table(surface, monkeypatch, tmp_path, {"compat-comment": [entry]})
    findings = surface.audit_exceptions(surface._load_exceptions())
    assert any("[exception-metadata]" in finding and "YYYY-MM-DD" in finding for finding in findings)


def test_expired_exception_is_finding(surface, monkeypatch, tmp_path):
    entry = {**_EXCEPTION_ENTRY, "expiry": "2000-01-01"}
    _use_exception_table(surface, monkeypatch, tmp_path, {"compat-comment": [entry]})
    findings = surface.audit_exceptions(surface._load_exceptions())
    assert any("[exception-expiry]" in finding and "2000-01-01" in finding for finding in findings)


def test_unused_exception_is_stale_finding(surface, monkeypatch, tmp_path):
    """例外登记了但规则已无违规——不再查询即意味着它是永不到期的豁免。"""
    _use_exception_table(surface, monkeypatch, tmp_path, {"compat-comment": [_EXCEPTION_ENTRY]})
    findings = surface.audit_exceptions(surface._load_exceptions())
    assert any("[exception-stale]" in finding for finding in findings)


def test_used_exception_suppresses_finding_and_is_not_stale(surface, monkeypatch, tmp_path):
    py_root = tmp_path / "py"
    py_root.mkdir()
    target = py_root / "mod.py"
    target.write_text("# 兼容既有导入面：旧路径\n", encoding="utf-8")
    entry = {**_EXCEPTION_ENTRY, "path": surface.rel(target), "name": "兼容既有导入面"}
    _use_exception_table(surface, monkeypatch, tmp_path, {"compat-comment": [entry]})
    exceptions = surface._load_exceptions()
    assert surface.scan_compat(py_root, exceptions) == []
    assert surface.audit_exceptions(exceptions) == []


def test_unparsable_exception_table_is_finding(surface, monkeypatch, tmp_path):
    path = tmp_path / "_import_surface_exceptions.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(surface, "EXCEPTIONS_FILE", path)
    findings, stats = surface.collect()
    assert any("[exception-metadata]" in finding and "无法解析" in finding for finding in findings)
    assert stats == {"exception-table": 1}
