"""`--mode portability` 探针模式测试（CI portability job 的本地等价复现）。

覆盖：需求文件 BOM/PEP263 判定、两道探针的环境变量与失败回传、探针聚合结果，
以及注册表口径（探针模式不进 bench、不参与标记计数）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod():
    """加载 `_test_runner/portability.py` 为可测模块。"""
    from src.test._script_loader import load_script

    return load_script("_test_runner/portability.py", module_name="_test_runner_portability_under_test")


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class TestRequirementsBom:
    """需求文件必须带 UTF-8 BOM 或 PEP263 编码声明（旧 pip locale 回退的触发条件）。"""

    def test_utf8_bom_is_accepted(self, mod, tmp_path: Path):
        path = tmp_path / "requirements.txt"
        path.write_bytes("\ufeff".encode("utf-8") + b"pandas\n")
        ok, detail = mod.check_requirements_bom(path)
        assert ok is True
        assert "BOM" in detail

    def test_pep263_cookie_is_accepted(self, mod, tmp_path: Path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"# -*- coding: utf-8 -*-\npandas\n")
        assert mod.check_requirements_bom(path)[0] is True

    def test_plain_ascii_file_is_rejected(self, mod, tmp_path: Path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"pandas\n")
        ok, detail = mod.check_requirements_bom(path)
        assert ok is False
        assert "BOM" in detail

    def test_missing_file_is_rejected(self, mod, tmp_path: Path):
        assert mod.check_requirements_bom(tmp_path / "absent.txt")[0] is False


class TestEncodingProbe:
    """隐式编码严格档：环境变量与失败回传。"""

    def test_sets_strict_encoding_env(self, mod, monkeypatch):
        seen: dict = {}

        def _fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs.get("env", {})
            return _proc(0, stdout="100 passed in 3s\n")

        monkeypatch.setattr(subprocess, "run", _fake_run)
        assert mod.run_encoding_probe() == []
        assert seen["env"]["PYTHONWARNDEFAULTENCODING"] == "1"
        assert seen["cmd"][1:4] == ["-m", "pytest", "src/test/unit"]

    def test_failure_returns_output_tail(self, mod, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **k: _proc(1, stdout="FAILED src/test/x.py::test_y - EncodingWarning\n1 failed\n"),
        )
        tail = mod.run_encoding_probe()
        assert any("EncodingWarning" in line for line in tail)


class TestPipLocaleProbe:
    """需求文件 locale 解码探针：确定性判定优先 + LC_ALL=C 烟测。"""

    def test_deterministic_check_short_circuits_without_subprocess(self, mod, monkeypatch, tmp_path: Path):
        bad = tmp_path / "requirements.txt"
        bad.write_bytes(b"pandas\n")
        monkeypatch.setattr(mod, "REQUIREMENTS", bad)
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("不应启动子进程"))
        assert mod.run_pip_locale_probe() != []

    def test_runs_under_c_locale(self, mod, monkeypatch, tmp_path: Path):
        good = tmp_path / "requirements.txt"
        good.write_bytes("\ufeff".encode("utf-8") + b"pandas\n")
        monkeypatch.setattr(mod, "REQUIREMENTS", good)
        monkeypatch.setattr(mod, "pip_version", lambda timeout=None: "24.3.1")
        seen: dict = {}

        def _fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            seen["env"] = kwargs.get("env", {})
            return _proc(0, stdout="Would install ...\n")

        monkeypatch.setattr(subprocess, "run", _fake_run)
        assert mod.run_pip_locale_probe() == []
        assert seen["env"]["LC_ALL"] == "C"
        assert seen["env"]["PYTHONUTF8"] == "0"
        assert "--dry-run" in seen["cmd"]

    def test_failure_returns_output_tail(self, mod, monkeypatch, tmp_path: Path):
        good = tmp_path / "requirements.txt"
        good.write_bytes("\ufeff".encode("utf-8") + b"pandas\n")
        monkeypatch.setattr(mod, "REQUIREMENTS", good)
        monkeypatch.setattr(mod, "pip_version", lambda timeout=None: "24.3.1")
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **k: _proc(1, stderr="UnicodeDecodeError: 'gbk' codec can't decode byte 0xac")
        )
        tail = mod.run_pip_locale_probe()
        assert any("UnicodeDecodeError" in line for line in tail)


class TestRunPortabilityAggregate:
    """两道探针的聚合口径：通过数=探针项数，任一失败即非零退出。"""

    def test_all_probes_pass(self, mod, monkeypatch):
        monkeypatch.setattr(mod, "run_encoding_probe", lambda timeout=None: [])
        monkeypatch.setattr(mod, "run_pip_locale_probe", lambda timeout=None: [])
        stats = mod.run_portability(desc="探针")
        assert (stats["passed"], stats["failed"], stats["exit_code"]) == (2, 0, 0)
        assert stats["timed_out"] is False

    def test_single_failure_marks_non_zero_exit(self, mod, monkeypatch):
        monkeypatch.setattr(mod, "run_encoding_probe", lambda timeout=None: [])
        monkeypatch.setattr(mod, "run_pip_locale_probe", lambda timeout=None: ["缺少 BOM"])
        stats = mod.run_portability()
        assert (stats["passed"], stats["failed"]) == (1, 1)
        assert stats["exit_code"] != 0


class TestRegistryWiring:
    """注册表口径：探针模式无 marker、不进 bench、也不参与标记计数。"""

    @staticmethod
    def _modes():
        from src.test._script_loader import load_script

        return load_script("_test_runner/modes.py", module_name="_test_runner_modes_portability_under_test")

    def test_probe_mode_declares_no_marker(self):
        modes = self._modes()
        cfg = modes.MODES["portability"]
        assert cfg.get("probes") is True
        assert "marker" not in cfg
        assert modes.mode_marker_expr("portability") == ""

    def test_bench_excludes_probe_modes(self):
        modes = self._modes()
        assert "portability" not in modes._BENCH_MODES
        assert "unit" in modes._BENCH_MODES
