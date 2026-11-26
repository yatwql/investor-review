"""测试：`pragma: no cover` 豁免清单守卫（未登记即报 PRAGMA，登记后放行）。

口径来源：`test-coverage.md`「不可达行处理原则」——可达分支补真用例覆盖，只有
平台分支 / 可选依赖缺失才允许标注，且须在该文档的「豁免清单」表按 `文件:行号`
逐行登记。本文件锁两侧：未登记 → 有 finding；已登记 → 无 finding。
"""

from __future__ import annotations

import pytest
from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(name="pragma_guard")
def fixture_pragma_guard():
    """豁免清单守卫模块（独立实例，避免与 CLI 加载时的模块状态耦合）。

    先加载薄 CLI：它在导入期把 `scripts/` 接入 `sys.path`，`_traces_code` 子包的
    绝对导入才可解析（子包模块不能单独按文件路径加载）。
    """
    load_script("check-code-traces.py")
    return load_script("_traces_code/pragma_exemptions.py", module_name="_traces_code_pragma_guard")


def _write_source(tmp_path):
    """造一个带 `pragma: no cover` 的被检源文件，返回（文件, pragma 行号）。"""
    body = ["def f():", "    return 1", "", "if True:  # pragma: no cover - 样例"]
    source = tmp_path / "sample.py"
    source.write_text("\n".join(body) + "\n", encoding="utf-8")
    return source, len(body)


def _write_doc(tmp_path, entries: list[str]):
    doc = tmp_path / "test-coverage.md"
    rows = ["| `文件:行` | 类别 | 理由 | 到期复审 |", "|:--|:--|:--|:--|"]
    rows += [f"| `{ref}` | 平台分支 | 样例 | 下次发布前 |" for ref in entries]
    doc.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return doc


class TestPragmaExemptionGuard:
    def test_unregistered_pragma_is_a_finding(self, pragma_guard, tmp_path):
        source, lineno = _write_source(tmp_path)
        doc = _write_doc(tmp_path, [])
        hits = pragma_guard._scan_pragma_no_cover(source, doc)
        assert [(line, cat) for line, cat, _desc, _text in hits] == [(lineno, "PRAGMA")]

    def test_registered_pragma_is_accepted(self, pragma_guard, tmp_path):
        source, lineno = _write_source(tmp_path)
        ref = f"{pragma_guard._rel_posix(source)}:{lineno}"
        doc = _write_doc(tmp_path, [ref])
        assert pragma_guard._scan_pragma_no_cover(source, doc) == []

    def test_registry_is_line_strict(self, pragma_guard, tmp_path):
        """登记行号漂移一位不再豁免：豁免的是那一行分支，不是整个文件。"""
        source, lineno = _write_source(tmp_path)
        ref = f"{pragma_guard._rel_posix(source)}:{lineno + 1}"
        doc = _write_doc(tmp_path, [ref])
        assert [line for line, _cat, _desc, _text in pragma_guard._scan_pragma_no_cover(source, doc)] == [lineno]
