"""测试：真实耗时与真实子进程守卫（测试内 `time.sleep(≥0.1)` / 未 mock 的真子进程即报）。

口径来源：测试应当验证行为、不应消耗墙钟。真睡满整段耗时、真起解释器跑 pytest，
都会让墙钟随宿主环境与并行度漂移，是 CI 抖动与 flaky 的主要来源。本文件锁四侧：
真等待/未 mock 的真子进程 → finding；短等待 / 已被替身接管的子进程 / 非解释器子进程
→ 放行；例外表登记点 → 放行；例外表自审（字段、到期、陈旧）三类问题。
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    # 实现包内部是扁平 import（`_test_redundancy.*`），注入 scripts/ 才能加载
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _test_redundancy.slow_io import (  # noqa: E402
    KIND_SLEEP,
    KIND_SUBPROCESS,
    _ExceptionTable,
    audit_exceptions,
    audit_stale_exceptions,
    check_slow_or_subprocess,
    extract_slow_or_subprocess,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.unit_scripts,
]


def _extract(tmp_path: Path, body: str) -> tuple[Path, list[list]]:
    """解析样例源，返回（文件, 文件内事实）。"""
    path = tmp_path / "test_sample.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path, extract_slow_or_subprocess(_parse(path), path)


def _parse(path: Path):
    import ast

    return ast.parse(path.read_text(encoding="utf-8"))


class TestSlowSleep:
    def test_short_sleep_is_accepted(self, tmp_path):
        """低于阈值的短等待（让出一次调度）不属浪费墙钟的形态。"""
        _path, facts = _extract(tmp_path, "import time\n\ndef test_x():\n    time.sleep(0.01)\n")
        assert facts == []

    def test_long_sleep_is_a_finding(self, tmp_path):
        path, facts = _extract(tmp_path, "import time\n\ndef test_x():\n    time.sleep(1)\n")
        assert [(line, kind) for line, kind, _key in facts] == [(4, KIND_SLEEP)]
        assert facts[0][2].endswith("::slow-sleep::time.sleep(1)")
        findings = check_slow_or_subprocess({path: facts}, _ExceptionTable(set(), []))
        assert len(findings) == 1
        assert "真实等待" in findings[0]

    def test_non_literal_sleep_is_not_judged(self, tmp_path):
        """实参不是字面量时无法静态判定时长，不报（避免误报）。"""
        _path, facts = _extract(tmp_path, "import time\n\ndef test_x(seconds):\n    time.sleep(seconds)\n")
        assert facts == []


class TestRealSubprocess:
    def test_unmocked_pytest_run_is_a_finding(self, tmp_path):
        path, facts = _extract(
            tmp_path,
            """\
            import subprocess
            import sys

            def test_x():
                subprocess.run([sys.executable, "-m", "pytest", "-q"], check=True)
            """,
        )
        assert [(line, kind) for line, kind, _key in facts] == [(5, KIND_SUBPROCESS)]
        findings = check_slow_or_subprocess({path: facts}, _ExceptionTable(set(), []))
        assert len(findings) == 1
        assert "真实执行子进程" in findings[0]

    def test_monkeypatched_subprocess_is_accepted(self, tmp_path):
        """同函数体内 `monkeypatch.setattr(subprocess, …)` 即被替身接管，不真执行。"""
        _path, facts = _extract(
            tmp_path,
            """\
            import subprocess
            import sys

            def test_x(monkeypatch):
                monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
                subprocess.run([sys.executable, "-m", "pytest"])
            """,
        )
        assert facts == []

    def test_decorator_patch_is_accepted(self, tmp_path):
        """装饰器上的 `@patch("subprocess.run")` 不在函数体内，同样算 mock 证据。"""
        _path, facts = _extract(
            tmp_path,
            """\
            import subprocess
            import sys
            from unittest.mock import patch

            @patch("subprocess.run")
            def test_x(_run):
                subprocess.run([sys.executable, "-m", "pytest"])
            """,
        )
        assert facts == []

    def test_subprocess_without_interpreter_is_accepted(self, tmp_path):
        """与解释器/测试无关的子进程（如 ls）不属本规则要拦的形态。"""
        _path, facts = _extract(tmp_path, "import subprocess\n\ndef test_x():\n    subprocess.run(['ls'])\n")
        assert facts == []


class TestSlowOrSubprocessExceptions:
    def _entry(self, key: str, **overrides) -> dict:
        entry = {"name": key, "owner": "o", "reason": "r", "expiry": "2027-06-30", "replacement": "x"}
        entry.update(overrides)
        return entry

    def test_registered_site_is_accepted(self, tmp_path):
        path, facts = _extract(tmp_path, "import time\n\ndef test_x():\n    time.sleep(1)\n")
        table = _ExceptionTable({facts[0][2]}, [self._entry(facts[0][2])])
        assert check_slow_or_subprocess({path: facts}, table) == []

    def test_metadata_audit_reports_missing_fields(self):
        findings = audit_exceptions(_ExceptionTable(set(), [{"name": "x"}]))
        assert any("缺少字段" in finding for finding in findings)

    def test_metadata_audit_reports_expired_entry(self):
        entry = self._entry("x", expiry="2020-01-01")
        findings = audit_exceptions(_ExceptionTable(set(), [entry]))
        assert any("已于 2020-01-01 到期" in finding for finding in findings)

    def test_stale_entry_is_reported(self, tmp_path):
        """登记点已删/已改（不再命中）→ 例外成免死金牌，须报 stale。"""
        path, facts = _extract(tmp_path, "import time\n\ndef test_x():\n    time.sleep(1)\n")
        entry = self._entry("test_sample.py::slow-sleep::time.sleep(9)")
        stale = audit_stale_exceptions(_ExceptionTable(set(), [entry]), {path: facts})
        assert any("未命中任何违规" in finding for finding in stale)

    def test_repo_exception_table_is_well_formed(self):
        """现树例外表：字段齐全、未到期，且每条都仍命中违规。"""
        from _test_redundancy.slow_io import load_exceptions

        table = load_exceptions()
        assert audit_exceptions(table) == []
        facts = {
            path: extract_slow_or_subprocess(_parse(path), path)
            for path in sorted((_REPO_ROOT / "src" / "test").rglob("test_*.py"))
        }
        assert audit_stale_exceptions(table, facts) == []
