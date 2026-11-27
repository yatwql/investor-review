"""测试：浮点求和口径守卫（均值/方差须 `math.fsum`，内建 `sum()` 朴素累加即报 FLOATSUM）。

口径来源：内建 `sum()` 对浮点的累加策略随解释器演进（朴素累加 → 补偿求和），同一份数据
在不同版本上末位可能不同；零方差序列在朴素累加下会累出极小非零残差，令 `ssx > 0` 判据
失效、算出天文数字的标准误。本文件锁四侧：均值/离差形态 → finding；整数计数 / 已 fsum
包裹 / `sum` 被重绑定 / 非守卫面 → 放行；例外表登记点 → 放行；例外表自审四类问题。
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from src.test._script_loader import load_script

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


@pytest.fixture(name="float_sum_guard")
def fixture_float_sum_guard():
    """浮点求和口径守卫模块（先加载薄 CLI 以接入 `scripts/` 的 sys.path）。"""
    load_script("check-code-traces.py")
    return load_script("_traces_code/numeric_sum.py", module_name="_traces_code_numeric_sum")


def _write_source(tmp_path: Path, body: str, rel: str = "scripts/sample.py") -> tuple[Path, Path]:
    """在合成仓库根下写一个样例源文件，返回（文件, 仓库根）。"""
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path, tmp_path


def _scan(guard, source: Path, root: Path, exceptions=None):
    """按合成仓库根扫描（守卫面判定与例外表均可控）。"""
    table = exceptions if exceptions is not None else guard._ExceptionTable(set(), [])
    return guard._scan_float_sum(source, table, repo_root=root)


class TestFloatSumDetection:
    def test_mean_pattern_is_a_finding(self, float_sum_guard, tmp_path):
        source, root = _write_source(tmp_path, "def f(xs):\n    return sum(xs) / len(xs)\n")
        hits = _scan(float_sum_guard, source, root)
        assert [(line, cat) for line, cat, _desc, _text in hits] == [(2, "FLOATSUM")]
        assert hits[0][3] == "sum(xs)"

    def test_deviation_squares_pattern_is_a_finding(self, float_sum_guard, tmp_path):
        source, root = _write_source(
            tmp_path,
            "def f(pairs):\n    return sum((a - b) ** 2 for a, b in pairs)\n",
        )
        hits = _scan(float_sum_guard, source, root)
        assert [cat for _line, cat, _desc, _text in hits] == ["FLOATSUM"]

    def test_integer_count_ratio_is_accepted(self, float_sum_guard, tmp_path):
        """`sum(1 for …) / len(…)` 是整数计数比，整数加法无末位漂移。"""
        source, root = _write_source(tmp_path, "def f(xs):\n    return sum(1 for x in xs if x) / len(xs)\n")
        assert _scan(float_sum_guard, source, root) == []

    def test_integer_literal_sequence_is_accepted(self, float_sum_guard, tmp_path):
        source, root = _write_source(tmp_path, "def f():\n    return sum([1, 2, 3]) / 3\n")
        assert _scan(float_sum_guard, source, root) == []

    def test_len_based_sequence_is_accepted(self, float_sum_guard, tmp_path):
        source, root = _write_source(tmp_path, "def f(rows):\n    return sum(len(row) for row in rows) / len(rows)\n")
        assert _scan(float_sum_guard, source, root) == []

    def test_sum_inside_math_fsum_is_accepted(self, float_sum_guard, tmp_path):
        """本身就是目标形态（已被 `math.fsum` 包裹）不报。"""
        source, root = _write_source(
            tmp_path,
            "import math\n\ndef f(pairs):\n    return math.fsum([sum((a - b) ** 2 for a, b in pairs)])\n",
        )
        assert _scan(float_sum_guard, source, root) == []

    def test_locally_rebound_sum_is_accepted(self, float_sum_guard, tmp_path):
        """`sum` 被局部重绑定后不是内建函数，判定不成立。"""
        source, root = _write_source(tmp_path, "def f(xs, sum):\n    return sum(xs) / len(xs)\n")
        assert _scan(float_sum_guard, source, root) == []

    def test_outside_guarded_surface_is_skipped(self, float_sum_guard, tmp_path):
        """守卫面只含 `src/python/**` 与 `scripts/**`（测试域归测试冗余检查）。"""
        source, root = _write_source(tmp_path, "def f(xs):\n    return sum(xs) / len(xs)\n", rel="src/test/sample.py")
        assert _scan(float_sum_guard, source, root) == []


class TestFloatSumExceptions:
    def _key_of(self, guard, source: Path) -> str:
        return guard._float_sum_hits(source)[0][2]

    def test_registered_site_is_accepted(self, float_sum_guard, tmp_path):
        source, root = _write_source(tmp_path, "def f(xs):\n    return sum(xs) / len(xs)\n")
        key = self._key_of(float_sum_guard, source)
        assert key.endswith("sample.py::f::sum(xs)")
        assert _scan(float_sum_guard, source, root, float_sum_guard._ExceptionTable({key}, [])) == []

    def test_metadata_audit_reports_missing_fields(self, float_sum_guard):
        table = float_sum_guard._ExceptionTable({"scripts/sample.py::f::sum(xs)"}, [{"name": "scripts/sample.py::f"}])
        findings = float_sum_guard.audit_exceptions(table, repo_root=Path("/nonexistent"))
        assert any("缺少字段" in finding for finding in findings)

    def test_metadata_audit_reports_expired_entry(self, float_sum_guard, tmp_path):
        source, root = _write_source(tmp_path, "def f(xs):\n    return sum(xs) / len(xs)\n")
        entry = {
            "name": self._key_of(float_sum_guard, source),
            "owner": "o",
            "reason": "r",
            "expiry": "2020-01-01",
            "replacement": "x",
        }
        findings = float_sum_guard.audit_exceptions(float_sum_guard._ExceptionTable(set(), [entry]), repo_root=root)
        assert any("已于 2020-01-01 到期" in finding for finding in findings)

    def test_audit_reports_stale_entry(self, float_sum_guard, tmp_path):
        """登记点已是 `math.fsum`（不再命中）→ 例外成免死金牌，须报 stale。"""
        source, root = _write_source(tmp_path, "import math\n\ndef f(xs):\n    return math.fsum(xs) / len(xs)\n")
        entry = {
            "name": "scripts/sample.py::f::sum(xs) / len(xs)",
            "owner": "o",
            "reason": "r",
            "expiry": "2027-06-30",
            "replacement": "x",
        }
        findings = float_sum_guard.audit_exceptions(float_sum_guard._ExceptionTable(set(), [entry]), repo_root=root)
        assert any("未命中任何违规" in finding for finding in findings)
        assert source.is_file()

    def test_valid_entry_has_no_audit_finding(self, float_sum_guard, tmp_path):
        source, root = _write_source(tmp_path, "def f(xs):\n    return sum(xs) / len(xs)\n")
        entry = {
            "name": self._key_of(float_sum_guard, source),
            "owner": "o",
            "reason": "r",
            "expiry": "2027-06-30",
            "replacement": "x",
        }
        assert float_sum_guard.audit_exceptions(float_sum_guard._ExceptionTable(set(), [entry]), repo_root=root) == []


class TestFloatSumWiring:
    def test_category_lands_in_code_bucket(self):
        """FLOATSUM 必须在 CODE 桶（退出码 2），否则落进 LOW 兜底静默降级。"""
        traces = load_script("check-code-traces.py")
        assert "FLOATSUM" in traces.CODE_CATEGORIES
        assert "FLOATSUM" not in traces.HIGH_CATEGORIES
        assert "FLOATSUM" not in traces.LOW_CATEGORIES

    def test_repo_tree_is_clean_for_float_sum(self):
        """现树零 FLOATSUM finding（改用例/改生产代码时同步处理，不留存量）。"""
        traces = load_script("check-code-traces.py")
        guard = load_script("_traces_code/numeric_sum.py", module_name="_traces_code_numeric_sum")
        assert guard.audit_exceptions(guard.load_exceptions()) == []
        repo_root = Path(traces.REPO_ROOT)
        remaining = []
        for subdir in ("src/python", "scripts"):
            for path in sorted((repo_root / subdir).rglob("*.py")):
                remaining += [(path, hit) for hit in traces._scan_float_sum(path)]
        assert remaining == []
