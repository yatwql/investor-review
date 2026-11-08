"""风格因子回归计算层的重依赖惰性化（pandas/numpy 缺失边界）。

回归场景：`analysis/style_factor_regression.py` 曾在**模块顶层** `import pandas as pd`，
而调用点（`report/_report_factor_metrics.py`）在函数内导入该模块且不在 try 内——
裸解释器（系统 Python，无 pandas）跑 full 报告时，异常从数据准备阶段冒泡到
`generate_report`，整份报告失败，而不是按 §1.4.5 让该区块降级为 available=False。

本文件锁两件事：

① 重依赖缺失时**模块本身仍可导入**（惰性导入 + TYPE_CHECKING 类型注释）；
② 真正调用计算入口时才抛 ImportError——由编排层捕获并降级，不是静默硬算。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from src.python.analysis import style_factor_regression as sfr

pytestmark = [pytest.mark.unit, pytest.mark.unit_analysis, pytest.mark.edge]

_SFR_PATH = Path(sfr.__file__).resolve()


def _block(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    """把模块名映射为 None：后续 `import <name>` 抛 ImportError（等价于未安装）。"""
    for name in names:
        monkeypatch.setitem(sys.modules, name, None)


class TestNumericStackLazyImport:
    def test_module_body_has_no_top_level_numeric_import(self):
        """模块顶层不得出现 pandas/numpy 导入（缺库时模块导入即失败的那类写法）。"""
        tree = ast.parse(_SFR_PATH.read_text(encoding="utf-8"))
        top_level_imports = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                top_level_imports |= {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_level_imports.add(node.module)

        assert not {"pandas", "numpy"} & top_level_imports
        assert sfr.FACTOR_INDICES, "常量仍须在模块顶层可用（编排层要用它建取数任务）"

    def test_compute_entry_raises_import_error_when_dependency_missing(self, monkeypatch):
        """计算入口真正用到重依赖时才抛 ImportError（供编排层捕获降级）。"""
        _block(monkeypatch, "pandas")
        with pytest.raises(ImportError):
            sfr.compute_factor_exposure(
                [{"date": "2026-09-01", "return": 0.01}],
                {"size": [{"date": "2026-09-01", "return": 0.02}]},
            )

    def test_unavailable_result_works_without_dependencies(self, monkeypatch):
        """降级契约工厂是纯字典装配，缺重依赖时仍须可用（编排层拿它兜底）。"""
        _block(monkeypatch, "pandas", "numpy")
        result = sfr.unavailable_result("source_failed")
        assert result["available"] is False
        assert result["status"] == "source_failed"
        assert result["betas"] == {}
