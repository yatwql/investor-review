"""子进程入口覆盖归并的量测域契约：只并 ``src/python``，测试文件自身不进汇总口径。

覆盖口径的「语句总数」是 `src/python` 的行数。子进程入口执行器过去按
``--source <root>/src`` 量测并无条件归并，子进程导入的任何 ``src/test`` 文件都被记成
「被量测代码」并进本进程数据——实测全量 unit 跑完 ``coverage report`` 给出
167724 语句 / 30%（真实口径 4.99 万 / 99.8%），944 个文件落在 ``src/python`` 之外。
本文件是该缺陷的回归守卫：量测域收紧到 ``src/python``（与 pytest-cov 的 ``--cov``
同一常量来源），归并前再按域过滤一遍。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.python.core import constants
from src.test import _script_loader
from src.test._subprocess_coverage import _merge_child_data, run_entry_child

pytestmark = [pytest.mark.unit, pytest.mark.unit_core]

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

#: 子进程脚本：故意同时导入 src/python 与 src/test 各一个模块——前者应进覆盖数据，
#: 后者（量测者自身）不应对汇总口径有任何贡献
_CHILD_CODE = """
from src.python.core.constants import APP_NAME
from src.test._script_loader import SCRIPTS_DIR

print(APP_NAME, SCRIPTS_DIR.name)
"""


def _stub_current_coverage(monkeypatch, coverage_mod, data_file: Path):
    """把 ``Coverage.current()`` 指向一个**未启动**的实例（只做数据容器）。

    真实的当前量测归 pytest-cov 所有，测试不能另起一个 collector（会抢走 tracer）；
    这里只借用 ``get_data()`` 这个合并目标。
    """
    cov = coverage_mod.Coverage(data_file=str(data_file))
    monkeypatch.setattr(coverage_mod.Coverage, "current", classmethod(lambda cls: cov))
    return cov


def test_run_entry_child_merge_stays_inside_source_package(monkeypatch, tmp_path):
    """子进程导入 src/test 模块后，归并结果仍只含 src/python 的文件。"""
    coverage_mod = pytest.importorskip("coverage")
    cov = _stub_current_coverage(monkeypatch, coverage_mod, tmp_path / "parent.coverage")

    completed = run_entry_child(_CHILD_CODE, cwd=_PROJECT_ROOT)

    assert completed.returncode == 0, completed.stderr
    assert "投资复盘助手" in completed.stdout
    measured = cov.get_data().measured_files()
    assert measured, "子进程未归并任何覆盖数据（有效 merge 失效）"
    assert not [f for f in measured if "/src/test/" in f.replace("\\", "/")], (
        "src/test 下的文件被并入覆盖数据（量测域被放宽）"
    )
    assert str(Path(constants.__file__).resolve()) in measured, "src/python 下的常量模块未被归并（归并过窄或未生效）"


def test_merge_child_data_purges_files_outside_source_package(monkeypatch, tmp_path):
    """子进程数据里混入域外文件时，归并前剔除，域内文件照常并入。"""
    coverage_mod = pytest.importorskip("coverage")
    cov = _stub_current_coverage(monkeypatch, coverage_mod, tmp_path / "parent.coverage")
    inside = str(Path(constants.__file__).resolve())
    outside = str(Path(_script_loader.__file__).resolve())

    data_file = tmp_path / "child.coverage"
    child_data = coverage_mod.CoverageData(str(data_file))
    child_data.add_lines({inside: {1}, outside: {1}})
    child_data.write()

    source_root = (_PROJECT_ROOT / constants.SOURCE_PACKAGE_REL).resolve()
    # 先让本进程已有同域数据，「不减少」才是可断言的语义（update 是并集不是替换）
    cov.get_data().add_lines({inside: {2}})
    before = set(cov.get_data().measured_files())
    _merge_child_data(data_file, source_root)
    after = cov.get_data().measured_files()

    assert outside not in after, "域外文件未被剔除"
    assert inside in after
    assert before <= set(after), "归并把已有域内数据替换掉了（应为并集）"
