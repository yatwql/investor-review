"""`_test_runner/portability.py` 的超时与 pip 版本判定分支。

契约：两道探针的**超时**都折算成失败项（返回失败输出，由聚合层计失败项数），
而不是抛异常中断整档；pip ≥25 时提示「LC_ALL=C 烟测不经过旧 pip 回退分支」。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.test._script_loader import load_script

pytestmark = [pytest.mark.unit, pytest.mark.unit_scripts]


@pytest.fixture(name="mod")
def fixture_mod():
    return load_script("_test_runner/portability.py", module_name="_test_runner_portability_branches_under_test")


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class TestTimeouts:
    """超时按失败处理，不向上抛。"""

    def test_encoding_probe_timeout_is_reported(self, mod, monkeypatch):
        def _timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

        monkeypatch.setattr(subprocess, "run", _timeout)
        tail = mod.run_encoding_probe(1)
        assert any("超时" in line for line in tail)

    def test_pip_probe_timeout_is_reported(self, mod, monkeypatch, tmp_path: Path):
        good = tmp_path / "requirements.txt"
        good.write_bytes("\ufeff".encode("utf-8") + b"pandas\n")
        monkeypatch.setattr(mod, "REQUIREMENTS", good)
        monkeypatch.setattr(mod, "pip_version", lambda timeout=None: "24.3.1")

        def _timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="pip", timeout=1)

        monkeypatch.setattr(subprocess, "run", _timeout)
        tail = mod.run_pip_locale_probe(1)
        assert any("超时" in line for line in tail)


class TestPipVersion:
    """`pip --version` 解析：取版本号；调用失败返回空串（探针 ② 仍可跑）。"""

    def test_version_is_parsed(self, mod, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run", lambda *a, **k: _proc(0, stdout="pip 24.3.1 from /x/site-packages (python 3.13)\n")
        )
        assert mod.pip_version() == "24.3.1"

    def test_execution_failure_yields_empty_string(self, mod, monkeypatch):
        def _boom(*args, **kwargs):
            raise OSError("无 pip")

        monkeypatch.setattr(subprocess, "run", _boom)
        assert mod.pip_version() == ""

    def test_modern_pip_prints_limited_verdict_note(self, mod, monkeypatch, tmp_path: Path, capsys):
        good = tmp_path / "requirements.txt"
        good.write_bytes("\ufeff".encode("utf-8") + b"pandas\n")
        monkeypatch.setattr(mod, "REQUIREMENTS", good)
        monkeypatch.setattr(mod, "pip_version", lambda timeout=None: "25.2")
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _proc(0, stdout="Would install 1 package\n"))
        assert mod.run_pip_locale_probe() == []
        assert "不经过旧 pip 的 locale 回退分支" in capsys.readouterr().out
