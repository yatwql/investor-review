"""check-script-contract.py 的降级分支：不可解析脚本与 `__pycache__` 跳过。

规则输入的五个 AST 助手在遇到语法错误文件时不得抛异常，一律返回
「无违规」中性值（未声明 / 不引用 / 无违规）——扫描面里混入不可解析文件
不应让整个守护崩掉。`has_test_reference` 另跳过 `__pycache__` 下的 .py。
"""

from __future__ import annotations

import pytest
from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="contract")
def fixture_contract():
    return load_script("check-script-contract.py", module_name="_check_script_contract_rare")


@pytest.fixture(name="broken")
def fixture_broken(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n", encoding="utf-8")
    return path


class TestUnparsableScriptDegrades:
    def test_declared_exit_codes_returns_none(self, contract, broken):
        assert contract.declared_exit_codes(broken) is None

    def test_uses_report_contract_returns_false(self, contract, broken):
        assert contract.uses_report_contract(broken) is False

    def test_calls_function_returns_false(self, contract, broken):
        assert contract.calls_function(broken, "add_common_args") is False

    def test_consumes_verbose_returns_false(self, contract, broken):
        assert contract.consumes_verbose(broken) is False

    def test_encoding_violations_returns_empty(self, contract, broken):
        assert contract.encoding_violations(broken) == []

    def test_script_findings_still_returns_list(self, contract, broken):
        findings = contract.script_findings(broken)
        assert isinstance(findings, list)


class TestTestReferenceScan:
    def test_pycache_entries_are_skipped(self, contract, monkeypatch, tmp_path):
        cached = tmp_path / "__pycache__"
        cached.mkdir()
        (cached / "ref.py").write_text("sample-script.py\n", encoding="utf-8")
        monkeypatch.setattr(contract, "TEST_DIR", tmp_path)
        monkeypatch.setattr(contract, "_TEST_TEXT_CACHE", {})
        assert contract.has_test_reference("sample-script.py") is False

    def test_live_test_file_reference_is_found(self, contract, monkeypatch, tmp_path):
        (tmp_path / "test_ref.py").write_text('load_script("sample-script.py")\n', encoding="utf-8")
        monkeypatch.setattr(contract, "TEST_DIR", tmp_path)
        monkeypatch.setattr(contract, "_TEST_TEXT_CACHE", {})
        assert contract.has_test_reference("sample-script.py") is True
