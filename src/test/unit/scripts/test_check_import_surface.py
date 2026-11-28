"""导入面观察期检查（check-import-surface.py）的规则与自检。"""

from __future__ import annotations

import json

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(scope="module")
def surface():
    return load_script("check-import-surface.py", module_name="_check_import_surface_under_test")


@pytest.mark.real_repo  # 与 pre-commit 钩子同一守护、同一棵树：不进 dev-verify
def test_real_repo_has_no_import_surface_findings(surface):
    findings, stats = surface.collect()
    assert findings == []
    # 规则集合与其扫描结果逐项对应（新增规则必须同时产出统计键，否则 -v 少报一路）
    assert set(stats) == {
        "compat-comment",
        "private-all",
        "cross-private",
        "cross-private-scripts",
        "dynamic-target",
        "layer-inversion",
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


class TestScriptsCrossPrivate:
    """`scripts/` 侧私有模块导入：口径同 `src/python` 的 cross-private（只判模块面）。"""

    @pytest.fixture(name="roots")
    def _roots(self, tmp_path):
        py_root = tmp_path / "py"
        pkg = py_root / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "_impl.py").write_text("X = 1\n", encoding="utf-8")
        (pkg / "public.py").write_text("Y = 1\n", encoding="utf-8")
        scripts_root = tmp_path / "scripts"
        scripts_root.mkdir()
        return py_root, scripts_root

    def test_private_module_import_in_script_is_reported(self, surface, roots):
        py_root, scripts_root = roots
        (scripts_root / "shot.py").write_text("from src.python.pkg._impl import X\n", encoding="utf-8")
        findings = surface.scan_cross_private_scripts(py_root, None, scripts_root)
        assert any("[cross-private-scripts]" in f and "src.python.pkg._impl" in f for f in findings)

    def test_package_facade_private_submodule_is_reported(self, surface, roots):
        """`from src.python.pkg import _impl`（从包门面取私有子模块）同判。"""
        py_root, scripts_root = roots
        (scripts_root / "shot.py").write_text("from src.python.pkg import _impl\n", encoding="utf-8")
        findings = surface.scan_cross_private_scripts(py_root, None, scripts_root)
        assert any("src.python.pkg._impl" in f for f in findings)

    def test_public_module_private_symbol_and_shared_import_allowed(self, surface, roots):
        """公开模块的私有**符号**导入与 `scripts` 内部互引均不在本规则内。"""
        py_root, scripts_root = roots
        (scripts_root / "shot.py").write_text(
            "from src.python.pkg.public import _Y\nfrom _shared.checklib import rel\nfrom src.python.pkg import public\n",
            encoding="utf-8",
        )
        assert surface.scan_cross_private_scripts(py_root, None, scripts_root) == []

    def test_excepted_script_private_import_is_suppressed(self, surface, monkeypatch, tmp_path, roots):
        py_root, scripts_root = roots
        script = scripts_root / "shot.py"
        script.write_text("from src.python.pkg._impl import X\n", encoding="utf-8")
        entry = {
            **_EXCEPTION_ENTRY,
            "path": surface.rel(script),
            "name": "src.python.pkg._impl",
        }
        _use_exception_table(surface, monkeypatch, tmp_path, {"cross-private-scripts": [entry]})
        exceptions = surface._load_exceptions()
        assert surface.scan_cross_private_scripts(py_root, exceptions, scripts_root) == []
        assert surface.audit_exceptions(exceptions) == []


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


def test_layer_inversion_detected(surface, tmp_path):
    """三层反向依赖均报 layer-inversion：analysis→report/llm、fetcher→report/analysis、providers→report/analysis。"""
    root = tmp_path / "py"
    for layer in ("analysis", "fetcher", "providers", "report", "llm", "core", "tui", "web", "cache", "config"):
        (root / layer).mkdir(parents=True)
    (root / "analysis" / "a1.py").write_text(
        "from src.python.report.data_status import get_tracker\n", encoding="utf-8"
    )
    (root / "analysis" / "a2.py").write_text("import src.python.llm.skeleton\n", encoding="utf-8")
    (root / "fetcher" / "f1.py").write_text(
        "from src.python.analysis.fee_schedule_model import parse_fee_percent\n", encoding="utf-8"
    )
    (root / "providers" / "p1.py").write_text(
        "from src.python.report.data_status import mark_data_used\n", encoding="utf-8"
    )
    # 报告/llm 层不得反向依赖交互层（tui/web/cli）的格式化与状态条实现
    (root / "report" / "r1.py").write_text("from src.python.tui.live_status import LiveStatusBar\n", encoding="utf-8")
    (root / "llm" / "l1.py").write_text("from src.python.web.progress import WebProgressReporter\n", encoding="utf-8")
    # 基础设施层同样单向：cache 可编排取数但不得依赖报告层，config 不得依赖分析层实现
    (root / "cache" / "c1.py").write_text(
        "from src.python.report.market_value import classify_holdings\n", encoding="utf-8"
    )
    (root / "config" / "g1.py").write_text(
        "from src.python.analysis.drawdown_events import MIN_SPAN\n", encoding="utf-8"
    )
    findings = surface.scan_layer_inversion(root)
    assert any("[layer-inversion]" in f and "a1.py" in f and "report.data_status" in f for f in findings)
    assert any("[layer-inversion]" in f and "a2.py" in f and "llm.skeleton" in f for f in findings)
    assert any("[layer-inversion]" in f and "f1.py" in f and "analysis.fee_schedule_model" in f for f in findings)
    assert any("[layer-inversion]" in f and "p1.py" in f and "report.data_status" in f for f in findings)
    assert any("[layer-inversion]" in f and "r1.py" in f and "tui.live_status" in f for f in findings)
    assert any("[layer-inversion]" in f and "l1.py" in f and "web.progress" in f for f in findings)
    assert any("[layer-inversion]" in f and "c1.py" in f and "report.market_value" in f for f in findings)
    assert any("[layer-inversion]" in f and "g1.py" in f and "analysis.drawdown_events" in f for f in findings)


def test_layer_inversion_core_import_allowed(surface, tmp_path):
    """下层依赖 core 合法（core 是公共面）。"""
    root = tmp_path / "py"
    for layer in ("analysis", "fetcher", "providers", "core"):
        (root / layer).mkdir(parents=True)
    (root / "analysis" / "mod.py").write_text("from src.python.core.num_utils import finite_or\n", encoding="utf-8")
    (root / "fetcher" / "mod.py").write_text("from src.python.core.degradation import get_tracker\n", encoding="utf-8")
    (root / "providers" / "mod.py").write_text(
        "from src.python.core.degradation import mark_data_used\n", encoding="utf-8"
    )
    assert surface.scan_layer_inversion(root) == []


def test_layer_inversion_exception_suppresses_and_is_used(surface, monkeypatch, tmp_path):
    """例外表命中即放行，并登记为 used（避免被判「从未命中的陈货」）。"""
    root = tmp_path / "py"
    (root / "fetcher").mkdir(parents=True)
    (root / "analysis").mkdir(parents=True)
    target = root / "fetcher" / "mod.py"
    target.write_text("from src.python.analysis.fee_schedule_model import parse_fee_percent\n", encoding="utf-8")
    monkeypatch.setattr(surface, "rel", lambda path: "fetcher/mod.py")
    exc = surface.ExceptionTable(
        surface.EXCEPTIONS_FILE,
        surface.table_spec("import-surface").rules,
        {
            "layer-inversion": [
                {"path": "fetcher/mod.py", "name": "src.python.analysis.fee_schedule_model"},
            ]
        },
    )
    assert surface.scan_layer_inversion(root) != []
    assert surface.scan_layer_inversion(root, exc) == []
    assert ("layer-inversion", "fetcher/mod.py", "src.python.analysis.fee_schedule_model") in exc.used
